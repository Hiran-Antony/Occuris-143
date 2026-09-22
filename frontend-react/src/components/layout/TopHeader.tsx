/**
 * TopHeader.tsx — Dashboard header bar.
 * Shows: current case, region, data status, UTC clock.
 * All values come from app state — nothing is hardcoded.
 */
import React, { useEffect, useState } from 'react';
import { useDashboardStore } from '../../store/dashboardStore';
import { CASES } from '../../data/cases';
import type { CaseId } from '../../types/investigation';

const VIEW_LABELS: Record<string, { icon: string; title: string; sub: string }> = {
  monitoring:    { icon: '📡', title: 'Regional Monitoring',       sub: 'Arabian Sea · 3 Investigation Cases' },
  maritime:      { icon: '🧠', title: 'Maritime Memory',           sub: 'M5 · AIS Trajectory Engine · Virtual Gateways' },
  spill:         { icon: '🛢', title: 'Spill Investigation',        sub: 'M1 · M2 · SAR Detection · Look-Alike · Geometry' },
  spillsplit:    { icon: '✂️', title: 'SpillSplit',                 sub: 'M4 · Source Hypothesis Testing · BIC Comparison' },
  drift:         { icon: '🌊', title: 'Drift Forecast',             sub: 'M3 · Backward RK45 Drift · Origin Zone' },
  investigation: { icon: '🔎', title: 'Investigation',              sub: 'M6 · M7 · M8 · Evidence Fusion' },
  replay:        { icon: '▶',  title: 'Vessel Replay',              sub: 'M5 · AIS Track Replay · Time-Controlled' },
  report:        { icon: '📄', title: 'Case Report',                sub: 'M8 · WeasyPrint · PDF' },
};

const CASE_PILLS: { id: CaseId; label: string; color: string }[] = [
  { id: 'all',     label: 'All Cases',         color: '#00e5ff' },
  { id: 'case_01', label: 'Case 01 · Al-Mahra',     color: '#ff5252' },
  { id: 'case_02', label: 'Case 02 · Lakshadweep',  color: '#ff6b35' },
  { id: 'case_03', label: 'Case 03 · Oman Basin',   color: '#ffd740' },
];

export const TopHeader: React.FC = () => {
  const activeView = useDashboardStore((s) => s.activeView);
  const selectedCase = useDashboardStore((s) => s.selectedCase);
  const setSelectedCase = useDashboardStore((s) => s.setSelectedCase);
  const isSynthetic = useDashboardStore((s) => s.isSynthetic);

  const [utcTime, setUtcTime] = useState('--:--');
  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setUtcTime(
        `${String(now.getUTCHours()).padStart(2, '0')}:${String(now.getUTCMinutes()).padStart(2, '0')}`
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const view = VIEW_LABELS[activeView] ?? VIEW_LABELS.monitoring;
  const caseTitle =
    selectedCase !== 'all' ? CASES[selectedCase]?.title : 'All Cases';

  return (
    <header className="top-header">
      <div className="top-header__left">
        <span className="top-header__view-icon">{view.icon}</span>
        <div>
          <div className="top-header__title">{view.title}</div>
          <div className="top-header__sub">{view.sub}</div>
        </div>
      </div>

      {/* Case pills */}
      <div className="case-pills">
        {CASE_PILLS.map((p) => (
          <button
            key={p.id}
            className={`case-pill${selectedCase === p.id ? ' case-pill--active' : ''}`}
            onClick={() => setSelectedCase(p.id)}
            style={{ '--pill-color': p.color } as React.CSSProperties}
          >
            {p.id !== 'all' && (
              <span className="case-pill__dot" style={{ background: p.color }} />
            )}
            {p.label}
          </button>
        ))}
      </div>

      <div className="top-header__right">
        {/* Data status */}
        <div className={`data-status${isSynthetic ? ' data-status--synthetic' : ' data-status--live'}`}>
          {isSynthetic ? '⚠ SYNTHETIC' : '✓ OBSERVED'}
        </div>
        {/* Region */}
        {selectedCase !== 'all' && (
          <div className="top-header__region">
            {caseTitle.split('—')[1]?.trim() ?? caseTitle}
          </div>
        )}
        {/* UTC Clock */}
        <div className="top-header__clock">
          <span className="top-header__clock-label">Demo</span>
          <span className="top-header__clock-time">{utcTime}</span>
          <span className="top-header__clock-label">UTC</span>
        </div>
      </div>
    </header>
  );
};
