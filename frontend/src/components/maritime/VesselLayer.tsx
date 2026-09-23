/**
 * VesselLayer — renders all 5 vessels from the AIS test dataset as map markers.
 *
 * Position at each moment is determined by:
 *   1. Find the two chronologically adjacent AIS observations for the current timestamp.
 *   2. If the gap between those two observations exceeds the AIS gap threshold (flagged by M5),
 *      do NOT interpolate — instead display the last known position with an AIS GAP indicator.
 *   3. If no gap: linearly interpolate lat/lon between the two adjacent observations.
 *
 * No positions are fabricated. No movement is generated randomly.
 * Vessel tracks and gap metadata come exclusively from /api/cases/{caseId}/vessels/{id}/track.
 */
import { CircleMarker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { Marker } from 'react-leaflet';

// Color per vessel (not related to suspicion — just visual distinction)
const VESSEL_COLORS: Record<string, string> = {
  V001: '#00d4ff',
  V002: '#ffb800',
  V003: '#00ff88',
  V004: '#ff6b6b',
  V005: '#c084fc',
};

interface AisPing {
  timestamp: string;
  lat: number;
  lon: number;
  sog: number;
  cog: number;
  nav_status: number;
  physically_impossible: boolean;
}

interface AisGap {
  gap_start: string;
  gap_end: string;
  duration_minutes: number;
  start_lat: number;
  start_lon: number;
  end_lat: number;
  end_lon: number;
  implied_speed_knots: number;
}

export interface VesselTrack {
  vessel_id: string;
  vessel_name: string;
  mmsi: number;
  positions: AisPing[];
  gaps: AisGap[];
  journey?: {
    entry_gateway: string | null;
    exit_gateway: string | null;
    status: string | null;
    actual_duration_hours: number | null;
    expected_duration_hours: number | null;
    delay_hours: number | null;
  };
}

interface VesselState {
  lat: number;
  lon: number;
  sog: number;
  cog: number;
  isInGap: boolean;       // true = current timestamp falls inside an M5-detected AIS gap
  isStale: boolean;       // true = past last known AIS observation
}

/**
 * Determine vessel position at a given timestamp using actual AIS observations.
 * Gaps are respected: no interpolation across them.
 */
function getVesselStateAt(track: VesselTrack, currentMs: number): VesselState | null {
  const { positions, gaps } = track;
  if (!positions || positions.length === 0) return null;

  const firstMs = new Date(positions[0].timestamp).getTime();
  const lastMs = new Date(positions[positions.length - 1].timestamp).getTime();

  // Before vessel enters the dataset time range
  if (currentMs < firstMs) return null;

  // After last observation + 10 min grace
  if (currentMs > lastMs + 10 * 60 * 1000) return null;

  // Check if current timestamp falls inside any M5-detected AIS gap
  for (const gap of gaps) {
    const gapStart = new Date(gap.gap_start).getTime();
    const gapEnd = new Date(gap.gap_end).getTime();
    if (currentMs > gapStart && currentMs < gapEnd) {
      // Inside gap: show last known position before gap, with gap indicator
      return {
        lat: gap.start_lat,
        lon: gap.start_lon,
        sog: 0,
        cog: 0,
        isInGap: true,
        isStale: false,
      };
    }
  }

  // At or past final observed position
  if (currentMs >= lastMs) {
    const last = positions[positions.length - 1];
    return { lat: last.lat, lon: last.lon, sog: last.sog, cog: last.cog, isInGap: false, isStale: true };
  }

  // Interpolate strictly between two adjacent observed positions (no gap between them)
  for (let i = 0; i < positions.length - 1; i++) {
    const t0 = new Date(positions[i].timestamp).getTime();
    const t1 = new Date(positions[i + 1].timestamp).getTime();
    if (currentMs >= t0 && currentMs <= t1) {
      const dt = t1 - t0;
      const frac = dt > 0 ? (currentMs - t0) / dt : 0;
      return {
        lat: positions[i].lat + (positions[i + 1].lat - positions[i].lat) * frac,
        lon: positions[i].lon + (positions[i + 1].lon - positions[i].lon) * frac,
        sog: positions[i].sog + (positions[i + 1].sog - positions[i].sog) * frac,
        cog: positions[i].cog,
        isInGap: false,
        isStale: false,
      };
    }
  }

  // Fallback: last position
  const last = positions[positions.length - 1];
  return { lat: last.lat, lon: last.lon, sog: last.sog, cog: last.cog, isInGap: false, isStale: true };
}

interface Props {
  tracks: VesselTrack[];
  currentTimestamp: Date;
  selectedVesselId: string | null;
  onSelectVessel: (vesselId: string | null) => void;
}

export default function VesselLayer({ tracks, currentTimestamp, selectedVesselId, onSelectVessel }: Props) {
  const currentMs = currentTimestamp.getTime();

  return (
    <>
      {tracks.map(track => {
        const state = getVesselStateAt(track, currentMs);
        if (!state) return null;

        const color = VESSEL_COLORS[track.vessel_id] || '#7ba7c0';
        const isSelected = track.vessel_id === selectedVesselId;

        return (
          <div key={track.vessel_id}>
            {/* Selection ring */}
            {isSelected && (
              <CircleMarker
                center={[state.lat, state.lon]}
                radius={16}
                pathOptions={{ color, fillColor: 'transparent', weight: 2, dashArray: '3 3' }}
              />
            )}

            {/* AIS gap warning ring */}
            {state.isInGap && (
              <CircleMarker
                center={[state.lat, state.lon]}
                radius={12}
                pathOptions={{ color: '#ffb800', fillColor: 'transparent', weight: 2, dashArray: '2 4', opacity: 0.8 }}
              />
            )}

            {/* Vessel position marker */}
            <Marker
              position={[state.lat, state.lon]}
              icon={L.divIcon({
                html: `<div style="
                  width: 10px; height: 10px; border-radius: 50%;
                  background: ${state.isInGap ? '#ffb800' : color};
                  border: 2px solid ${state.isInGap ? '#fff8' : '#fff5'};
                  box-shadow: 0 0 ${isSelected ? 8 : 4}px ${color};
                  cursor: pointer;
                "></div>`,
                className: '',
                iconSize: [10, 10],
                iconAnchor: [5, 5],
              })}
              eventHandlers={{
                click: () => onSelectVessel(isSelected ? null : track.vessel_id),
              }}
            >
              <Popup>
                <div style={{ fontFamily: 'monospace', fontSize: 12, minWidth: 180 }}>
                  <div style={{ fontWeight: 700, color, marginBottom: 6 }}>
                    {track.vessel_id} — {track.vessel_name}
                  </div>
                  <div style={{ color: '#aaa', fontSize: 10, marginBottom: 4 }}>
                    DATA MODE: MVP / SYNTHETIC TEST DATA
                  </div>
                  {state.isInGap && (
                    <div style={{ background: 'rgba(255,184,0,0.15)', border: '1px solid #ffb800', borderRadius: 4, padding: '3px 6px', marginBottom: 6, fontSize: 10, color: '#ffb800', fontWeight: 600 }}>
                      AIS GAP — Last known position shown
                    </div>
                  )}
                  {state.isStale && (
                    <div style={{ background: 'rgba(120,120,120,0.15)', border: '1px solid #666', borderRadius: 4, padding: '3px 6px', marginBottom: 6, fontSize: 10, color: '#aaa' }}>
                      Track ended — last observed position
                    </div>
                  )}
                  <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr', gap: '2px 6px', fontSize: 11 }}>
                    <span style={{ color: '#888' }}>MMSI</span><span>{track.mmsi}</span>
                    <span style={{ color: '#888' }}>Speed</span><span>{state.sog.toFixed(1)} kn</span>
                    <span style={{ color: '#888' }}>Course</span><span>{state.cog.toFixed(0)}°</span>
                    <span style={{ color: '#888' }}>Lat</span><span>{state.lat.toFixed(4)}°N</span>
                    <span style={{ color: '#888' }}>Lon</span><span>{state.lon.toFixed(4)}°E</span>
                    {track.journey?.entry_gateway && (
                      <><span style={{ color: '#888' }}>Entry</span><span>{track.journey.entry_gateway}</span></>
                    )}
                    {track.journey?.exit_gateway && (
                      <><span style={{ color: '#888' }}>Exit</span><span>{track.journey.exit_gateway}</span></>
                    )}
                  </div>
                </div>
              </Popup>
            </Marker>

            {/* Vessel label */}
            <Marker
              position={[state.lat + 0.07, state.lon]}
              icon={L.divIcon({
                html: `<div style="
                  font-family: 'JetBrains Mono', monospace;
                  font-size: 9px; font-weight: 700;
                  color: ${state.isInGap ? '#ffb800' : color};
                  text-shadow: 0 1px 3px #000c;
                  white-space: nowrap;
                  pointer-events: none;
                ">${track.vessel_id}${state.isInGap ? ' ⚠' : ''}</div>`,
                className: '',
                iconSize: [60, 14],
                iconAnchor: [30, 7],
              })}
            />
          </div>
        );
      })}
    </>
  );
}
