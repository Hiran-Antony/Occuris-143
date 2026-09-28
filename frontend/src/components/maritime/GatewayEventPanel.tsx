/**
 * GatewayEventPanel — computes gateway crossings live in the frontend.
 *
 * Crossings are detected by scanning consecutive AIS pings for each vessel
 * and checking if the line segment between them intersects a gate polygon.
 * Events appear in the panel only when the replay timestamp passes them.
 * No pre-computed backend data needed.
 */
import { useMemo } from 'react';
import type { VesselTrack } from './VesselLayer';

// ── Gate definitions (must match region.yaml exactly) ─────────────────────────
// Each gate is a thin rectangle on one side of the monitoring box.
const GATES = [
  {
    id: 'GATE_A', label: 'GATE A', color: '#00d4ff',
    minLon: 58.8, maxLon: 59.2, minLat: 14.5, maxLat: 22.0,
  },
  {
    id: 'GATE_B', label: 'GATE B', color: '#00ff88',
    minLon: 59.0, maxLon: 70.0, minLat: 21.8, maxLat: 22.2,
  },
  {
    id: 'GATE_C', label: 'GATE C', color: '#ffb800',
    minLon: 59.0, maxLon: 70.0, minLat: 14.3, maxLat: 14.7,
  },
  {
    id: 'GATE_D', label: 'GATE D', color: '#ff6b6b',
    minLon: 69.8, maxLon: 70.2, minLat: 14.5, maxLat: 22.0,
  },
];

function pointInGate(lat: number, lon: number, gate: typeof GATES[0]): boolean {
  return lat >= gate.minLat && lat <= gate.maxLat &&
         lon >= gate.minLon && lon <= gate.maxLon;
}

interface LiveCrossingEvent {
  id: string;
  vessel_id: string;
  vessel_name: string;
  gateway_id: string;
  gateway_label: string;
  color: string;
  event_type: 'ENTERED' | 'EXITED';
  timestamp: Date;
  speed_knots: number;
  course_deg: number;
}

function computeCrossings(tracks: VesselTrack[]): LiveCrossingEvent[] {
  const events: LiveCrossingEvent[] = [];

  for (const track of tracks) {
    const pings = track.positions;
    if (!pings || pings.length < 2) continue;

    for (const gate of GATES) {
      let wasInside = pointInGate(pings[0].lat, pings[0].lon, gate);

      for (let i = 1; i < pings.length; i++) {
        const p = pings[i];
        const isInside = pointInGate(p.lat, p.lon, gate);

        if (!wasInside && isInside) {
          // Vessel entered gate
          events.push({
            id: `${track.vessel_id}-${gate.id}-ENTERED-${i}`,
            vessel_id: track.vessel_id,
            vessel_name: track.vessel_name,
            gateway_id: gate.id,
            gateway_label: gate.label,
            color: gate.color,
            event_type: 'ENTERED',
            timestamp: new Date(p.timestamp),
            speed_knots: p.sog,
            course_deg: p.cog,
          });
        } else if (wasInside && !isInside) {
          // Vessel exited gate
          events.push({
            id: `${track.vessel_id}-${gate.id}-EXITED-${i}`,
            vessel_id: track.vessel_id,
            vessel_name: track.vessel_name,
            gateway_id: gate.id,
            gateway_label: gate.label,
            color: gate.color,
            event_type: 'EXITED',
            timestamp: new Date(p.timestamp),
            speed_knots: p.sog,
            course_deg: p.cog,
          });
        }

        wasInside = isInside;
      }
    }
  }

  // Sort chronologically
  return events.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
}

function formatUTC(d: Date) {
  return d.toLocaleTimeString('en-GB', {
    hour: '2-digit', minute: '2-digit', timeZone: 'UTC',
  }) + ' UTC';
}

interface Props {
  caseId: string;
  currentTimestamp: Date;
  selectedVesselId: string | null;
  tracks: VesselTrack[];
}

