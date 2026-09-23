/**
 * VesselTrackLayer — renders the historical AIS track for a selected vessel.
 *
 * Track segments are drawn from actual AIS observations.
 * AIS gaps (from M5 TrackBuilder) are rendered as dashed/orange segments
 * with an explicit "AIS GAP" label — never silently filled.
 *
 * M6 continuity classifications are preserved exactly as received from the backend.
 */
import { Polyline, CircleMarker, Tooltip } from 'react-leaflet';
import type { VesselTrack } from './VesselLayer';

const VESSEL_COLORS: Record<string, string> = {
  V001: '#00d4ff',
  V002: '#ffb800',
  V003: '#00ff88',
  V004: '#ff6b6b',
  V005: '#c084fc',
};

interface Props {
  track: VesselTrack;
  /** Limit track rendering to positions at or before this time. */
  upToTimestamp: Date;
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

export default function VesselTrackLayer({ track, upToTimestamp }: Props) {
  const color = VESSEL_COLORS[track.vessel_id] || '#7ba7c0';
  const cutoffMs = upToTimestamp.getTime();

  // Observed positions up to the current playback time
  const visiblePings = track.positions.filter(
    p => new Date(p.timestamp).getTime() <= cutoffMs
  );

  if (visiblePings.length === 0) return null;

  // Build observed line segments (split around gaps)
  // A segment is a consecutive run of pings with no AIS gap between them.
  const observedSegments: [number, number][][] = [];
  let currentSegment: [number, number][] = [];

  for (let i = 0; i < visiblePings.length; i++) {
    const ping = visiblePings[i];
    // Check if there is a gap before this ping
    if (i > 0) {
      const prevPing = visiblePings[i - 1];
      const isGap = track.gaps.some(g => {
        const gs = new Date(g.gap_start).getTime();
        const ge = new Date(g.gap_end).getTime();
        const prevTs = new Date(prevPing.timestamp).getTime();
        const curTs = new Date(ping.timestamp).getTime();
        return Math.abs(gs - prevTs) < 60000 && Math.abs(ge - curTs) < 60000;
      });

      if (isGap) {
        // End current segment, start new one
        if (currentSegment.length > 0) {
          observedSegments.push(currentSegment);
        }
        currentSegment = [];
      }
    }
    currentSegment.push([ping.lat, ping.lon]);
  }
  if (currentSegment.length > 0) {
    observedSegments.push(currentSegment);
  }

  // Visible gaps (only those whose gap_start is before cutoff)
  const visibleGaps: AisGap[] = track.gaps.filter(
    g => new Date(g.gap_start).getTime() <= cutoffMs
  );

  return (
    <>
      {/* Observed track segments — solid lines */}
      {observedSegments.map((seg, idx) => (
        seg.length > 1 && (
          <Polyline
            key={`obs-${track.vessel_id}-${idx}`}
            positions={seg}
            pathOptions={{
              color,
              weight: 2,
              opacity: 0.75,
              dashArray: undefined,
            }}
          />
        )
      ))}

      {/* AIS gap segments — dashed amber line, explicitly labelled */}
      {visibleGaps.map((gap, idx) => {
        const gapLine: [number, number][] = [
          [gap.start_lat, gap.start_lon],
          [gap.end_lat, gap.end_lon],
        ];
        const midLat = (gap.start_lat + gap.end_lat) / 2;
        const midLon = (gap.start_lon + gap.end_lon) / 2;
        return (
          <div key={`gap-${track.vessel_id}-${idx}`}>
            <Polyline
              positions={gapLine}
              pathOptions={{
                color: '#ffb800',
                weight: 2,
                opacity: 0.65,
                dashArray: '4 6',
              }}
            >
              <Tooltip sticky>
                <div style={{ fontFamily: 'monospace', fontSize: 11, color: '#ffb800', fontWeight: 700 }}>
                  AIS GAP<br />
                  <span style={{ fontWeight: 400, color: '#ccc', fontSize: 10 }}>
                    Duration: {gap.duration_minutes.toFixed(0)} min
                    {gap.implied_speed_knots > 0 && ` | Implied: ${gap.implied_speed_knots.toFixed(1)} kn`}
                  </span>
                </div>
              </Tooltip>
            </Polyline>
            {/* Gap midpoint marker */}
            <CircleMarker
              center={[midLat, midLon]}
              radius={4}
              pathOptions={{ color: '#ffb800', fillColor: '#ffb800', fillOpacity: 0.4, weight: 1.5 }}
            >
              <Tooltip permanent direction="top" offset={[0, -6]}>
                <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#ffb800', fontWeight: 700 }}>
                  AIS GAP
                </span>
              </Tooltip>
            </CircleMarker>
          </div>
        );
      })}

      {/* Observed ping dots along the track */}
      {visiblePings.filter((_, i) => i % 5 === 0).map((ping, idx) => (
        <CircleMarker
          key={`ping-${track.vessel_id}-${idx}`}
          center={[ping.lat, ping.lon]}
          radius={2}
          pathOptions={{ color, fillColor: color, fillOpacity: 0.6, weight: 0 }}
        />
      ))}
    </>
  );
}
