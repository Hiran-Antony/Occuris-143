/**
 * mapConfig.ts — Authoritative MapLibre configuration.
 * Tile sources, map defaults, and georeferencing helpers.
 *
 * IMPORTANT: Do NOT transform pixel coordinates here.
 * The spill_bbox from cases.ts is the single source of truth.
 * Use the spill_bbox[lat_min/lat_max/lon_min/lon_max] to position image layers.
 */
import type { CaseConfig } from '../types/investigation';

export const TILE_SOURCES = {
  dark: 'https://{a|b|c|d}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
  satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  street: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
} as const;

export type MapStyle = keyof typeof TILE_SOURCES;

export const ARABIAN_SEA_CENTER: [number, number] = [62.0, 18.0]; // [lng, lat]
export const ARABIAN_SEA_ZOOM = 5;

export const VESSEL_COLORS: Record<string, string> = {
  V001: '#00e5ff',
  V002: '#ff5252',
  V003: '#ffd740',
  V004: '#00e676',
  V005: '#b388ff',
};

/**
 * Returns the MapLibre `coordinates` array for an image overlay.
 * Order: [top-left, top-right, bottom-right, bottom-left]
 * Using the authoritative spill_bbox from config.py/cases.ts.
 */
export function bboxToImageCoordinates(c: CaseConfig): [number, number][] {
  const { lat_min, lat_max, lon_min, lon_max } = c.spill_bbox;
  return [
    [lon_min, lat_max], // top-left
    [lon_max, lat_max], // top-right
    [lon_max, lat_min], // bottom-right
    [lon_min, lat_min], // bottom-left
  ];
}
