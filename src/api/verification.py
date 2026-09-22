"""
Module 6 — AIS Verification Engine — FastAPI Router
Prefix: /api/v1/verification
Endpoints:
- POST /run/{vessel_id}?case_id= (idempotent; returns bundle + ledger_hash)
- GET /report/{vessel_id}?case_id= (cached, includes input hashes)
- GET /case/{case_id} (all vessel reports for a case)
- GET /ledger/verify (full chain incl. Module 6)
- POST /analyst-labels (storage only)
- GET /review-queue (interval-width desc)
All responses: source_mode, generated_at, module6_version.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.ais.audit import MerkleAuditEngine, canonical_json
from src.ais.schemas import (
    AnalystLabel,
    AisSourceMode,
    CaseContextV1,
    EvidenceBundleV1,
    Module6VerificationBundleV1,
)
from src.config import DB_PATH, ROOT, CASES

from src.verification.pipeline import VerificationPipeline, MODULE6_VERSION, load_verification_config

router = APIRouter(prefix="/api/v1/verification", tags=["Module 6 — AIS Verification"])

# ── Module State ──────────────────────────────────────────────────────────────

_pipeline: Optional[VerificationPipeline] = None
_results_cache: Dict[str, Module6VerificationBundleV1] = {}  # key: "vessel_id::case_id"
_analyst_labels: List[AnalystLabel] = []


def _get_pipeline() -> VerificationPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = VerificationPipeline()
    return _pipeline


def _cache_key(vessel_id: str, case_id: str) -> str:
    return f"{vessel_id}::{case_id}"


def _build_case_context(case_id: str) -> CaseContextV1:
    """Build CaseContextV1 from config CASES."""
    case_cfg = CASES.get(case_id)
    if not case_cfg:
        # Build a minimal context for unknown cases
        return CaseContextV1(
            case_id=case_id,
            release_window_start=datetime(2024, 3, 14, 6, 0, tzinfo=timezone.utc),
            release_window_end=datetime(2024, 3, 15, 6, 0, tzinfo=timezone.utc),
        )

    spill_bbox = case_cfg.get("spill_bbox", {})
    origin_zone = {
        "type": "Polygon",
        "coordinates": [[
            [spill_bbox.get("lon_min", 0), spill_bbox.get("lat_min", 0)],
            [spill_bbox.get("lon_max", 0), spill_bbox.get("lat_min", 0)],
            [spill_bbox.get("lon_max", 0), spill_bbox.get("lat_max", 0)],
            [spill_bbox.get("lon_min", 0), spill_bbox.get("lat_max", 0)],
            [spill_bbox.get("lon_min", 0), spill_bbox.get("lat_min", 0)],
        ]],
    }

    sar_ts_str = case_cfg.get("sar_timestamp", "2024-03-15T06:30:00Z")
    sar_ts = datetime.fromisoformat(sar_ts_str.replace("Z", "+00:00"))
    release_hours = case_cfg.get("release_window_hours", 24)

    from datetime import timedelta
    release_start = sar_ts - timedelta(hours=release_hours)
    release_end = sar_ts

    return CaseContextV1(
        case_id=case_id,
        origin_zones=[origin_zone],
        release_window_start=release_start,
        release_window_end=release_end,
        sar_acquisition_time=sar_ts,
        spill_center=case_cfg.get("spill_center"),
    )


def _get_evidence_bundle(vessel_id: str, case_id: str) -> EvidenceBundleV1:
    """Get EvidenceBundleV1 from the Module 5 maritime engine."""
    # Import here to avoid circular dependency
    from src.api.maritime import engine, ensure_pipeline

    ensure_pipeline()

    track = engine.tracks.get(vessel_id)
    if not track:
        raise HTTPException(status_code=404, detail=f"Vessel {vessel_id} not found in Module 5")

    journey = engine.journeys.get(vessel_id)
    transit = engine.transits.get(vessel_id)
    assessment = engine.assessments.get(vessel_id)
    dna = engine.dna_profiles.get(vessel_id)
    dark_hyps = engine.dark_hypotheses.get(vessel_id, [])

    dna_best_confidence = None
    dna_method = None
    if dna:
        matches = engine.dna_extractor.reidentify_post_gap(track, engine.dna_profiles)
        if matches:
            dna_best_confidence = matches[0].confidence_pct
            dna_method = matches[0].method

    anomaly_ids = [
        e.event_id for e in engine.collective_events
        if vessel_id in e.vessel_cluster
    ]

    return EvidenceBundleV1(
        case_id=case_id,
        vessel_id=vessel_id,
        journey=journey,
        ais_gaps=list(track.gaps),
        transit_analysis=transit,
        behaviour_assessment=assessment,
        dna_profile_id=vessel_id if dna else None,
        dna_best_match_confidence=dna_best_confidence,
        dna_method=dna_method,
        collective_anomaly_ids=anomaly_ids,
        dark_path_hypotheses=dark_hyps,
        latest_event_hash=engine.audit_engine.latest_hash,
        source_mode=engine.source.source_mode,
    )


def _get_all_bundles_and_tracks(case_id: str):
    """Get all bundles and tracks from Module 5."""
    from src.api.maritime import engine, ensure_pipeline

    ensure_pipeline()

    bundles = []
    for vessel_id in engine.tracks:
        try:
            bundle = _get_evidence_bundle(vessel_id, case_id)
            bundles.append(bundle)
        except HTTPException:
            continue

    return bundles, engine.tracks


def _extend_audit_chain(result: Module6VerificationBundleV1) -> str:
    """Extend Module 5 Merkle chain with VERIFICATION_ARTIFACT record."""
    from src.api.maritime import engine, ensure_pipeline

    ensure_pipeline()

    artifact = {
        "record_type": "VERIFICATION_ARTIFACT",
        "case_id": result.case_id,
        "vessel_id": result.vessel_id,
        "ais_state": result.ais_state.value,
        "integrity_score": result.integrity_score,
        "module6_version": result.module6_version,
        "anomaly_count": len(result.anomaly_classifications),
    }

    curr_h, _ = engine.audit_engine.hash_and_append(artifact)
    return curr_h


def _envelope(data: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap response with source_mode, generated_at, module6_version."""
    data["module6_version"] = MODULE6_VERSION
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    data.setdefault("source_mode", AisSourceMode.SYNTHETIC_REPLAY.value)
    return data


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/run/{vessel_id}")
def run_verification(
    vessel_id: str,
    case_id: str = Query("case_01", description="Investigation case ID"),
):
    """Idempotent: run 6-stage verification pipeline for a vessel. Returns bundle + ledger_hash."""
    key = _cache_key(vessel_id, case_id)

    # Idempotent: return cached if exists
    if key in _results_cache:
        cached = _results_cache[key]
        return _envelope({
            "source_mode": cached.source_mode.value,
            "status": "CACHED",
            "verification_bundle": cached.model_dump(),
            "ledger_hash": cached.ledger_hash,
        })

    pipeline = _get_pipeline()
    context = _build_case_context(case_id)
    bundle = _get_evidence_bundle(vessel_id, case_id)

    # Get all bundles and tracks for concurrency analysis
    all_bundles, all_tracks = _get_all_bundles_and_tracks(case_id)

    from src.api.maritime import engine
    track = engine.tracks.get(vessel_id)

    result = pipeline.run(
        bundle=bundle,
        context=context,
        track=track,
        all_bundles=all_bundles,
        all_tracks=all_tracks,
    )

    # Extend Merkle audit chain
    ledger_hash = _extend_audit_chain(result)
    result.ledger_hash = ledger_hash

    # Cache
    _results_cache[key] = result

    # Persist to DB
    _persist_verification(result)

    return _envelope({
        "source_mode": result.source_mode.value,
        "status": "COMPUTED",
        "verification_bundle": result.model_dump(),
        "ledger_hash": ledger_hash,
    })


