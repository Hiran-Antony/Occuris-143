import { useEffect, useState } from 'react';
import { vesselApi, dashboardApi } from '../api/client';
import type { Vessel, BehaviourEvent, TimelineEvent, DashboardStats } from '../types';

function formatDuration(h: number | null) {
  if (h == null) return '—';
  const hrs = Math.floor(h);
  const min = Math.round((h - hrs) * 60);
  return `${hrs}h ${min}m`;
}

function delayClass(d: number | null) {
  if (d == null) return '';
  if (d <= 1) return 'delay-on-time';
  if (d <= 3) return 'delay-minor';
  if (d <= 6) return 'delay-significant';
  return 'delay-major';
}

function delayLabel(d: number | null) {
  if (d == null) return '—';
  if (d <= 1) return `+${formatDuration(d)} ✓`;
  if (d <= 3) return `+${formatDuration(d)}`;
  return `+${formatDuration(d)} ⚠`;
}

function EventTypeIcon({ type }: { type: string }) {
  const map: Record<string, string> = {
    ais_gap: '📵',
    impossible_jump: '⚡',
    operational_stop: '⚓',
    speed_reduction: '🐢',
    route_deviation: '↗️',
  };
  return <span>{map[type] || '🔸'}</span>;
}

function GateBadge({ gate }: { gate: string | null }) {
  if (!gate) return <span style={{ color: 'var(--text-muted)' }}>—</span>;
  return <span className={`badge badge-gate-${gate}`}>Gate {gate}</span>;
}

