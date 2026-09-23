/**
 * Gateway API client
 * Talks to:
 *   GET  /api/gateways            → GeoJSON FeatureCollection
 *   GET  /api/gateways/crossings  → crossing log
 *   POST /api/ais/positions       → ingest AIS position
 */

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface GatewayFeature {
  type: 'Feature';
  properties: {
    id: string;
    name: string;
    color: string;
    description: string | null;
  };
  geometry: {
    type: 'LineString';
    coordinates: [number, number][];  // [lon, lat]
  };
}

export interface GatewayCollection {
  type: 'FeatureCollection';
  features: GatewayFeature[];
}

export interface GatewayCrossing {
  id: number;
  mmsi: string;
  gateway_id: string;
  gateway_name: string | null;
  timestamp: string;         // ISO-8601
  direction: 'entering' | 'exiting' | string;
  latitude: number | null;
  longitude: number | null;
}

export interface CrossingsResponse {
  total: number;
  crossings: GatewayCrossing[];
}

export interface AISPositionIn {
  mmsi: string;
  timestamp: string;         // ISO-8601 UTC
  latitude: number;
  longitude: number;
  sog?: number;
  cog?: number;
  heading?: number | null;
}

export interface AISPositionResponse {
  status: string;
  mmsi: string;
  position_id: number;
  crossings_detected: string[];
  message: string;
}

// ── API calls ─────────────────────────────────────────────────────────────────

/** Fetch all four demo gateways as a GeoJSON FeatureCollection. */
export async function fetchGateways(): Promise<GatewayCollection> {
  const res = await fetch(`${BASE}/api/gateways`);
  if (!res.ok) throw new Error(`fetchGateways: ${res.status}`);
  return res.json();
}

/** Fetch gateway crossing events with optional filters. */
export async function fetchCrossings(params?: {
  mmsi?: string;
  gateway_id?: string;
  limit?: number;
}): Promise<CrossingsResponse> {
  const qs = new URLSearchParams();
  if (params?.mmsi)       qs.set('mmsi',       params.mmsi);
  if (params?.gateway_id) qs.set('gateway_id', params.gateway_id);
  if (params?.limit)      qs.set('limit',      String(params.limit));

  const res = await fetch(`${BASE}/api/gateways/crossings?${qs}`);
  if (!res.ok) throw new Error(`fetchCrossings: ${res.status}`);
  return res.json();
}

/** Post a single real-time AIS position update. */
export async function postAISPosition(
  payload: AISPositionIn,
): Promise<AISPositionResponse> {
  const res = await fetch(`${BASE}/api/ais/positions`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail ?? `postAISPosition: ${res.status}`);
  }
  return res.json();
}