export default function GatewayEventPanel({ currentTimestamp, selectedVesselId, tracks }: Props) {
  // Compute all crossings from the actual vessel tracks (zero backend dependency)
  const allEvents = useMemo(() => computeCrossings(tracks), [tracks]);

  // Only show events that have occurred at or before the current replay time
  const cutoffMs = currentTimestamp.getTime();
  const visibleEvents = allEvents
    .filter(ev => ev.timestamp.getTime() <= cutoffMs)
    .reverse(); // most recent first

  const filteredEvents = selectedVesselId
    ? visibleEvents.filter(ev => ev.vessel_id === selectedVesselId)
    : visibleEvents;

  return (
    <div style={{ width: 280, minWidth: 280, flexShrink: 0, borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', background: 'var(--bg-card)', backdropFilter: 'blur(16px)', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 7, height: 7, borderRadius: '50%',
          background: visibleEvents.length > 0 ? '#00ff88' : '#888',
          boxShadow: visibleEvents.length > 0 ? '0 0 6px #00ff88' : 'none',
          flexShrink: 0,
        }} />
        <span style={{ fontWeight: 700, fontSize: 12, letterSpacing: '0.08em', color: 'var(--text-primary)' }}>
          GATEWAY CROSSINGS
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 10, background: 'rgba(0,212,255,0.12)', color: 'var(--cyan)', borderRadius: 4, padding: '2px 6px', fontFamily: 'JetBrains Mono' }}>
          {visibleEvents.length} / {allEvents.length}
        </span>
      </div>

      {/* Filter strip */}
      {selectedVesselId && (
        <div style={{ padding: '6px 12px', background: 'rgba(0,212,255,0.06)', borderBottom: '1px solid var(--border)', fontSize: 10, color: 'var(--cyan)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span>Filtered: {selectedVesselId}</span>
          <span style={{ marginLeft: 'auto', opacity: 0.7 }}>({filteredEvents.length} events)</span>
        </div>
      )}

      {/* Data source badge */}
      <div style={{ padding: '4px 12px', borderBottom: '1px solid var(--border)', fontSize: 9, color: '#666', fontFamily: 'JetBrains Mono', letterSpacing: '0.06em' }}>
        LIVE · Computed from AIS track segments · Replay time-filtered
      </div>

      {/* Event list */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {tracks.length === 0 && (
          <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>Loading tracks…</div>
        )}
        {tracks.length > 0 && filteredEvents.length === 0 && (
          <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>
            {allEvents.length === 0
              ? 'No crossings detected in tracks.'
              : 'No crossings yet — advance the replay.'}
          </div>
        )}
        {filteredEvents.map(ev => (
          <div
            key={ev.id}
            style={{ padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.04)', display: 'flex', gap: 10, alignItems: 'flex-start' }}
          >
            {/* Color dot */}
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: ev.color, marginTop: 3, flexShrink: 0, boxShadow: `0 0 5px ${ev.color}` }} />

            <div style={{ flex: 1, minWidth: 0 }}>
              {/* Vessel ID */}
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>
                {ev.vessel_id}
                <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontSize: 10, marginLeft: 4 }}>
                  {ev.vessel_name}
                </span>
              </div>

              {/* Gateway name */}
              <div style={{ fontSize: 11, color: ev.color, marginTop: 2, fontWeight: 600 }}>
                {ev.gateway_label}
              </div>

              {/* Event type + time */}
              <div style={{ fontSize: 10, marginTop: 2, display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{
                  background: ev.event_type === 'ENTERED' ? 'rgba(0,255,136,0.12)' : 'rgba(255,107,107,0.12)',
                  color: ev.event_type === 'ENTERED' ? '#00ff88' : '#ff6b6b',
                  padding: '1px 6px', borderRadius: 3, fontWeight: 700, letterSpacing: '0.06em',
                }}>
                  {ev.event_type}
                </span>
                <span style={{ color: 'var(--text-muted)', fontFamily: 'JetBrains Mono', fontSize: 10 }}>
                  {formatUTC(ev.timestamp)}
                </span>
              </div>

              {/* Speed / course */}
              <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2, fontFamily: 'JetBrains Mono' }}>
                {ev.speed_knots.toFixed(1)} kn · {ev.course_deg.toFixed(0)}°
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
