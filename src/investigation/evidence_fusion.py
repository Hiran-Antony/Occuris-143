"""
Module 8 — Evidence Fusion Orchestrator

Consumes Case Context, M5, M6, and M7 bundles to construct the full investigation picture.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.ais.schemas import EvidenceBundleV1, Module6VerificationBundleV1
from src.counterfactual.schemas import CounterfactualEvidenceBundleV1
from src.investigation.audit_linker import generate_audit_reference
from src.investigation.candidate_evidence import assemble_candidate_evidence
from src.investigation.provenance import build_provenance_record
from src.investigation.real_data_validator import validate_ais_integrity
from src.investigation.schemas import (
    AISEvidence,
    CandidateEvidence,
    InvestigationReportBundleV1,
    MODULE8_SCHEMA_VERSION,
    PhysicalEvidence,
)
from src.investigation.spatial_analysis import evaluate_spatial_evidence
from src.investigation.temporal_analysis import evaluate_temporal_evidence

# Mandatory limitations for all Occuris output
LIMITATIONS = [
    "Physical consistency does not establish causation.",
    "Occuris reconstructs physical consistency using SAR, AIS and ocean-atmospheric data, "
    "but does not prove that a vessel caused an oil spill from satellite imagery alone.",
    "Oil-like dark features can arise from natural phenomena and other substances.",
    "Environmental model uncertainties and AIS reconstruction errors remain."
]


def fuse_evidence(
    case_cfg: Dict[str, Any],
    run_id: str,
    m5_bundles: List[EvidenceBundleV1],
    m6_bundles: List[Module6VerificationBundleV1],
    m7_bundles: List[CounterfactualEvidenceBundleV1]
) -> InvestigationReportBundleV1:
    """
    Main entry point for Module 8.
    """
    
    # 1. Real Data Validation
    for m5 in m5_bundles:
        validate_ais_integrity(m5)
        
    m6_map = {b.vessel_id: b for b in m6_bundles}
    m7_map = {b.vessel_id: b for b in m7_bundles}
    
    candidates: List[CandidateEvidence] = []
    
    for m5 in m5_bundles:
        vid = m5.vessel_id
        m6 = m6_map.get(vid)
        m7 = m7_map.get(vid)
        
        # Assemble sub-evidences
        temporal = evaluate_temporal_evidence(case_cfg, m6)
        spatial = evaluate_spatial_evidence(m6)
        
        # Extract AIS Evidence
        if m6 and m6.dark_path:
            dp_eval = m6.dark_path.hypotheses_evaluated
        else:
            dp_eval = 0
            
        ais = AISEvidence(
            ais_status=m6.ais_state.value if m6 else "UNKNOWN",
            dark_path_hypotheses_evaluated=dp_eval,
            data_quality_flags=[]  # M6 doesn't have data_quality_flags field
        )
        
        # Extract Physical Evidence
        physical = None
        env_version = "UNKNOWN"
        if m7:
            env_version = m7.environment_version
            best = m7.best_hypothesis
            if best:
                physical = PhysicalEvidence(
                    hypothesis_id=best.hypothesis_id,
                    release_time_iso=best.release_time_iso,
                    release_location_lat=best.release_location.lat,
                    release_location_lon=best.release_location.lon,
                    release_source=best.release_location.source,
                    iou=best.physical_metrics.iou,
                    centroid_distance_km=best.physical_metrics.centroid_distance_km,
                    area_similarity=best.physical_metrics.area_similarity,
                    shape_similarity=best.physical_metrics.shape_similarity,
                    orientation_similarity=best.physical_metrics.orientation_similarity,
                    candidate_exceeds_baseline_p95=m7.candidate_exceeds_p95,
                    time_sensitivity_best_offset_hours=(
                        m7.time_sensitivity.best_offset_hours if m7.time_sensitivity else None
                    )
                )
        
        # Assemble Candidate
        cand = assemble_candidate_evidence(
            vessel_id=vid,
            spatial=spatial,
            temporal=temporal,
            ais=ais,
            physical=physical
        )
        candidates.append(cand)
        
    # Provenance
    provenance = build_provenance_record(case_cfg, env_version)
    
    # Bundle extraction
    import datetime as dt
    sar_time_iso = case_cfg["sar_timestamp"]
    t_sar = datetime.fromisoformat(sar_time_iso.replace("Z", "+00:00"))
    release_window_hours = case_cfg.get("release_window_hours", 24)
    t_window_start = t_sar - dt.timedelta(hours=release_window_hours)
    
    return InvestigationReportBundleV1(
        schema_version=MODULE8_SCHEMA_VERSION,
        incident_id=case_cfg["id"],
        run_id=run_id,
        sar_observation={
            "acquisition_time_iso": sar_time_iso,
            "detection_type": "Possible oil-like surface anomaly"
        },
        source_zone=case_cfg.get("spill_center", {}),
        release_window={
            "start_iso": t_window_start.isoformat(),
            "end_iso": sar_time_iso
        },
        candidate_vessels=candidates,
        data_provenance=provenance,
        audit_ledger_reference=generate_audit_reference(run_id),
        limitations=list(LIMITATIONS),
        generated_at=datetime.now(timezone.utc).isoformat()
    )
