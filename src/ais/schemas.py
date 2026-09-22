"""
Module 5 — Maritime Memory & Virtual Gateways — Comprehensive Pydantic v2 Schemas
Covers Core AIS, Virtual Corridors, State-Machine Crossings, Transit Analyses,
Behavioral DNA, Collective Anomalies, Dark-Path Hypotheses, and Merkle Audit Anchors.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


# ── Enums ─────────────────────────────────────────────────────────────────────

class AisSourceMode(str, Enum):
    SYNTHETIC_REPLAY = "SYNTHETIC_REPLAY"
    LIVE_FEED = "LIVE_FEED"


# Backwards compatibility alias
AISSourceMode = AisSourceMode



class EventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    CORRIDOR_CROSSING = "CORRIDOR_CROSSING"


class JourneyStatus(str, Enum):
    COMPLETED = "COMPLETED"                    # Entry + Exit crossings detected
    IN_REGION = "IN_REGION"                    # Entered via gateway, has not exited yet
    ENTRY_ONLY_PARTIAL = "ENTRY_ONLY_PARTIAL"  # Data window ends while vessel is inside
    EXIT_ONLY_PARTIAL = "EXIT_ONLY_PARTIAL"    # Vessel was inside at data window start
    WINDOW_INTERIOR = "WINDOW_INTERIOR"        # All pings inside region, no boundary crossing


class ExpectedTimeBasis(str, Enum):
    HISTORICAL = "HISTORICAL"
    CORRIDOR_BASELINE = "CORRIDOR_BASELINE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


class BehaviourStatus(str, Enum):
    NORMAL_TRANSIT = "NORMAL_TRANSIT"
    EXPLAINED_DELAY = "EXPLAINED_DELAY"
    POTENTIAL_UNEXPLAINED_DELAY = "POTENTIAL_UNEXPLAINED_DELAY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class FactorSupportStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class TrafficLevel(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class AISContinuity(str, Enum):
    CONTINUOUS = "CONTINUOUS"
    GAP_DETECTED = "GAP_DETECTED"


class CollectiveAnomalyType(str, Enum):
    COORDINATED_DARK = "COORDINATED_DARK"
    RENDEZVOUS = "RENDEZVOUS"
    CONVERGENCE = "CONVERGENCE"


class JourneyStateMachineState(str, Enum):
    OUTSIDE = "OUTSIDE"
    ENTRY = "ENTRY"
    INSIDE = "INSIDE"
    EXIT = "EXIT"


# ── ITU-R M.1371 Navigational Status Mapping ───────────────────────────────────

NAV_STATUS_MAP = {
    0: "Under way using engine",
    1: "At anchor",
    2: "Not under command",
    3: "Restricted manoeuvrability",
    4: "Constrained by draught",
    5: "Moored",
    6: "Aground",
    7: "Engaged in fishing",
    8: "Under way sailing",
    9: "Reserved (HSC)",
    10: "Reserved (WIG)",
    11: "Power-driven vessel towing astern",
    12: "Power-driven vessel pushing ahead/alongside",
    13: "Reserved",
    14: "AIS-SART / MOB / EPIRB",
    15: "Undefined / default",
}

def nav_status_label(code: int) -> str:
    return NAV_STATUS_MAP.get(code, f"Unknown ({code})")


# ── Base Envelope ─────────────────────────────────────────────────────────────

class BaseEnvelope(BaseModel):
    """Base schema ensuring source-mode and UTC generation timestamps on all payloads."""
    source_mode: AisSourceMode = AisSourceMode.SYNTHETIC_REPLAY
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Core AIS Models ───────────────────────────────────────────────────────────

class AisPing(BaseModel):
    """Normalized, validated AIS ping."""
    mmsi: int
    vessel_id: str
    vessel_name: str = ""
    timestamp: datetime
    lat: float
    lon: float
    sog: float = 0.0          # Speed Over Ground in knots
    cog: float = 0.0          # Course Over Ground in degrees
    nav_status: int = 0
    source: str = "UNKNOWN"
    physically_impossible: bool = False

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if not -90.0 <= v <= 90.0:
            raise ValueError(f"Latitude {v} out of range [-90, 90]")
        return v

    @field_validator("lon")
    @classmethod
    def validate_lon(cls, v: float) -> float:
        if not -180.0 <= v <= 180.0:
            raise ValueError(f"Longitude {v} out of range [-180, 180]")
        return v

    @property
    def nav_status_label(self) -> str:
        return nav_status_label(self.nav_status)


# Backwards compatibility alias
AISRecord = AisPing


class AisGap(BaseModel):
    """Detected period of AIS reporting silence exceeding threshold."""
    vessel_id: str
    gap_start: datetime
    gap_end: datetime
    duration_minutes: float
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    implied_speed_knots: float = 0.0


# Backwards compatibility alias
AISGap = AisGap


class VesselTrack(BaseModel):
    """Chronological trajectory and detected coverage gaps for a vessel."""
    vessel_id: str
    vessel_name: str = ""
    mmsi: int = 0
    pings: List[AisPing] = []
    gaps: List[AisGap] = []
    total_distance_km: float = 0.0

    def __init__(self, **data: Any):
        continuity = data.pop("ais_continuity", None)
        super().__init__(**data)
        if continuity is not None:
            object.__setattr__(self, "_explicit_continuity", continuity)

    @property
    def ping_count(self) -> int:
        return len(self.pings)

    @property
    def ais_continuity(self) -> AISContinuity:
        if hasattr(self, "_explicit_continuity") and self._explicit_continuity is not None:
            return self._explicit_continuity
        return AISContinuity.GAP_DETECTED if self.gaps else AISContinuity.CONTINUOUS


# ── Gateway Corridor & Crossing Models ────────────────────────────────────────

class GatewayCorridor(BaseModel):
    """Narrow geofenced corridor polygon loaded from config/region.yaml."""
    gateway_id: str
    name: str
    orientation: str       # 'north' | 'south' | 'east' | 'west'
    entry_side: str
    exit_side: str
    geometry_geojson: Dict[str, Any]
    color: str = "#00e5ff"


# Backwards compatibility alias
GatewayDefinition = GatewayCorridor


class GatewayCrossingEvent(BaseModel):
    """Accurately interpolated gateway crossing event."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    vessel_id: str
    vessel_name: str = ""
    gateway_id: str
    event_type: EventType
    timestamp: datetime
    latitude: float
    longitude: float
    speed_knots: float = 0.0
    course_deg: float = 0.0
    interpolation_ratio: float = 0.0
    source: str = "AIS_PROCESSING"
    row_hash: Optional[str] = None
    prev_hash: Optional[str] = None

    # Aliases for frontend convenience
    @property
    def lat(self) -> float:
        return self.latitude

    @property
    def lon(self) -> float:
        return self.longitude

    @property
    def speed(self) -> float:
        return self.speed_knots

    @property
    def course(self) -> float:
        return self.course_deg


