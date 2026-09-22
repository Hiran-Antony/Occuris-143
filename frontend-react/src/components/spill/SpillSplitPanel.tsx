/**
 * SpillSplitPanel.tsx — Renders BIC comparison and stability scores.
 * Only uses actual M4 json outputs.
 */
import React from 'react';
import type { SpillSplitResult } from '../../types/investigation';
import { MetricCard } from '../common/MetricCard';

interface Props {
  data: SpillSplitResult | null;
}

export const SpillSplitPanel: React.FC<Props> = ({ data }) => {
  if (!data) return <div className="panel__content panel__content--empty">Loading SpillSplit data...</div>;

  const { one_source, two_source, result, stability } = data;

  return (
    <div className="panel spillsplit-panel">
      <div className="panel__header">
        <h2 className="panel__title">SOURCE HYPOTHESIS TESTING (M4)</h2>
      </div>
      <div className="panel__content">
        <div className="spillsplit-verdict">
          <div className="spillsplit-verdict__label">Selected Hypothesis</div>
          <div className="spillsplit-verdict__value">
            {result === 'two_sources' ? 'H2: TWO SOURCES' : 'H1: SINGLE SOURCE'}
          </div>
        </div>

        <div className="panel__section-title">Bayesian Information Criterion (BIC)</div>
        <div className="bic-comparison">
          <div className={`bic-bar ${result === 'one_source' ? 'bic-bar--winner' : ''}`}>
            <span className="bic-bar__label">H1 (Single)</span>
            <span className="bic-bar__value">{one_source.bic.toFixed(1)}</span>
            <div className="bic-bar__fill" style={{ width: '80%' }} />
          </div>
          <div className={`bic-bar ${result === 'two_sources' ? 'bic-bar--winner' : ''}`}>
            <span className="bic-bar__label">H2 (Two)</span>
            <span className="bic-bar__value">{two_source.bic.toFixed(1)}</span>
            <div className="bic-bar__fill" style={{ width: '95%' }} />
          </div>
          <div className="bic-note">Lower BIC score is better.</div>
        </div>

        <div className="panel__section-title">Stability & Separation</div>
        <div className="spill-metrics-grid">
          <MetricCard 
            label="Stability Score" 
            value={(stability.score * 100).toFixed(1)} 
            unit="%"
          />
          <MetricCard 
            label="Variation" 
            value={stability.variation_km.toFixed(2)} 
            unit="km"
          />
          <MetricCard 
            label="Source Separation" 
            value={data.source_separation_km.toFixed(1)} 
            unit="km"
          />
        </div>
      </div>
    </div>
  );
};
