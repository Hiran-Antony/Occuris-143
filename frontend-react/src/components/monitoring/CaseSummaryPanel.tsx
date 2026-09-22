/**
 * CaseSummaryPanel.tsx — Right panel in Monitoring view.
 * Shows active case list and allows clicking to select a case.
 */
import React from 'react';
import { CASE_LIST, CASE_COLORS } from '../../data/cases';
import { useDashboardStore } from '../../store/dashboardStore';

export const CaseSummaryPanel: React.FC = () => {
  const selectedCase = useDashboardStore((s) => s.selectedCase);
  const setSelectedCase = useDashboardStore((s) => s.setSelectedCase);

  return (
    <div className="panel case-summary-panel">
      <div className="panel__header">
        <h2 className="panel__title">ACTIVE CASES</h2>
        <div className="panel__subtitle">Arabian Sea Region</div>
      </div>
      
      <div className="panel__content">
        {CASE_LIST.map((c) => {
          const isActive = selectedCase === c.id || selectedCase === 'all';
          const color = CASE_COLORS[c.id];
          return (
            <button
              key={c.id}
              className={`case-card${isActive ? ' case-card--active' : ''}`}
              onClick={() => setSelectedCase(c.id)}
            >
              <div className="case-card__header">
                <span className="case-card__dot" style={{ backgroundColor: color }} />
                <span className="case-card__id">{c.id.toUpperCase().replace('_', ' ')}</span>
                <span className="case-card__time">{new Date(c.sar_timestamp).toLocaleDateString()}</span>
              </div>
              <div className="case-card__title">{c.title.split('—')[1]?.trim() ?? c.title}</div>
              <div className="case-card__desc">{c.description}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