# ── Maritime Memory & Journey Models ──────────────────────────────────────────

class VesselJourney(BaseModel):
    """Unit of maritime memory for corridor transit."""
    journey_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    vessel_id: str
    vessel_name: str = ""
    entry_gateway: Optional[str] = None
    entry_time: Optional[datetime] = None
    exit_gateway: Optional[str] = None
    exit_time: Optional[datetime] = None
    distance_km: float = 0.0
    actual_duration_h: float = 0.0
    expected_duration_h: Optional[float] = None
    delay_h: Optional[float] = None
    z_score: Optional[float] = None
    average_speed_kn: Optional[float] = None
    max_observed_speed_kn: Optional[float] = None
    dominant_course_deg: Optional[float] = None
    expected_basis: ExpectedTimeBasis = ExpectedTimeBasis.INSUFFICIENT_HISTORY
    status: JourneyStatus = JourneyStatus.IN_REGION


class TransitAnalysis(BaseModel):
    """Transit delay calculation against prioritized baselines."""
    expected_duration_h: Optional[float] = None
    actual_duration_h: float
    delay_h: Optional[float] = None
    z_score: Optional[float] = None
    expected_basis: ExpectedTimeBasis
    reference_speed_kn: Optional[float] = None


# ── Behavior Audit & Explanation Models ───────────────────────────────────────

