/**
 * maritimeApi.ts — Wrapper for the FastAPI maritime endpoints.
 * These correspond to the routes in src/api/maritime.py and maritime_router.py.
 */
import type {
  VesselSummary,
  VesselTrack,
  VesselJourneyData,
} from '../types/investigation';

const BASE = '';  // same-origin; Vite proxies /api to FastAPI backend

export type AisBehaviour = Record<string, { status: string }>;

export interface SourceInfo {
  mode: string;
  label?: string;
  record_count?: number;
  current_time?: string;
}

export interface GatewayEvent {
  vessel_id: string;
  vessel_name: string;
  gateway_id: string;
  event_type: 'ENTRY' | 'EXIT';
  timestamp: string;
  lat: number;
  lon: number;
  speed: number;
  course: number;
}

export interface GatewayFeature {
  type: 'Feature';
  geometry: { type: 'LineString'; coordinates: [number, number][] };
  properties: { gateway_id: string; name: string; color: string };
}

async function safeFetch<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return res.json() as Promise<T>;
  } catch {
    return null;
  }
}

export async function fetchVessels(): Promise<VesselSummary[]> {
  return (await safeFetch<VesselSummary[]>(`${BASE}/api/maritime/vessels`)) ?? [];
}

export async function fetchGatewayEvents(): Promise<GatewayEvent[]> {
  return (await safeFetch<GatewayEvent[]>(`${BASE}/api/maritime/gateway-events`)) ?? [];
}

export async function fetchVesselTrack(vesselId: string): Promise<VesselTrack | null> {
  return safeFetch<VesselTrack>(`${BASE}/api/maritime/vessels/${vesselId}/track`);
}

export async function fetchVesselJourney(vesselId: string): Promise<VesselJourneyData | null> {
  return safeFetch<VesselJourneyData>(`${BASE}/api/maritime/vessels/${vesselId}/journey`);
}

export async function fetchBehaviour(): Promise<AisBehaviour> {
  return (await safeFetch<AisBehaviour>(`${BASE}/api/maritime/behaviour`)) ?? {};
}

export async function fetchSourceInfo(): Promise<SourceInfo | null> {
  return safeFetch<SourceInfo>(`${BASE}/api/maritime/source-info`);
}

export async function fetchGateways(): Promise<GatewayFeature[]> {
  const data = await safeFetch<{ features: GatewayFeature[] }>(`${BASE}/api/gateways`);
  return data?.features ?? [];
}
