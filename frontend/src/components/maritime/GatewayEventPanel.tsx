/**
 * GatewayEventPanel — right-side panel showing M5 GatewayCrossingEvent records.
 *
 * Events come exclusively from /api/cases/{caseId}/gateway-events (M5 CrossingDetector output).
 * The panel only shows events whose timestamp is <= the current AIS replay timestamp.
 *
 * No crossing events are calculated or fabricated in React. React only displays
 * what the backend's M5 module detected.
 */
import { useEffect, useState } from 'react';
import { caseApi } from '../../api/client';

interface GatewayCrossingEvent {
  event_id: string;
  vessel_id: string;
  vessel_name: string;
  gateway_id: string;
  event_type: 'ENTRY' | 'EXIT' | 'CORRIDOR_CROSSING';
  timestamp: string;
  latitude: number;
  longitude: number;
  speed_knots: number;
  course_deg: number;
}

const GATEWAY_COLORS: Record<string, string> = {
  GATE_A: '#00d4ff',
  GATE_B: '#ffb800',
  GATE_C: '#00ff88',
  GATE_D: '#ff6b6b',
};

const EVENT_TYPE_LABEL: Record<string, string> = {
  ENTRY: 'ENTERED',
  EXIT: 'EXITED',
  CORRIDOR_CROSSING: 'CROSSING',
};

function formatUTC(iso: string) {
  return new Date(iso).toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  }) + ' UTC';
}

interface Props {
  caseId: string;
  currentTimestamp: Date;
  selectedVesselId: string | null;
}

export default function GatewayEventPanel({ caseId, currentTimestamp, selectedVesselId }: Props) {
  const [allEvents, setAllEvents] = useState<GatewayCrossingEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    caseApi.getGatewayEvents(caseId)
      .then((data: GatewayCrossingEvent[]) => {
        // Sort chronologically
        const sorted = [...(data || [])].sort(
          (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );
        setAllEvents(sorted);
      })
      .catch(() => setAllEvents([]))
      .finally(() => setLoading(false));
  }, [caseId]);

  // Only show events that have occurred at or before the current replay timestamp
  const cutoffMs = currentTimestamp.getTime();
  const visibleEvents = allEvents
    .filter(ev => new Date(ev.timestamp).getTime() <= cutoffMs)
    .reverse(); // most recent first

  const filteredEvents = selectedVesselId
    ? visibleEvents.filter(ev => ev.vessel_id === selectedVesselId)
    : visibleEvents;

  return (
    <div style={{ width: 280, minWidth: 280, flexShrink: 0, borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', background: 'var(--bg-card)', backdropFilter: 'blur(16px)', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ width: 7, height: 7, borderRadius: '50%', background: allEvents.length > 0 ? '#00ff88' : '#888', boxShadow: allEvents.length > 0 ? '0 0 6px #00ff88' : 'none', flexShrink: 0 }} />
        <span style={{ fontWeight: 700, fontSize: 12, letterSpacing: '0.08em', color: 'var(--text-primary)' }}>
          GATEWAY CROSSINGS
        </span>
        {allEvents.length > 0 && (
          <span style={{ marginLeft: 'auto', fontSize: 10, background: 'rgba(0,212,255,0.12)', color: 'var(--cyan)', borderRadius: 4, padding: '2px 6px', fontFamily: 'JetBrains Mono' }}>
            {allEvents.length} total
          </span>
        )}
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
        SOURCE: M5 CrossingDetector · MVP / SYNTHETIC TEST DATA
      </div>

      {/* Event list */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading && (
          <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>Loading events…</div>
        )}
        {!loading && filteredEvents.length === 0 && (
          <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>
            {allEvents.length === 0
              ? 'No crossing events found.'
              : 'No events before current timestamp.'}
          </div>
        )}
        {filteredEvents.map(ev => {
          const gwColor = GATEWAY_COLORS[ev.gateway_id] || '#7ba7c0';
          const isEntry = ev.event_type === 'ENTRY';
          return (
            <div
              key={ev.event_id}
              style={{ padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.04)', display: 'flex', gap: 10, alignItems: 'flex-start' }}
            >
              {/* Color dot */}
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: gwColor, marginTop: 3, flexShrink: 0, boxShadow: `0 0 5px ${gwColor}` }} />

              <div style={{ flex: 1, minWidth: 0 }}>
                {/* Vessel ID */}
                <div style={{ fontFamily: 'JetBrains Mono', fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>
                  {ev.vessel_id}
                  <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontSize: 10, marginLeft: 4 }}>
                    {ev.vessel_name}
                  </span>
                </div>

                {/* Gateway name */}
                <div style={{ fontSize: 11, color: gwColor, marginTop: 2, fontWeight: 600 }}>
                  {ev.gateway_id.replace('_', ' ')}
                </div>

                {/* Event type */}
                <div style={{ fontSize: 10, marginTop: 2, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ background: isEntry ? 'rgba(0,255,136,0.12)' : 'rgba(255,107,107,0.12)', color: isEntry ? '#00ff88' : '#ff6b6b', padding: '1px 6px', borderRadius: 3, fontWeight: 700, letterSpacing: '0.06em' }}>
                    {EVENT_TYPE_LABEL[ev.event_type] || ev.event_type}
                  </span>
                  <span style={{ color: 'var(--text-muted)', fontFamily: 'JetBrains Mono', fontSize: 10 }}>
                    {formatUTC(ev.timestamp)}
                  </span>
                </div>

                {/* Speed */}
                <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2, fontFamily: 'JetBrains Mono' }}>
                  {ev.speed_knots.toFixed(1)} kn · {ev.course_deg.toFixed(0)}°
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