class ExplanationFactor(BaseModel):
    """Forensic factor test result."""
    factor: str           # 'TRAFFIC' | 'WEATHER' | 'AIS_GAP' | 'NAV_STATUS'
    status: FactorSupportStatus
    detail: str


# Backwards compatibility alias
DelayExplanation = ExplanationFactor



class BehaviourAssessment(BaseModel):
    """Synthesized multi-factor assessment with attached evidence."""
    vessel_id: str
    status: BehaviourStatus
    transit: Optional[TransitAnalysis] = None
    ais_continuity: AISContinuity = AISContinuity.CONTINUOUS
    nav_status_observed: str = "Under way using engine"
    explanations: List[ExplanationFactor] = []
    row_hash: Optional[str] = None


# ── Innovation A: Vessel Behavioral DNA Models ────────────────────────────────

class VesselBehavioralDNA(BaseModel):
    """Statistical kinematic signature of a vessel."""
    vessel_id: str
    feature_vector: Dict[str, float]  # speed_mean, speed_std, loiter_ratio, straightness, etc.
    speed_histogram: Dict[str, int] = {}
    covariance: Optional[List[List[float]]] = None
    sample_count: int
    confidence: float
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DnaMatch(BaseModel):
    """Kinematic behavioral similarity re-identification result."""
    vessel_id: str
    candidate_id: str
    confidence_pct: float
    mahalanobis_dist: float
    method: str = "MAHALANOBIS_DNA_RE_ID"  # full_cov | shrunk | diagonal
    sample_count: int = 0
    disclaimer: str = "behavioural similarity, not identity proof"

    @property
    def target_vessel_id(self) -> str:
        return self.candidate_id


# ── Innovation B: Collective Anomaly Models ───────────────────────────────────

