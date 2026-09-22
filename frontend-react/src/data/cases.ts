/**
 * cases.ts — Authoritative case data derived from src/config.py (CASES dict).
 * Bounding boxes are the SINGLE source of truth for georeferencing,
 * matching the GeoTransform class used by Modules 2, 3, and 4.
 *
 * Do NOT create a separate pixel transform in the frontend.
 * The spill_bbox fields here come directly from config.py.
 */
import type { CaseConfig } from '../types/investigation';

export const CASES: Record<string, CaseConfig> = {
  case_01: {
    id: 'case_01',
    title: 'Case 01 — Al-Mahra Corridor Spill',
    description: 'Suspected discharge in international shipping lane east of Yemen',
    spill_center: { lat: 14.8, lon: 53.1 },
    // Authoritative bbox from src/config.py — used by GeoTransform in Modules 2/3/4
    spill_bbox: { lat_min: 14.0, lat_max: 15.6, lon_min: 52.2, lon_max: 54.0 },
    sar_timestamp: '2024-03-15T06:30:00Z',
    release_window_hours: 24,
  },
  case_02: {
    id: 'case_02',
    title: 'Case 02 — Lakshadweep Passage Spill',
    description: 'Dark vessel activity suspected near Lakshadweep Sea tanker route',
    spill_center: { lat: 17.5, lon: 69.2 },
    spill_bbox: { lat_min: 16.8, lat_max: 18.2, lon_min: 68.4, lon_max: 70.0 },
    sar_timestamp: '2024-04-02T09:15:00Z',
    release_window_hours: 18,
  },
  case_03: {
    id: 'case_03',
    title: 'Case 03 — Oman Basin Spill',
    description: 'Multi-source spill signature detected in Oman Basin transit zone',
    spill_center: { lat: 21.3, lon: 61.8 },
    spill_bbox: { lat_min: 20.5, lat_max: 22.1, lon_min: 61.0, lon_max: 62.6 },
    sar_timestamp: '2024-04-18T04:45:00Z',
    release_window_hours: 30,
  },
};

export const CASE_LIST = Object.values(CASES);

/** Visual colors for each case on the map (matching original app.js). */
export const CASE_COLORS: Record<string, string> = {
  case_01: '#ff5252',
  case_02: '#ff6b35',
  case_03: '#ffd740',
};

/** Arabian Sea region bbox from src/config.py ARABIAN_SEA_BBOX */
export const ARABIAN_SEA_BBOX = {
  lon_min: 58.0, lon_max: 75.0,
  lat_min: 14.0, lat_max: 25.0,
};

/** Default map center for Arabian Sea overview */
export const MAP_DEFAULT_CENTER: [number, number] = [62.0, 18.0]; // [lng, lat] for MapLibre
export const MAP_DEFAULT_ZOOM = 5;