@router.get("/report/{vessel_id}")
def get_verification_report(
    vessel_id: str,
    case_id: str = Query("case_01", description="Investigation case ID"),
):
    """Retrieve cached verification result with input hashes."""
    key = _cache_key(vessel_id, case_id)

    if key not in _results_cache:
        raise HTTPException(
            status_code=404,
            detail=f"No verification report for {vessel_id} in case {case_id}. Run POST /run first.",
        )

    result = _results_cache[key]

    return _envelope({
        "source_mode": result.source_mode.value,
        "verification_bundle": result.model_dump(),
        "ledger_hash": result.ledger_hash,
        "input_hashes": {
            "case_id": case_id,
            "vessel_id": vessel_id,
            "schema_version": result.schema_version,
        },
    })


@router.get("/case/{case_id}")
def get_case_verification(case_id: str):
    """Retrieve all vessel verification reports for a case."""
    case_results = {
        k.split("::")[0]: v.model_dump()
        for k, v in _results_cache.items()
        if k.endswith(f"::{case_id}")
    }

    return _envelope({
        "source_mode": AisSourceMode.SYNTHETIC_REPLAY.value,
        "case_id": case_id,
        "vessel_count": len(case_results),
        "reports": case_results,
    })


@router.get("/ledger/verify")
def verify_ledger():
    """Full chain verification including Module 6 VERIFICATION_ARTIFACT records."""
    from src.api.maritime import engine, ensure_pipeline

    ensure_pipeline()
    result = engine.audit_engine.verify_ledger()

    return _envelope({
        "source_mode": AisSourceMode.SYNTHETIC_REPLAY.value,
        "verification": result.model_dump(),
    })