class CollectiveAnomalyEvent(BaseModel):
    """Coordinated multi-vessel event detected across regional fleet."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    vessel_cluster: List[str]
    anomaly_type: CollectiveAnomalyType
    window_start: datetime
    window_end: datetime
    evidence: Dict[str, Any]


# ── Innovation C: Physics-Informed Dark-Path Models ───────────────────────────

class CandidateDarkPath(BaseModel):
    """Hypothetical trajectory connecting blackout endpoints."""
    path_type: str         # 'geodesic' | 'rhumb' | 'dna_prior' | 'current_assisted'
    coordinates: List[Tuple[float, float]] # [(lon, lat), ...]
    length_km: float
    implied_speed_knots: float
    feasible: bool
    probability: float
    intersects_origin: bool = False

    @property
    def waypoints(self) -> List[Tuple[float, float]]:
        return self.coordinates


class DarkPathHypothesis(BaseModel):
    """Physics-informed reconstruction of an AIS gap."""
    hypothesis_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    vessel_id: str
    gap_start: datetime
    gap_end: datetime
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    paths: List[CandidateDarkPath]
    intersects_origin: bool = False
    disclaimer: str = "HYPOTHESIS — reconstructed, not observed"

    @property
    def candidate_paths(self) -> List[CandidateDarkPath]:
        return self.paths


# ── Innovation D: Merkle Audit Models ─────────────────────────────────────────

class AuditAnchor(BaseModel):
    """Cryptographic Merkle checkpoint anchoring an event sequence."""
    anchor_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    merkle_root: str
    event_count: int
    window_start: datetime
    window_end: datetime
    external_tx_id: Optional[str] = None
    input_csv_hash: Optional[str] = None
    region_yaml_hash: Optional[str] = None
    pipeline_params_hash: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuditVerifyResult(BaseModel):
    """Chain and Merkle root verification outcome."""
    verified: bool
    total_events: int
    broken_chain_at: Optional[str] = None
    merkle_root_match: bool
    status: str       # 'VERIFY_SUCCESS' | 'VERIFY_FAILED'
    details: str


# ── Traffic Density Models ────────────────────────────────────────────────────

class TrafficDensityBin(BaseModel):
    """Corridor density calculation for a specific time window."""
    gateway_id: str
    window_start: datetime
    window_end: datetime
    vessel_count: int
    percentile_class: str   # 'HIGH' | 'NORMAL' | 'LOW'


# ── Replay Snapshot Model ─────────────────────────────────────────────────────

class ReplaySnapshot(BaseModel):
    """Synchronized maritime state snapshot at target replay timestamp."""
    time: datetime
    source_mode: AisSourceMode
    vessels: List[Dict[str, Any]]
    active_corridors: List[str]
    recent_crossings: List[GatewayCrossingEvent]
    active_anomalies: List[CollectiveAnomalyEvent]


# ── Evidence Bundle Contract (frozen; consumed by Modules 6/7/8) ──────────────

class EvidenceBundleV1(BaseModel):
    """
    Frozen downstream contract for Module 5 evidence.
    schema_version must be bumped on any breaking change.
    Modules 6, 7, 8 (and the future Module 8 OccurisBench) consume ONLY this schema.
    """
    schema_version: str = "1.0.0"
    case_id: str
    vessel_id: str
    journey: Optional[VesselJourney] = None
    ais_gaps: List[AisGap] = []
    transit_analysis: Optional[TransitAnalysis] = None
    behaviour_assessment: Optional[BehaviourAssessment] = None
    dna_profile_id: Optional[str] = None
    dna_best_match_confidence: Optional[float] = None
    dna_method: Optional[str] = None
    collective_anomaly_ids: List[str] = []
    dark_path_hypotheses: List[DarkPathHypothesis] = []
    latest_event_hash: Optional[str] = None
    source_mode: AisSourceMode = AisSourceMode.SYNTHETIC_REPLAY
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    module5_version: str = "5.1.0"


class RunManifest(BaseModel):
    """Deterministic build manifest for reproducibility auditing."""
    build_id: str
    input_csv_hash: str
    region_yaml_hash: str
    code_rev: str = "unknown"
    params_hash: str
    seed: int = 0
    built_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    output_hash: str = ""


class SourceInfo(BaseModel):
    """AIS Source status and metadata."""
    mode: Any
    current_time: Optional[str] = None
    total_pings: int
    active_vessels: int


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 6 — AIS Verification Engine — Frozen Schemas
# Consumed by Module 6 pipeline; snapshot-tested for contract stability.
# ══════════════════════════════════════════════════════════════════════════════

# ── Module 6 Enums ────────────────────────────────────────────────────────────

class VerificationStageStatus(str, Enum):
    """Completion status of each verification stage."""
    PASSED = "PASSED"
    FLAGGED = "FLAGGED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class AnomalyClassification(str, Enum):
    """Per-anomaly forensic classification. NEVER implies guilt or intent."""
    EXPLAINED = "EXPLAINED"
    UNEXPLAINED = "UNEXPLAINED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class KinematicFlag(str, Enum):
    """EKF-detected kinematic anomaly type."""
    TELEPORT_JUMP = "TELEPORT_JUMP"
    SPEED_IMPOSSIBLE = "SPEED_IMPOSSIBLE"
    COURSE_DISCONTINUITY = "COURSE_DISCONTINUITY"
    TURN_RATE_OUTLIER = "TURN_RATE_OUTLIER"


class AisState(str, Enum):
    """Per-vessel AIS record integrity state. REPORTING_ANOMALY displays as
    'possible spoofing / reporting anomaly — verification required'."""
    NORMAL = "NORMAL"
    AIS_GAP_DARK = "AIS_GAP_DARK"
    REPORTING_ANOMALY = "REPORTING_ANOMALY"
    AMBIGUOUS = "AMBIGUOUS"


class ReachabilityVerdict(str, Enum):
    """Physical reachability assessment between reported positions."""
    REACHABLE = "REACHABLE"
    POSSIBLY_REACHABLE = "POSSIBLY_REACHABLE"
    IMPLAUSIBLE = "IMPLAUSIBLE"


# ── Module 6 Input Contract ──────────────────────────────────────────────────

class CaseContextV1(BaseModel):
    """Investigation case context consumed by Module 6.
    Origin-zone data arrives ONLY via this contract — never via imports."""
    case_id: str
    origin_zones: List[Dict[str, Any]] = []       # GeoJSON polygon(s)
    release_window_start: datetime
    release_window_end: datetime
    sar_acquisition_time: Optional[datetime] = None
    source_mode: AisSourceMode = AisSourceMode.SYNTHETIC_REPLAY
    spill_center: Optional[Dict[str, float]] = None  # {lat, lon}


# ── Module 6 Stage Result Models ─────────────────────────────────────────────

class WindowResolution(BaseModel):
    """Stage 1: Investigation window resolved per-vessel."""
    vessel_id: str
    window_start: datetime
    window_end: datetime
    overlap_minutes: float
    vessel_present: bool
    origin_zone_ref: Optional[str] = None
    status: VerificationStageStatus = VerificationStageStatus.PASSED


class GapConcurrencyRecord(BaseModel):
    """Per-gap concurrency analysis: how many other vessels had overlapping gaps."""
    gap_start: datetime
    gap_end: datetime
    duration_minutes: float
    concurrent_vessel_count: int
    concurrent_vessel_ids: List[str] = []
    coverage_flag: bool = False


class ContinuityReport(BaseModel):
    """Stage 2: AIS continuity analysis with windowed statistics."""
    vessel_id: str
    total_gaps: int
    total_dark_minutes: float
    max_gap_minutes: float
    gap_concurrency_index: float        # Fraction of OTHER vessels with overlapping gaps
    gap_concurrency_records: List[GapConcurrencyRecord] = []
    coverage_support: bool = False      # True when ≥ coverage_min_vessels concurrent
    status: VerificationStageStatus = VerificationStageStatus.PASSED


class KinematicEvent(BaseModel):
    """Stage 3: Single EKF-detected kinematic anomaly event."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    vessel_id: str
    ping_index: int
    timestamp: datetime
    lat: float
    lon: float
    nis_value: float                    # Normalised Innovation Squared
    p_value: float                      # chi²(2) p-value
    flag: KinematicFlag
    implied_speed_kn: Optional[float] = None
    implied_course_change_deg: Optional[float] = None
    detail: str = ""


