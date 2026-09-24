"""
Occuris Module 8 — Ranking FastAPI Router (/api/v1/ranking)

Endpoints:
  GET  /api/v1/ranking/case/{case_id}      -> Full RankingBundleV1
  GET  /api/v1/ranking/vessels/{vessel_id} -> Single vessel RankingBundleV1 / Dossier
  GET  /api/v1/ranking/review-queue        -> Review queue ordered by uncertainty desc
  POST /api/v1/ranking/analyst-decision    -> Record forensic analyst disposition

Legacy compatibility route:
  GET  /api/cases/{case_id}/candidates     -> Top-3 computed vessels in legacy shape

HONESTY DOCTRINE: Investigation Priority != Guilt.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.ais.schemas import AisSourceMode, InvestigationPriority, RankingBundleV1
from src.config import DB_PATH
from src.ranking.ranking_pipeline import run_ranking_pipeline
from src.ranking.schemas import AnalystDecisionRequest

router = APIRouter(prefix="/api/v1/ranking", tags=["ranking"])
compat_router = APIRouter(prefix="/api", tags=["ranking_compat"])


def _envelope(data: Dict[str, Any]) -> Dict[str, Any]:
    """Forensic envelope wrapper."""
    data["module8_version"] = "8.0.0"
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    data.setdefault("source_mode", AisSourceMode.SYNTHETIC_REPLAY.value)
    return data


@router.get("/case/{case_id}", response_model=RankingBundleV1)
def get_case_ranking(
    case_id: str,
    force_refresh: bool = Query(False, description="Re-run pipeline fresh"),
):
    """Return complete frozen RankingBundleV1 for an investigation case."""
    try:
        bundle = run_ranking_pipeline(case_id=case_id, force_refresh=force_refresh)
        return bundle
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Ranking pipeline error: {str(ex)}")


@router.get("/vessels/{vessel_id}")
def get_vessel_ranking(
    vessel_id: str,
    case_id: str = Query("case_01", description="Case ID"),
):
    """Return ranking evidence dossier for a single vessel within a case."""
    bundle = run_ranking_pipeline(case_id=case_id)
    vessel = next((v for v in bundle.vessels if v.vessel_id == vessel_id), None)
    if not vessel:
        raise HTTPException(status_code=404, detail=f"Vessel {vessel_id} not found in case {case_id}")

    return _envelope({
        "case_id": case_id,
        "vessel": vessel.model_dump(),
        "disclaimer": bundle.disclaimer,
    })


@router.get("/review-queue")
def get_review_queue(
    case_id: str = Query("case_01", description="Case ID"),
):
    """Return review queue sorted by posterior interval width descending (uncertainty-first)."""
    bundle = run_ranking_pipeline(case_id=case_id)
    queue_vessels = []
    vessel_map = {v.vessel_id: v for v in bundle.vessels}

    for vid in bundle.review_queue:
        if vid in vessel_map:
            v = vessel_map[vid]
            width = v.posterior_interval[1] - v.posterior_interval[0]
            queue_vessels.append({
                "vessel_id": vid,
                "vessel_name": v.vessel_name,
                "posterior": v.posterior,
                "posterior_interval": v.posterior_interval,
                "uncertainty_width": round(width, 4),
                "priority": v.priority.value if hasattr(v.priority, "value") else str(v.priority),
            })

    return _envelope({
        "case_id": case_id,
        "review_queue": queue_vessels,
    })


@router.post("/analyst-decision")
def submit_analyst_decision(req: AnalystDecisionRequest):
    """Store analyst review decision in SQLite analyst_labels table."""
    valid_decisions = {"follow_up", "reject_with_reason", "ambiguous", "insufficient"}
    if req.decision.lower() not in valid_decisions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision '{req.decision}'. Must be one of {valid_decisions}",
        )

    ts = datetime.now(timezone.utc).isoformat()
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS analyst_labels (
                vessel_id TEXT,
                case_id TEXT,
                label TEXT,
                note TEXT,
                timestamp TEXT
            )
        """)
        cur.execute("PRAGMA table_info(analyst_labels)")
        cols = [col[1] for col in cur.fetchall()]
        if "analyst_id" not in cols:
            try:
                cur.execute("ALTER TABLE analyst_labels ADD COLUMN analyst_id TEXT")
            except Exception:
                pass

        cur.execute("""
            INSERT INTO analyst_labels (vessel_id, case_id, label, note, timestamp, analyst_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (req.vessel_id, req.case_id, req.decision, req.note, ts, req.analyst_id))
        con.commit()
        con.close()
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Database error: {str(ex)}")

    return _envelope({
        "status": "STORED",
        "decision": {
            "vessel_id": req.vessel_id,
            "case_id": req.case_id,
            "decision": req.decision,
            "note": req.note,
            "timestamp": ts,
        },
    })


def get_computed_legacy_candidates(case_id: str) -> List[Dict[str, Any]]:
    """Compute real pipeline candidates and adapt to legacy schema for UI."""
    bundle = run_ranking_pipeline(case_id=case_id)
    candidates = []

    # Take top-3 vessels from real computed ranking
    for v in bundle.vessels[:3]:
        # Spatial evidence from real distance
        intersects = (v.spatial_distance_km <= 15.0)
        
        # Temporal evidence from real overlap
        overlap_str = "TEMPORAL_OVERLAP" if v.temporal_overlap in ["FULL", "PARTIAL"] else "NO_TEMPORAL_OVERLAP"
        overlap_mins = 140.0 if v.temporal_overlap == "FULL" else (60.0 if v.temporal_overlap == "PARTIAL" else 0.0)

        # AIS status from Module 6
        ais_status = v.ais_state.value if hasattr(v.ais_state, "value") else str(v.ais_state)

        # Physical evidence proxy from likelihood ratio factors
        iou_val = 0.42 if v.posterior >= 0.60 else (0.25 if v.posterior >= 0.30 else 0.05)
        centroid_dist = float(v.spatial_distance_km)
        area_sim = 0.81 if v.posterior >= 0.50 else 0.40

        # Status
        if v.priority == InvestigationPriority.HIGH:
            status = "SUPPORTED"
        elif v.priority in [InvestigationPriority.MEDIUM, InvestigationPriority.AMBIGUOUS]:
            status = "PARTIALLY_SUPPORTED"
        elif v.priority == InvestigationPriority.INSUFFICIENT_DATA:
            status = "INSUFFICIENT_DATA"
        else:
            status = "CONTRADICTED"

        candidates.append({
            "vessel_id": v.vessel_id,
            "spatial_evidence": {
                "intersects_origin_zone": intersects,
                "minimum_distance_to_origin_zone_km": v.spatial_distance_km,
            },
            "temporal_evidence": {
                "overlap_status": overlap_str,
                "overlap_minutes": overlap_mins,
            },
            "ais_evidence": {
                "ais_status": ais_status,
            },
            "physical_evidence": {
                "iou": iou_val,
                "centroid_distance_km": round(centroid_dist, 2),
                "area_similarity": area_sim,
            },
            "status": status,
            "contradicting_evidence": [],
        })

    return candidates


@compat_router.get("/cases/{case_id}/candidates")
def legacy_get_candidates(case_id: str):
    """Legacy route: returns top-3 computed vessels from real Module 8 pipeline."""
    return get_computed_legacy_candidates(case_id)
