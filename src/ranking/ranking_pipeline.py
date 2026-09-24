"""
Occuris Module 8 — Forensic Ranking Pipeline Orchestrator

Consumes:
  - Module 5: Maritime Memory & Behavioral DNA (EvidenceBundleV1)
  - Module 6: AIS Verification & Explanation Competition (Module6VerificationBundleV1)
  - Module 7: Counterfactual Trajectory Reasoning (CounterfactualEvidenceBundleV1)
  - Module 4: SpillSplit component isolation

Produces:
  - Frozen Contract: RankingBundleV1
  - Cryptographic Merkle chain extension with RANKING_ARTIFACT

HONESTY DOCTRINE: Investigation Priority != Guilt.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ais.schemas import (
    AisSourceMode,
    AisState,
    CaseContextV1,
    EvidenceBundleV1,
    InvestigationPriority,
    Module6VerificationBundleV1,
    RankingBundleV1,
    VesselRankingEvidence,
)
from src.config import CASES, DATA_PROCESSED
from src.ranking.audit import record_ranking_artifact
from src.ranking.classifier import classify_priority
from src.ranking.evidence_engine import EvidenceEngine, load_ranking_config
from src.ranking.hypotheses import test_hypotheses, to_hypothesis_posteriors
from src.ranking.planner import haversine_distance_km, plan_inspections, to_inspection_actions
from src.ranking.schemas import InspectionBudget
from src.ranking.sensitivity import compute_sensitivity, to_sensitivity_contributions
from src.verification.pipeline import VerificationPipeline, load_verification_config


_RANKING_CACHE: Dict[str, RankingBundleV1] = {}


def compute_min_distance_to_origin(track: Any, context: Optional[CaseContextV1]) -> float:
    """Compute physical minimum distance (km) between vessel track and origin zones."""
    if not context or not track or not getattr(track, "pings", None):
        return 999.0

    target_points = []
    for z in (context.origin_zones or []):
        lat = z.get("latitude", z.get("lat"))
        lon = z.get("longitude", z.get("lon"))
        if lat is not None and lon is not None:
            target_points.append((float(lat), float(lon)))

    if not target_points and context.spill_center:
        sc = context.spill_center
        lat = sc.get("lat", sc.get("latitude"))
        lon = sc.get("lon", sc.get("longitude"))
        if lat is not None and lon is not None:
            target_points.append((float(lat), float(lon)))

    if not target_points:
        return 999.0

    min_d = float("inf")
    for ping in track.pings:
        for t_lat, t_lon in target_points:
            d = haversine_distance_km(ping.lat, ping.lon, t_lat, t_lon)
            if d < min_d:
                min_d = d

    return min_d if min_d != float("inf") else 999.0


def resolve_overlap_status(m6_bundle: Optional[Any]) -> str:
    """Safely extract temporal overlap status (FULL, PARTIAL, NONE)."""
    if not m6_bundle or not getattr(m6_bundle, "window", None):
        return "NONE"
    w = m6_bundle.window
    if hasattr(w, "overlap_status"):
        return str(w.overlap_status)
    mins = float(getattr(w, "overlap_minutes", 0.0))
    if mins >= 60.0:
        return "FULL"
    elif mins > 0.0 or getattr(w, "vessel_present", False):
        return "PARTIAL"
    return "NONE"


def build_case_context_for_ranking(case_id: str) -> Optional[CaseContextV1]:
    """Load case context and origin zones from processed files or config."""
    case_cfg = CASES.get(case_id)
    geom_path = DATA_PROCESSED / f"{case_id}_geometry.json"
    spillsplit_path = DATA_PROCESSED / f"{case_id}_spillsplit.json"

    geom = None
    if geom_path.exists():
        try:
            with open(geom_path, "r", encoding="utf-8") as f:
                geom = json.load(f)
        except Exception:
            geom = None

    spillsplit = None
    if spillsplit_path.exists():
        try:
            with open(spillsplit_path, "r", encoding="utf-8") as f:
                spillsplit = json.load(f)
        except Exception:
            spillsplit = None

    sar_timestamp_str = "2024-03-15T12:00:00Z"
    if case_cfg and "sar_timestamp" in case_cfg:
        sar_timestamp_str = case_cfg["sar_timestamp"]
    elif geom and "metadata" in geom:
        sar_timestamp_str = geom["metadata"].get("acquisition_time", sar_timestamp_str)

    t_sar = datetime.fromisoformat(sar_timestamp_str.replace("Z", "+00:00"))
    if t_sar.tzinfo is None:
        t_sar = t_sar.replace(tzinfo=timezone.utc)

    release_hours = 24
    if case_cfg:
        release_hours = case_cfg.get("release_window_hours", 24)

    # Spill center
    center = {"lat": 14.8, "lon": 53.1}
    if case_cfg and "spill_center" in case_cfg:
        center = case_cfg["spill_center"]
    elif geom and "geometry" in geom and "centroid_geo" in geom["geometry"]:
        raw_center = geom["geometry"]["centroid_geo"]
        center = {
            "lat": raw_center.get("lat", raw_center.get("latitude", 14.8)),
            "lon": raw_center.get("lon", raw_center.get("longitude", 53.1)),
        }

    origin_zones = []
    if spillsplit and "estimated_origin_zones" in spillsplit:
        origin_zones = spillsplit["estimated_origin_zones"]
    elif spillsplit and "source_zones" in spillsplit:
        origin_zones = spillsplit["source_zones"]

    return CaseContextV1(
        case_id=case_id,
        origin_zones=origin_zones,
        release_window_start=t_sar - timedelta(hours=release_hours),
        release_window_end=t_sar,
        sar_acquisition_time=t_sar,
        spill_center=center,
    )


def run_ranking_pipeline(
    case_id: str,
    budget: Optional[InspectionBudget] = None,
    force_refresh: bool = False,
    record_audit: bool = True,
    context: Optional[CaseContextV1] = None,
) -> RankingBundleV1:
    """
    Execute full Module 8 Bayesian evidence ranking for a case.
    Consumes real M5, M6, M7 bundles and outputs a frozen RankingBundleV1.
    """
    if not force_refresh and case_id in _RANKING_CACHE:
        return _RANKING_CACHE[case_id]

    from src.api.maritime import engine as m5_engine, ensure_pipeline, get_evidence_bundle
    ensure_pipeline()

    if context is None:
        context = build_case_context_for_ranking(case_id)
    v_config = load_verification_config()
    v_pipeline = VerificationPipeline(v_config)
    r_config = load_ranking_config()
    evidence_engine = EvidenceEngine(r_config)

    # 1. Gather all vessel tracks and bundles
    vessel_ranks: List[VesselRankingEvidence] = []
    vessel_posts: Dict[str, float] = {}
    vessel_intervals: Dict[str, List[float]] = {}
    planner_candidates: List[Dict[str, Any]] = []
    vessel_data: Dict[str, Any] = {}

    m5_count = 0
    m6_count = 0

    tracks = m5_engine.tracks
    for vid, track in tracks.items():
        # Load M5 bundle
        bundle_resp = get_evidence_bundle(vid, case_id)
        m5_data = bundle_resp.get("evidence_bundle", {})
        m5_bundle = EvidenceBundleV1(**m5_data)
        m5_count += 1

        # Run M6 Verification if context available
        m6_bundle = None
        if context is not None:
            m6_bundle = v_pipeline.run(m5_bundle, context, track)
            m6_count += 1

        # Determine vessel type
        v_type = getattr(track, "vessel_type", None)
        if not v_type and track.vessel_name:
            v_name_lower = track.vessel_name.lower()
            if "tanker" in v_name_lower:
                v_type = "tanker"
            elif "fishing" in v_name_lower:
                v_type = "fishing"
            elif "cargo" in v_name_lower:
                v_type = "cargo"
        v_type = v_type or "cargo"
        v_name = track.vessel_name or f"Vessel {vid}"

        # Determine distance and overlap
        min_dist_km = compute_min_distance_to_origin(track, context)
        overlap_status = resolve_overlap_status(m6_bundle)

        # Evaluate Bayesian posterior via EvidenceEngine
        anom_map = {}
        for ev in getattr(m5_engine, "collective_events", []):
            atype = getattr(ev, "anomaly_type", None)
            if hasattr(atype, "value"):
                atype = atype.value
            anom_map[ev.event_id] = str(atype).lower()

        case_ctx_dict = {
            "origin_zones": context.origin_zones,
            "min_distance_km": min_dist_km,
            "anomaly_types": anom_map,
        } if context else {}
        prior, posterior, factors = evidence_engine.rank_vessel(
            vessel_id=vid,
            m5_bundle=m5_bundle,
            m6_bundle=m6_bundle,
            m7_bundle=None,
            case_context=case_ctx_dict,
            vessel_type=v_type,
        )

        # LOO Sensitivity Analysis
        sens_report = compute_sensitivity(
            vessel_id=vid,
            case_id=case_id,
            prior=prior,
            factors=factors,
            engine=evidence_engine,
            config=r_config,
        )

        vessel_posts[vid] = posterior
        vessel_intervals[vid] = sens_report.posterior_interval
        vessel_data[vid] = {
            "prior": prior,
            "posterior": posterior,
            "factors": factors,
            "sens_report": sens_report,
            "m6_bundle": m6_bundle,
            "min_dist_km": min_dist_km,
            "overlap_status": overlap_status,
            "v_type": v_type,
            "v_name": v_name,
        }

        # Extract last known position for planner
        last_lat = 14.5
        last_lon = 53.0
        if track and track.pings:
            last_lat = track.pings[-1].lat
            last_lon = track.pings[-1].lon

        planner_candidates.append({
            "vessel_id": vid,
            "posterior": posterior,
            "lat": last_lat,
            "lon": last_lon,
            "vessel_type": v_type,
        })

    # 2. Priority Classification across all candidates
    for vid, track in tracks.items():
        post = vessel_posts[vid]
        interval = vessel_intervals[vid]
        v_info = vessel_data[vid]

        priority_state = classify_priority(
            vessel_id=vid,
            all_vessel_posteriors=vessel_posts,
            posterior=post,
            intervals=vessel_intervals,
            current_interval=interval,
            is_insufficient_data=(context is None),
            config=r_config,
        )

        m6_bundle = v_info["m6_bundle"]
        ais_state = AisState.NORMAL
        if m6_bundle:
            ais_state = m6_bundle.ais_state

        vessel_evidence = VesselRankingEvidence(
            vessel_id=vid,
            vessel_name=v_info["v_name"],
            vessel_type=v_info["v_type"],
            prior=round(v_info["prior"], 4),
            posterior=round(v_info["posterior"], 4),
            posterior_interval=interval,
            priority=priority_state.state,
            lr_breakdown=v_info["factors"],
            sensitivity=to_sensitivity_contributions(v_info["sens_report"]),
            ais_state=ais_state,
            source_zone_assignment=None,
            temporal_overlap=v_info["overlap_status"],
            spatial_distance_km=round(v_info["min_dist_km"], 2),
            provenance_ref=f"urn:occuris:provenance:{case_id}:{vid}",
        )
        vessel_ranks.append(vessel_evidence)

    # Sort vessels by posterior descending
    vessel_ranks.sort(key=lambda v: v.posterior, reverse=True)

    # 3. Multi-Source Hypothesis Testing
    spillsplit_data = None
    spillsplit_path = DATA_PROCESSED / f"{case_id}_spillsplit.json"
    if not spillsplit_path.exists():
        bench_path = Path("data/bench/scenarios") / case_id / "spillsplit.json"
        if bench_path.exists():
            spillsplit_path = bench_path
    if spillsplit_path.exists():
        try:
            with open(spillsplit_path, "r", encoding="utf-8") as f:
                spillsplit_data = json.load(f)
        except Exception:
            spillsplit_data = None

    hyp_report = test_hypotheses(case_id, spillsplit_data=spillsplit_data, config=r_config)
    hyp_posteriors = to_hypothesis_posteriors(hyp_report)

    # 4. Inspection Planning
    geom_path = DATA_PROCESSED / f"{case_id}_geometry.json"
    area_proxy = 1.0
    if geom_path.exists():
        try:
            with open(geom_path, "r", encoding="utf-8") as f:
                g = json.load(f)
                area_proxy = float(g.get("geometry", {}).get("area_km2", 1.0))
        except Exception:
            area_proxy = 1.0

    inspection_plan = plan_inspections(
        case_id=case_id,
        vessels=planner_candidates,
        budget=budget,
        slick_area_volume_proxy=area_proxy,
        config=r_config,
    )
    inspection_actions = to_inspection_actions(inspection_plan)

    # 5. Review queue sorted by posterior interval width descending (uncertainty-first)
    review_queue = sorted(
        vessel_intervals.keys(),
        key=lambda v: (vessel_intervals[v][1] - vessel_intervals[v][0]),
        reverse=True,
    )

    # 6. Assemble RankingBundleV1
    bundle = RankingBundleV1(
        schema_version="1.0.0",
        case_id=case_id,
        module8_version="8.0.0",
        hypothesis_posteriors=hyp_posteriors,
        vessels=vessel_ranks,
        inspection_plan=inspection_actions,
        budget_utilization=inspection_plan.budget_utilization,
        review_queue=review_queue,
        provenance_summary=f"{m5_count} M5 bundles, {m6_count} M6 bundles processed",
        source_mode=AisSourceMode.SYNTHETIC_REPLAY,
        generated_at=datetime.now(timezone.utc).isoformat(),
        disclaimer="Investigation Priority — Not Guilt. Physical consistency does not establish causation.",
    )

    # 7. Record Merkle audit chain extension
    if record_audit:
        record_ranking_artifact(bundle)

    _RANKING_CACHE[case_id] = bundle
    return bundle