class KinematicEpisode(BaseModel):
    """Consecutive kinematic anomaly events forming an episode."""
    episode_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    vessel_id: str
    events: List[KinematicEvent] = []
    episode_type: KinematicFlag = KinematicFlag.TELEPORT_JUMP
    start_index: int = 0
    end_index: int = 0
    duration_minutes: float = 0.0


class IdentityConflict(BaseModel):
    """Same MMSI appearing at impossibly separated locations simultaneously."""
    vessel_id: str
    mmsi: int
    position_a: Dict[str, Any]        # {lat, lon, timestamp}
    position_b: Dict[str, Any]
    separation_km: float
    dt_minutes: float


class KinematicReport(BaseModel):
    """Stage 3: Full kinematic consistency report."""
    vessel_id: str
    total_pings_analyzed: int
    anomalous_pings: int
    episodes: List[KinematicEpisode] = []
    identity_conflicts: List[IdentityConflict] = []
    events: List[KinematicEvent] = []
    status: VerificationStageStatus = VerificationStageStatus.PASSED


class ReachabilityResult(BaseModel):
    """Stage 4: Physical reachability assessment."""
    vessel_id: str
    inter_ping_violations: int = 0
    round_trip_dark_checks: List[Dict[str, Any]] = []   # {gap_id, d1_km, d2_km, required_kn, limit_kn, margin_pct, verdict}
    overall_verdict: ReachabilityVerdict = ReachabilityVerdict.REACHABLE
    status: VerificationStageStatus = VerificationStageStatus.PASSED


