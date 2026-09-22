"""
Module 8 — Evidence Fusion & Investigation Data Contracts

All types consumed and emitted by Module 8 are defined here.
This schema strictly enforces forensic boundaries.
No 'culprit' or 'guilty' enum values exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


MODULE8_SCHEMA_VERSION = "1.0.0"


class EvidenceState(str, Enum):
    """The final evaluation state for a hypothesis against observed evidence."""
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class TemporalOverlap(str, Enum):
    TEMPORAL_OVERLAP = "TEMPORAL_OVERLAP"
    PARTIAL_TEMPORAL_OVERLAP = "PARTIAL_TEMPORAL_OVERLAP"
    NO_TEMPORAL_OVERLAP = "NO_TEMPORAL_OVERLAP"


@dataclass
class TemporalEvidence:
    """Answers: Was the vessel present during the release window?"""
    overlap_status: TemporalOverlap
    release_window_start_iso: str
    release_window_end_iso: str
    vessel_presence_start_iso: Optional[str]
    vessel_presence_end_iso: Optional[str]
    overlap_minutes: float


@dataclass
class SpatialEvidence:
    """Answers: Was the vessel physically near the estimated source zone?"""
    minimum_distance_to_origin_zone_km: float
    time_of_closest_approach_iso: Optional[str]
    intersects_origin_zone: bool


@dataclass
class AISEvidence:
    """Preserves Module 6 AIS status."""
    ais_status: str  # e.g. NORMAL, AIS_GAP_DARK, REPORTING_ANOMALY
    dark_path_hypotheses_evaluated: int
    data_quality_flags: List[str]


@dataclass
class PhysicalEvidence:
    """Module 7 counterfactual physical match results."""
    hypothesis_id: str
    release_time_iso: str
    release_location_lat: float
    release_location_lon: float
    release_source: str
    iou: float
    centroid_distance_km: float
    area_similarity: float
    shape_similarity: float
    orientation_similarity: float
    candidate_exceeds_baseline_p95: Optional[bool]
    time_sensitivity_best_offset_hours: Optional[float]


@dataclass
class ContradictionEvidence:
    """Describes explicitly contradicting evidence for a candidate."""
    category: str  # e.g., 'PHYSICS', 'KINEMATICS'
    description: str


@dataclass
class CandidateEvidence:
    """The synthesized evidence chain for a single candidate vessel."""
    vessel_id: str
    spatial_evidence: SpatialEvidence
    temporal_evidence: TemporalEvidence
    ais_evidence: AISEvidence
    physical_evidence: Optional[PhysicalEvidence]
    
    supporting_evidence: List[str]
    contradicting_evidence: List[ContradictionEvidence]
    
    status: EvidenceState
    reasoning: str


@dataclass
class DataProvenance:
    """Tracks the origin and integrity of the source datasets."""
    sar_dataset: Dict[str, str]
    ais_dataset: Dict[str, str]
    environment_dataset: Dict[str, str]
    is_synthetic: bool
    synthetic_disclaimer: Optional[str]


@dataclass
class InvestigationReportBundleV1:
    """
    Frozen output contract for Module 8.
    This is an auditable evidence chain, NOT a guilt determination.
    """
    schema_version: str
    incident_id: str
    run_id: str
    
    sar_observation: Dict[str, Any]
    source_zone: Dict[str, Any]
    release_window: Dict[str, str]
    
    candidate_vessels: List[CandidateEvidence]
    
    data_provenance: DataProvenance
    audit_ledger_reference: str
    limitations: List[str]
    
    generated_at: str