class AnalystLabelRequest(BaseModel):
    vessel_id: str
    case_id: str
    label: str  # INNOCENT_PATTERN | SUSPICIOUS_PATTERN | UNKNOWN
    note: str = ""


@router.post("/analyst-labels")
def submit_analyst_label(req: AnalystLabelRequest):
    """Submit analyst label. STORAGE ONLY — no feedback into scoring."""
    label = AnalystLabel(
        vessel_id=req.vessel_id,
        case_id=req.case_id,
        label=req.label,
        note=req.note,
    )
    _analyst_labels.append(label)
    _persist_analyst_label(label)

    return _envelope({
        "source_mode": AisSourceMode.SYNTHETIC_REPLAY.value,
        "status": "STORED",
        "label": label.model_dump(),
    })


@router.get("/review-queue")
def get_review_queue():
    """Return vessels sorted by review priority (interval width desc = most ambiguous first)."""
    queue = sorted(
        _results_cache.values(),
        key=lambda r: r.review_priority,
        reverse=True,
    )

    items = []
    for r in queue:
        items.append({
            "vessel_id": r.vessel_id,
            "case_id": r.case_id,
            "ais_state": r.ais_state.value,
            "integrity_score": r.integrity_score,
            "integrity_interval": r.integrity_interval,
            "review_priority": r.review_priority,
            "anomaly_count": len(r.anomaly_classifications),
        })

    return _envelope({
        "source_mode": AisSourceMode.SYNTHETIC_REPLAY.value,
        "queue": items,
        "total": len(items),
    })


# ── DB Persistence ────────────────────────────────────────────────────────────

def _persist_verification(result: Module6VerificationBundleV1):
    """Persist verification result to SQLite."""
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS verification_results (
                vessel_id TEXT,
                case_id TEXT,
                ais_state TEXT,
                integrity_score REAL,
                integrity_interval_lo REAL,
                integrity_interval_hi REAL,
                concealment_likelihood REAL,
                review_priority REAL,
                anomaly_count INTEGER,
                module6_version TEXT,
                ledger_hash TEXT,
                generated_at TEXT,
                bundle_json TEXT,
                PRIMARY KEY (vessel_id, case_id)
            )
        """)

        bundle_json = json.dumps(result.model_dump(), default=str)

        cur.execute("""
            INSERT OR REPLACE INTO verification_results
            (vessel_id, case_id, ais_state, integrity_score,
             integrity_interval_lo, integrity_interval_hi,
             concealment_likelihood, review_priority, anomaly_count,
             module6_version, ledger_hash, generated_at, bundle_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.vessel_id, result.case_id, result.ais_state.value,
            result.integrity_score,
            result.integrity_interval[0], result.integrity_interval[1],
            result.concealment_pattern_likelihood, result.review_priority,
            len(result.anomaly_classifications),
            result.module6_version, result.ledger_hash,
            result.generated_at, bundle_json,
        ))

        con.commit()
        con.close()
    except Exception as ex:
        print(f"[Verification API] Warning: SQLite persist encountered: {ex}")


def _persist_analyst_label(label: AnalystLabel):
    """Persist analyst label to SQLite."""
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

        cur.execute("""
            INSERT INTO analyst_labels (vessel_id, case_id, label, note, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (label.vessel_id, label.case_id, label.label, label.note, label.timestamp))

        con.commit()
        con.close()
    except Exception as ex:
        print(f"[Verification API] Warning: SQLite label persist encountered: {ex}")
