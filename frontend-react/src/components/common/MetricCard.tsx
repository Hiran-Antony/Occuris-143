/**
 * MetricCard.tsx — Reusable KPI card.
 * Values come from actual data. If value is null/undefined, shows "— / INSUFFICIENT DATA".
 * Never accepts hardcoded numbers.
 */
import React from 'react';

interface Props {
  label: string;
  value: string | number | null | undefined;
  unit?: string;
  caveat?: string;        // e.g. "PROVISIONAL GEOSPATIAL SCALE"
  highlight?: boolean;
  icon?: string;
}

export const MetricCard: React.FC<Props> = ({ label, value, unit, caveat, highlight, icon }) => {
  const displayValue = value !== null && value !== undefined ? value : '—';
  const hasData = value !== null && value !== undefined;

  return (
    <div className={`metric-card${highlight ? ' metric-card--highlight' : ''}`}>
      {icon && <span className="metric-card__icon">{icon}</span>}
      <div className={`metric-card__value${!hasData ? ' metric-card__value--empty' : ''}`}>
        {displayValue}
        {hasData && unit && <span className="metric-card__unit"> {unit}</span>}
      </div>
      <div className="metric-card__label">{label}</div>
      {caveat && <div className="metric-card__caveat">{caveat}</div>}
      {!hasData && <div className="metric-card__caveat metric-card__caveat--insufficient">INSUFFICIENT DATA</div>}
    </div>
  );
};