function TimelinePanel({ mmsi, onClose }: { mmsi: string; onClose: () => void }) {
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [events, setEvents] = useState<BehaviourEvent[]>([]);

  useEffect(() => {
    if (!mmsi) return;
    vesselApi.getTimeline(mmsi).then(setTimeline).catch(() => {});
    vesselApi.getEvents(mmsi).then(setEvents).catch(() => {});
  }, [mmsi]);

  return (
    <div className="timeline-panel fade-in">
      <div className="timeline-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>🧠 Journey Timeline</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 16 }}>✕</button>
        </div>
        <div className="timeline-sub mono">{mmsi}</div>
      </div>

      {/* Behaviour summary */}
      <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className="badge" style={{ background: 'rgba(255,184,0,0.1)', color: 'var(--amber)' }}>
            {events.length} events
          </span>
          <span className="badge badge-unexplained">
            {events.filter(e => !e.is_explained).length} unexplained
          </span>
          <span className="badge badge-explained">
            {events.filter(e => e.is_explained).length} explained
          </span>
        </div>
      </div>

      <div className="timeline-body">
        {timeline.length === 0 && (
          <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>No events recorded</div>
        )}
        {timeline.map((item, i) => {
          const isGate = item.type === 'gateway_crossing';
          const dotClass = isGate ? 'gate' : (item.severity || 'low');
          const time = new Date(item.time).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
          return (
            <div key={i} className="timeline-item">
              <div className={`timeline-dot ${dotClass}`} />
              <div className="timeline-content">
                <div className="timeline-time">{time} UTC</div>
                <div className="timeline-label">
                  {!isGate && <EventTypeIcon type={item.event_type || ''} />} {item.label}
                </div>
                {item.is_explained && item.explanation && (
                  <div className="timeline-explanation">✓ {item.explanation}</div>
                )}
                {!isGate && !item.is_explained && (
                  <div className="timeline-unexplained">⚠ No contextual explanation</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function MaritimeMemory() {
  const [vessels, setVessels] = useState<Vessel[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | 'anomaly' | 'unexplained'>('all');

  useEffect(() => {
    vesselApi.list().then(setVessels).catch(() => {});
    dashboardApi.stats().then(setStats).catch(() => {});
  }, []);

  const filtered = vessels
    .filter(v => {
      const q = search.toLowerCase();
      return v.mmsi.includes(q) || (v.name || '').toLowerCase().includes(q) || v.vessel_type.includes(q);
    })
    .filter(v => {
      if (filter === 'anomaly') return v.behaviour_event_count > 0;
      if (filter === 'unexplained') return v.unexplained_event_count > 0;
      return true;
    });

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">🧠 Maritime Memory</div>
          <div className="page-subtitle">Complete vessel history — journeys, behaviour events, and explanations</div>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          Continuously recorded before any incident
        </div>
      </div>

      {/* Stats */}
      <div className="stats-bar">
        <div className="stat-card">
          <div className="stat-value">{stats?.total_vessels ?? '—'}</div>
          <div className="stat-label">Total Vessels</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats?.completed_journeys ?? '—'}</div>
          <div className="stat-label">Completed Journeys</div>
        </div>
        <div className="stat-card warning">
          <div className="stat-value">{stats?.total_behaviour_events ?? '—'}</div>
          <div className="stat-label">Behaviour Events</div>
        </div>
        <div className="stat-card danger">
          <div className="stat-value">{stats?.unexplained_events ?? '—'}</div>
          <div className="stat-label">Unexplained</div>
        </div>
        <div className="stat-card success">
          <div className="stat-value">{stats ? stats.total_behaviour_events - stats.unexplained_events : '—'}</div>
          <div className="stat-label">Context-Explained</div>
        </div>
      </div>

      {/* Toolbar */}
      <div style={{ padding: '10px 24px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)', display: 'flex', gap: 12, alignItems: 'center' }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search MMSI, name or type…"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: 8, padding: '7px 14px', fontSize: 12, width: 240, outline: 'none' }}
        />
        {(['all', 'anomaly', 'unexplained'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{ background: filter === f ? 'rgba(0,212,255,0.15)' : 'var(--bg-card)', border: `1px solid ${filter === f ? 'var(--cyan)' : 'var(--border)'}`, color: filter === f ? 'var(--cyan)' : 'var(--text-secondary)', borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 11, fontWeight: 600, textTransform: 'capitalize' }}
          >
            {f === 'all' ? 'All Vessels' : f === 'anomaly' ? '⚠ With Events' : '🔴 Unexplained'}
          </button>
        ))}
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}>
          {filtered.length} vessels
        </span>
      </div>

      {/* Table + Timeline */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0, position: 'relative' }}>
        <div className="table-wrapper" style={{ flex: 1, overflowY: 'auto', overflowX: 'auto', height: '100%', position: 'relative' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>MMSI</th>
                <th>Name / Type</th>
                <th>Entry Gate</th>
                <th>Exit Gate</th>
                <th>Actual</th>
                <th>Expected</th>
                <th>Delay</th>
                <th>Status</th>
                <th>Events</th>
                <th>Unexplained</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(v => {
                const j = v.journey;
                const isSuspect = v.mmsi === '419000042';
                return (
                  <tr
                    key={v.mmsi}
                    onClick={() => setSelected(v.mmsi === selected ? null : v.mmsi)}
                    className={selected === v.mmsi ? 'selected' : ''}
                    style={isSuspect ? { borderLeft: '3px solid var(--red)' } : {}}
                  >
                    <td>
                      <span className="mono" style={{ fontSize: 11 }}>{v.mmsi}</span>
                      {isSuspect && <span style={{ marginLeft: 6, fontSize: 10, color: 'var(--red)', fontWeight: 700 }}>⭐ PRIMARY</span>}
                    </td>
                    <td>
                      <div style={{ fontSize: 12, fontWeight: 500 }}>{v.name || '—'}</div>
                      <span className={`badge badge-type-${v.vessel_type}`} style={{ marginTop: 2 }}>{v.vessel_type}</span>
                    </td>
                    <td><GateBadge gate={j?.entry_gateway || null} /></td>
                    <td><GateBadge gate={j?.exit_gateway || null} /></td>
                    <td style={{ fontFamily: 'JetBrains Mono', fontSize: 11 }}>{formatDuration(j?.actual_duration_hours || null)}</td>
                    <td style={{ fontFamily: 'JetBrains Mono', fontSize: 11, color: 'var(--text-muted)' }}>{formatDuration(j?.expected_duration_hours || null)}</td>
                    <td className={delayClass(j?.delay_hours || null)} style={{ fontFamily: 'JetBrains Mono', fontSize: 11, fontWeight: 600 }}>
                      {delayLabel(j?.delay_hours || null)}
                    </td>
                    <td>
                      {j && <span className={`badge badge-status-${j.status}`}>{j.status.replace('_', ' ')}</span>}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {v.behaviour_event_count > 0
                        ? <span style={{ color: 'var(--amber)', fontWeight: 700 }}>{v.behaviour_event_count}</span>
                        : <span style={{ color: 'var(--text-muted)' }}>0</span>}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {v.unexplained_event_count > 0
                        ? <span style={{ color: 'var(--red)', fontWeight: 700 }}>{v.unexplained_event_count}</span>
                        : <span style={{ color: 'var(--green)' }}>0</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Timeline panel */}
        {selected && (
          <TimelinePanel mmsi={selected} onClose={() => setSelected(null)} />
        )}
      </div>
    </div>
  );
}
