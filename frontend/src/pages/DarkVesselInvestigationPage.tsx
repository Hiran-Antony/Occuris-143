import { useState } from 'react';
import { NavLink } from 'react-router-dom';

export default function DarkVesselInvestigationPage() {
  const [selectedMmsi, setSelectedMmsi] = useState('419000042');

  const suspects = [
    {
      mmsi: '419000042',
      name: 'MT DESH SHOBHA',
      type: 'Crude Oil Tanker',
      flag: '🇮🇳 India',
      imo: '9238411',
      callsign: 'VTR9',
      score: 94,
      status: 'Selected Candidate',
      statusColor: '#ff3366',
      aisGapDuration: '2h 15m (12:30 – 14:45 UTC)',
      distanceToOrigin: '0.4 nautical miles',
      speedChange: 'Decelerated from 10.0 to 4.0 kts then resumed',
      justification: 'No squall or mechanical distress signal logged on GMDSS.',
      riskFactors: [
        'Dark AIS Gap directly overlaps 12:00–16:00 estimated spill release window',
        'Vessel transit path directly crosses 13.16°N, 86.19°E slick centroid',
        'Tanker vessel type carrying heavy petroleum hydrocarbons',
        'Resumed full speed (10.5 kts) immediately after transponder reactivation'
      ]
    },
    {
      mmsi: '419000040',
      name: 'EASTERN STAR',
      type: 'Container / Cargo',
      flag: '🇸🇬 Singapore',
      imo: '9184520',
      callsign: '9V823',
      score: 48,
      status: 'SECONDARY CANDIDATE',
      statusColor: '#ffb800',
      aisGapDuration: 'None (Continuous AIS broadcast)',
      distanceToOrigin: '4.8 nautical miles',
      speedChange: 'Minor heading alteration from 095° to 080°',
      justification: 'Course change corresponds to traffic separation adjustment.',
      riskFactors: [
        'Cargo ship with bunker fuel capacity only (less consistent with heavy slick)',
        'Continuous AIS transponder broadcast without blackouts',
        'Track passes 4.8 nm north of backtracked origin zone'
      ]
    },
    {
      mmsi: '419000041',
      name: 'GULF WAVE',
      type: 'Product Tanker',
      flag: '🇲🇾 Malaysia',
      imo: '9312948',
      callsign: '9MA21',
      score: 18,
      status: 'EXONERATED / WEATHER',
      statusColor: '#00ff88',
      aisGapDuration: 'None (Continuous AIS broadcast)',
      distanceToOrigin: '14.2 nautical miles',
      speedChange: 'Slowdown from 10.0 to 4.5 kts',
      justification: 'Vessel encountered localized convective sea state confirmed by scatterometer.',
      riskFactors: [
        'Slowdown fully matches barometric depression recorded by MetOcean sensor',
        'Distance to slick exceeds 14 nautical miles',
        'No deliberate transponder manipulation'
      ]
    }
  ];

  const active = suspects.find(s => s.mmsi === selectedMmsi) || suspects[0];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg-primary)', color: 'var(--text-primary)', overflow: 'hidden' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 24px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 20 }}>🔍</span>
            <h1 style={{ fontSize: 18, fontWeight: 700, letterSpacing: 0.5 }}>Dark Vessel Forensics & AIS Anomaly Matrix</h1>
            <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(255, 51, 102, 0.15)', color: 'var(--red)', border: '1px solid var(--red)' }}>
              MARPOL ANNEX I INVESTIGATION
            </span>
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Automated suspect ranking correlating dark transponder gaps, route deviations, and spatiotemporal proximity to the detected slick.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <NavLink
            to="/replay"
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 6, background: 'rgba(0, 212, 255, 0.15)', color: 'var(--cyan)', border: '1px solid var(--cyan)', textDecoration: 'none', fontSize: 12, fontWeight: 600 }}
          >
            ▶️ Open Vessel Replay
          </NavLink>
          <NavLink
            to="/report"
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 6, background: 'var(--cyan)', color: '#000', border: 'none', textDecoration: 'none', fontSize: 12, fontWeight: 700 }}
          >
            📄 Generate Case Dossier
          </NavLink>
        </div>
      </div>

      {/* Main Grid */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', padding: 20, gap: 20 }}>
        {/* Left Suspect Ranking List */}
        <div style={{ flex: '1 1 35%', display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
            Ranked Suspect Vessels ({suspects.length})
          </h3>

          {suspects.map(s => (
            <div
              key={s.mmsi}
              onClick={() => setSelectedMmsi(s.mmsi)}
              style={{
                background: selectedMmsi === s.mmsi ? 'rgba(0, 212, 255, 0.1)' : 'var(--bg-card)',
                border: `1px solid ${selectedMmsi === s.mmsi ? 'var(--cyan)' : 'var(--border)'}`,
                borderRadius: 10,
                padding: 16,
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: s.statusColor, background: `${s.statusColor}18`, padding: '2px 8px', borderRadius: 4 }}>
                  {s.status}
                </span>
                <span style={{ fontSize: 16, fontWeight: 700, color: s.statusColor }}>
                  {s.score}% Anomaly
                </span>
              </div>
              <h4 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                {s.name}
              </h4>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'flex', gap: 12 }}>
                <span>MMSI: {s.mmsi}</span>
                <span>{s.type}</span>
                <span>{s.flag}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Right Suspect Forensic Dossier */}
        <div style={{ flex: '1 1 65%', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 12, padding: 24, overflowY: 'auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border)', paddingBottom: 16, marginBottom: 20 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)' }}>{active.name}</h2>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>IMO: {active.imo} · Call Sign: {active.callsign}</span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--cyan)', marginTop: 4 }}>
                Flag State: {active.flag} · Category: {active.type}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Forensic Match Score</div>
              <div style={{ fontSize: 32, fontWeight: 700, color: active.statusColor, fontFamily: 'JetBrains Mono' }}>
                {active.score} / 100
              </div>
            </div>
          </div>

          {/* Anomaly Indicators Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 24 }}>
            <div style={{ background: 'var(--bg-card)', padding: 14, borderRadius: 8, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>AIS Gap Event</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: active.mmsi === '419000042' ? 'var(--red)' : 'var(--text-primary)' }}>
                {active.aisGapDuration}
              </div>
            </div>
            <div style={{ background: 'var(--bg-card)', padding: 14, borderRadius: 8, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Proximity to Slick Centroid</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--cyan)' }}>
                {active.distanceToOrigin}
              </div>
            </div>
            <div style={{ background: 'var(--bg-card)', padding: 14, borderRadius: 8, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Speed / Course Behavior</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                {active.speedChange}
              </div>
            </div>
            <div style={{ background: 'var(--bg-card)', padding: 14, borderRadius: 8, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Meteorological Justification</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                {active.justification}
              </div>
            </div>
          </div>

          {/* Key Evidence Bulletins */}
          <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Chain of Custody & Evidence Findings
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 24 }}>
            {active.riskFactors.map((f, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, background: 'rgba(255,255,255,0.02)', padding: 12, borderRadius: 6, border: '1px solid rgba(255,255,255,0.06)' }}>
                <span style={{ color: active.statusColor, fontSize: 14 }}>⚠️</span>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{f}</span>
              </div>
            ))}
          </div>

          {/* Action Callout */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0, 212, 255, 0.08)', padding: 16, borderRadius: 8, border: '1px solid rgba(0, 212, 255, 0.25)' }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--cyan)' }}>Recommended Maritime Action</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                Issue MARPOL Annex I Detention Notice & request Port State Control bilge sampling at destination port.
              </div>
            </div>
            <button
              onClick={() => alert(`Official PSC alert issued for MMSI ${active.mmsi} (${active.name}) to Indian Coast Guard & DG Shipping.`)}
              style={{ background: 'var(--red)', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: 6, fontWeight: 700, fontSize: 12, cursor: 'pointer' }}
            >
              🚨 Transmit PSC Notice
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
