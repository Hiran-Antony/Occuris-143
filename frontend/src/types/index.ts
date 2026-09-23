export interface Vessel {
  mmsi: string;
  vessel_type: 'tanker' | 'cargo' | 'fishing' | 'passenger' | 'unknown';
  name: string | null;
  flag: string | null;
  journey: Journey | null;
  behaviour_event_count: number;
  unexplained_event_count: number;
}

export interface SpillIncident {
  id: number;
  detected_at: string;
  acquisition_time: string;
  sar_confidence: number;
  look_alike_passed: boolean;
  sar_image_path?: string;
  mask_path?: string;
  status: string;
  look_alike_checks: {
    wind_check: boolean;
    shape_check: boolean;
    size_check: boolean;
  };
  geometry: {
    centroid_lat: number;
    centroid_lon: number;
    area_km2: number;
    length_km: number;
    width_km: number;
    orientation_deg: number;
    pixel_count: number;
  };
  origin: {
    lat: number;
    lon: number;
    radius_km: number;
    release_start: string;
    release_end: string;
  };
  spillsplit: {
    hypothesis: string;
    source_count: number;
    delta_bic: number;
    zones: number[][];
  };
  forward_drift: {
    t1h: number[][];
    t3h: number[][];
    t6h: number[][];
  };
}

export interface Suspect {
  mmsi: string;
  vessel_name: string;
  min_distance_km: number;
  match_score: number;
  priority: string;
  reasons: string[];
  event_count: number;
}

export interface AISPosition {
  id: number;
  mmsi: string;
  timestamp: string;
  latitude: number;
  longitude: number;
  speed: number;
  course: number;
  heading: number | null;
  nav_status: string | null;
  inside_region: boolean;
  flagged: boolean;
  flag_reason: string | null;
}

export interface GatewayCrossing {
  id: number;
  mmsi: string;
  gateway_id: string;
  gateway_name: string;
  timestamp: string;
  direction: 'entering' | 'exiting';
  latitude: number | null;
  longitude: number | null;
}

export interface Journey {
  id: number;
  mmsi: string;
  entry_gateway: string | null;
  entry_time: string | null;
  exit_gateway: string | null;
  exit_time: string | null;
  route_distance_nm: number | null;
  expected_duration_hours: number | null;
  actual_duration_hours: number | null;
  delay_hours: number | null;
  status: 'in_progress' | 'completed' | 'incomplete';
}

export interface BehaviourEvent {
  id: number;
  mmsi: string;
  start_time: string;
  end_time: string | null;
  event_type: string;
  severity: 'low' | 'medium' | 'high';
  latitude: number | null;
  longitude: number | null;
  description: string | null;
  explanation: string | null;
  is_explained: boolean;
}

export interface TimelineEvent {
  time: string;
  end_time?: string;
  type: 'gateway_crossing' | 'behaviour_event';
  label: string;
  gateway_id?: string;
  direction?: string;
  event_type?: string;
  severity?: string;
  is_explained?: boolean;
  explanation?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

export interface DashboardStats {
  total_vessels: number;
  vessels_ever_in_region: number;
  total_gateway_crossings: number;
  total_behaviour_events: number;
  unexplained_events: number;
  completed_journeys: number;
}

export interface VesselTrack {
  mmsi: string;
  positions: AISPosition[];
  geojson: {
    type: 'Feature';
    geometry: { type: 'LineString'; coordinates: [number, number][] };
    properties: { mmsi: string };
  };
}

export type GatewayId = 'A' | 'B' | 'C' | 'D';

export const GATEWAY_COLORS: Record<GatewayId, string> = {
  A: '#00ff88',
  B: '#00d4ff',
  C: '#ffb800',
  D: '#ff6b35',
};

export const VESSEL_TYPE_COLORS: Record<string, string> = {
  tanker:    '#ff6b35',
  cargo:     '#00d4ff',
  fishing:   '#00ff88',
  passenger: '#c77dff',
  unknown:   '#7ba7c0',
};

export const SEVERITY_COLORS = {
  low:    '#ffb800',
  medium: '#ff8800',
  high:   '#ff3366',
};
