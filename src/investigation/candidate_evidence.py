"""
Module 8 — Candidate Evidence Assembler

Synthesizes Temporal, Spatial, AIS, and Physical evidence for a single candidate vessel,
applying rules from contradiction analysis to determine the final evidence state.
"""

from typing import List, Optional

from src.investigation.contradiction_analysis import find_contradictions
from src.investigation.schemas import (
    AISEvidence,
    CandidateEvidence,
    ContradictionEvidence,
    EvidenceState,
    PhysicalEvidence,
    SpatialEvidence,
    TemporalEvidence,
    TemporalOverlap,
)


def _find_supports(
    spatial: SpatialEvidence,
    temporal: TemporalEvidence,
    physical: Optional[PhysicalEvidence],
) -> List[str]:
    supports = []
    
    if temporal.overlap_status == TemporalOverlap.TEMPORAL_OVERLAP:
        supports.append("Vessel track completely overlaps the estimated release window.")
    elif temporal.overlap_status == TemporalOverlap.PARTIAL_TEMPORAL_OVERLAP:
        supports.append("Vessel track partially overlaps the estimated release window.")
        
    if spatial.intersects_origin_zone:
        supports.append("Vessel was physically present inside the estimated source zone.")
        
    if physical is not None:
        if physical.candidate_exceeds_baseline_p95:
            supports.append(
                "Counterfactual simulation footprint is spatially consistent with the observed "
                f"spill (IoU {physical.iou:.3f}) and outperforms 95% of baseline origin-zone samples."
            )
        elif physical.iou > 0.1:
            supports.append(
                f"Counterfactual simulation footprint matches the observed spill (IoU {physical.iou:.3f})."
            )
            
    return supports


def assemble_candidate_evidence(
    vessel_id: str,
    spatial: SpatialEvidence,
    temporal: TemporalEvidence,
    ais: AISEvidence,
    physical: Optional[PhysicalEvidence],
) -> CandidateEvidence:
    """
    Combines all evidence dimensions to yield the final CandidateEvidence.
    """
    contradictions = find_contradictions(spatial, temporal, ais, physical)
    supports = _find_supports(spatial, temporal, physical)
    
    # Logic for determining status
    if len(contradictions) > 0:
        status = EvidenceState.CONTRADICTED
        reasoning = "Evidence contradicts this hypothesis."
    elif physical is None:
        status = EvidenceState.INSUFFICIENT_DATA
        reasoning = "Insufficient physical simulation data to evaluate consistency."
    elif physical.candidate_exceeds_baseline_p95 and spatial.intersects_origin_zone:
        status = EvidenceState.SUPPORTED
        reasoning = "Physical, temporal, and spatial evidence are consistent with this hypothesis."
    elif physical.iou > 0.05 or temporal.overlap_status != TemporalOverlap.NO_TEMPORAL_OVERLAP:
        status = EvidenceState.PARTIALLY_SUPPORTED
        reasoning = "Partial evidence supports this hypothesis, but significant uncertainties remain."
    else:
        status = EvidenceState.INSUFFICIENT_DATA
        reasoning = "Insufficient evidence to draw a conclusion."

    return CandidateEvidence(
        vessel_id=vessel_id,
        spatial_evidence=spatial,
        temporal_evidence=temporal,
        ais_evidence=ais,
        physical_evidence=physical,
        supporting_evidence=supports,
        contradicting_evidence=contradictions,
        status=status,
        reasoning=reasoning
    )
