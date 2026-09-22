/**
 * investigation.ts — TypeScript types mirroring Modules 1–8 Python schemas.
 * Do NOT invent fields. All fields map 1-to-1 with the Python Pydantic models.
 */

// ── Module 1/2 ────────────────────────────────────────────────────────────────

export interface SpillBbox {
  lat_min: number;
  lat_max: number;
  lon_min: number;
  lon_max: number;
}

export interface CaseConfig {
  id: string;
  title: string;
  description: string;
  spill_center: { lat: number; lon: number };
  spill_bbox: SpillBbox;
  sar_timestamp: string;
  release_window_hours: number;
}

export interface LookAlikeResult {
  spill_mean_intensity: number;
  background_mean_intensity: number;
  contrast_ratio: number;
  passed: boolean;
  interpretation: string;
  caveat: string;
}

export interface SpillGeometry {
  spill_pixels: number;
  area_km2: number;
  area_caveat: string;
  centroid_pixel: { x: number; y: number };
  centroid_geo: { latitude: number; longitude: number };
  orientation_deg: number;
  major_axis_km: number;
  minor_axis_km: number;
}

export interface GeometryResult {
  case_id: string;
  look_alike: LookAlikeResult;
  geometry: SpillGeometry;
}

// ── Module 4 ──────────────────────────────────────────────────────────────────

export interface SpillSplitHypothesis {
  bic: number;
  iou: number;
}

export interface SourceZone {
  latitude: number;
  longitude: number;
}

export interface StabilityAnalysis {
  score: number;
  n_bootstrap_runs: number;
  variation_km: number;
}

export interface SpillSplitResult {
  case_id: string;
  result: string;
  one_source: SpillSplitHypothesis;
  two_source: SpillSplitHypothesis;
  source_zones: SourceZone[];
  source_separation_km: number;
  stability: StabilityAnalysis;
}

// ── Module 5 (AIS) ────────────────────────────────────────────────────────────

export type AisStatus =
  | 'NORMAL_TRANSIT'
  | 'AIS_GAP_DARK'
  | 'REPORTING_ANOMALY'
  | 'AMBIGUOUS'
  | 'INSUFFICIENT_DATA';

export interface VesselSummary {
  vessel_id: string;
  vessel_name: string;
  mmsi: number;
  sog: number;
  cog: number;
  nav_status_label: string;
  status: AisStatus;
}

export interface AisPing {
  timestamp: string;
  lat: number;
  lon: number;
  sog: number;
  cog: number;
}

export interface AisGapSegment {
  start_lat: number;
  start_lon: number;
  end_lat: number;
  end_lon: number;
  duration_minutes: number;
}

export interface VesselTrack {
  vessel_id: string;
  vessel_name: string;
  pings: AisPing[];
  gaps: AisGapSegment[];
}

export interface VesselJourney {
  distance_km: number;
  actual_duration_h: number;
}

export interface TransitAnalysis {
  expected_duration_h: number;
  delay_h: number;
}

export interface VesselJourneyData {
  journey: VesselJourney;
  transit: TransitAnalysis;
}

// ── Module 7 (Counterfactual) ─────────────────────────────────────────────────

export interface SensitivityPoint {
  offset_hours: number;
  iou: number;
  centroid_distance_km: number;
  area_ratio: number;
}

export interface CounterfactualResult {
  vessel_id: string;
  case_id: string;
  sensitivity_curve: SensitivityPoint[];
  best_iou: number;
  best_offset_hours: number;
  physically_consistent: boolean;
}

// ── Module 8 (Evidence Fusion) ────────────────────────────────────────────────

/** Evidence state — ONLY four allowed values. Never CULPRIT/GUILTY/etc. */
export type EvidenceState =
  | 'SUPPORTED'
  | 'PARTIALLY_SUPPORTED'
  | 'CONTRADICTED'
  | 'INSUFFICIENT_DATA';

export interface SpatialEvidence {
  intersects_source_zone: boolean;
  closest_approach_km: number | null;
}

export interface TemporalEvidence {
  within_release_window: boolean;
  overlap_minutes: number | null;
}

export interface AisEvidence {
  ais_status: AisStatus;
  gap_count: number;
  total_gap_minutes: number;
}

export interface PhysicalEvidence {
  iou: number | null;
  centroid_distance_km: number | null;
  area_ratio: number | null;
  shape_score: number | null;
  physically_consistent: boolean | null;
}

export interface Contradiction {
  type: string;
  description: string;
}

export interface CandidateVesselEvidence {
  vessel_id: string;
  status: EvidenceState;
  spatial_evidence: SpatialEvidence;
  temporal_evidence: TemporalEvidence;
  ais_evidence: AisEvidence;
  physical_evidence: PhysicalEvidence;
  contradictions: Contradiction[];
}

export interface InvestigationReportBundle {
  case_id: string;
  run_id: string;
  sar_observation: Record<string, unknown>;
  source_zone: Record<string, unknown>;
  candidate_vessels: CandidateVesselEvidence[];
  is_synthetic: boolean;
  synthetic_disclaimer?: string;
  generated_at: string;
}

// ── Evidence Graph ─────────────────────────────────────────────────────────────

export interface GraphNode {
  id: string;
  label: string;
  type: 'observation' | 'geometry' | 'analysis' | 'vessel' | 'data' | 'evidence';
  status?: EvidenceState;
  data?: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface EvidenceGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// ── App State ─────────────────────────────────────────────────────────────────

export type ViewId =
  | 'monitoring'
  | 'maritime'
  | 'spill'
  | 'spillsplit'
  | 'drift'
  | 'investigation'
  | 'replay'
  | 'report';

export type CaseId = 'case_01' | 'case_02' | 'case_03' | 'all';