class DarkPathValidationEntry(BaseModel):
    """Per-hypothesis dark-path validation result."""
    hypothesis_id: str
    valid: bool
    intersects_origin: bool
    implied_speed_kn: float
    probability: float
    notes: str = ""
    disclaimer: str = "HYPOTHESIS — reconstructed, not observed"


class DarkPathValidation(BaseModel):
    """Stage 5: Aggregate dark-path validation result."""
    vessel_id: str
    hypotheses_evaluated: int = 0
    entries: List[DarkPathValidationEntry] = []
    dark_path_support: bool = False     # Any feasible path intersects origin zone
    status: VerificationStageStatus = VerificationStageStatus.PASSED


class AnomalyState(BaseModel):
    """Per-anomaly classification with explanation."""
    anomaly_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    anomaly_type: str                   # 'AIS_GAP' | 'KINEMATIC_EPISODE' | 'IDENTITY_CONFLICT'
    classification: AnomalyClassification
    cause: Optional[str] = None         # Explanation cause when EXPLAINED
    explanation_distribution: Dict[str, float] = {}   # Softmax distribution over hypotheses
    detail: str = ""


# ── Module 6 Output Contract ─────────────────────────────────────────────────

class Module6VerificationBundleV1(BaseModel):
    """
    Frozen downstream contract for Module 6 verification results.
    Consumed by Modules 7/8 and future OccurisBench.
    schema_version must be bumped on any breaking change.

    FORENSIC BOUNDARY: This bundle NEVER contains guilt, causation, or intent.
    ais_state REPORTING_ANOMALY displays as:
        'possible spoofing / reporting anomaly — verification required'
    """
    schema_version: str = "1.0.0"
    case_id: str
    vessel_id: str
    module6_version: str = "6.0.0"

    # Stage results
    window: Optional[WindowResolution] = None
    continuity: Optional[ContinuityReport] = None
    kinematic: Optional[KinematicReport] = None
    reachability: Optional[ReachabilityResult] = None
    dark_path: Optional[DarkPathValidation] = None

    # Classifications
    anomaly_classifications: List[AnomalyState] = []
    ais_state: AisState = AisState.NORMAL

    # Integrity (Bayesian posterior)
    integrity_score: float = 0.9        # P(AIS reliable | evidence)
    integrity_interval: List[float] = [0.7, 0.95]  # [lower, upper] from sensitivity analysis
    integrity_method: str = "bayesian_odds_lr"

    # Concealment pattern (separate axis from integrity)
    concealment_pattern_likelihood: float = 0.0
    concealment_interval: List[float] = [0.0, 0.0]
    explanation_distribution: Dict[str, float] = {}

    # Review
    review_priority: float = 0.0       # Interval width; higher = more ambiguous

    # Provenance
    ledger_hash: Optional[str] = None
    source_mode: AisSourceMode = AisSourceMode.SYNTHETIC_REPLAY
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Analyst Label (storage-only, no ML feedback loop) ─────────────────────────

class AnalystLabel(BaseModel):
    """Human analyst label for review queue. STORAGE ONLY — no feedback into scoring."""
    vessel_id: str
    case_id: str
    label: str                          # INNOCENT_PATTERN | SUSPICIOUS_PATTERN | UNKNOWN
    note: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

