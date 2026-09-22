/**
 * SpillCasePanel.tsx — Right panel for Spill Investigation View.
 * Shows geometry metrics and Look-Alike test results.
 */
import React, { useEffect, useState } from 'react';
import type { GeometryResult } from '../../types/investigation';
import { MetricCard } from '../common/MetricCard';

interface Props {
  caseId: string;
}

export const SpillCasePanel: React.FC<Props> = ({ caseId }) => {
  const [data, setData] = useState<GeometryResult | null>(null);

  useEffect(() => {
    if (caseId === 'all') {
      setData(null);
      return;
    }
    
    fetch(`/data/processed/${caseId}_geometry.json`)
      .then(res => res.json())
      .then(d => setData(d))
      .catch(err => {
        console.error("Failed to fetch geometry for", caseId, err);
        setData(null);
      });
  }, [caseId]);

  if (caseId === 'all') {
    return (
      <div className="panel spill-case-panel">
        <div className="panel__content panel__content--empty">
          Please select a specific case from the top header to view spill analysis.
        </div>
      </div>
    );
  }

  return (
    <div className="panel spill-case-panel">
      <div className="panel__header">
        <h2 className="panel__title">SPILL ANALYSIS</h2>
      </div>
      <div className="panel__content">
        <div className="panel__section-title">Look-Alike Verification</div>
        <div className="spill-metrics-grid">
          <MetricCard 
            label="Spill Intensity" 
            value={data?.look_alike?.spill_mean_intensity} 
          />
          <MetricCard 
            label="Background Intensity" 
            value={data?.look_alike?.background_mean_intensity} 
          />
          <MetricCard 
            label="Contrast Ratio" 
            value={data?.look_alike?.contrast_ratio} 
          />
        </div>
        <div className={`look-alike-status ${data?.look_alike?.passed ? 'look-alike-status--pass' : 'look-alike-status--fail'}`}>
          {data ? (data.look_alike?.passed ? '✓ PASSED' : '✗ FAILED') : 'INSUFFICIENT DATA'}
        </div>
        <div className="panel__text">
          {data?.look_alike?.interpretation || '—'}
        </div>

        <div className="panel__section-title">Geometric Properties</div>
        <div className="spill-metrics-grid">
          <MetricCard 
            label="Total Area" 
            value={data?.geometry?.area_km2} 
            unit="km²"
            caveat="PROVISIONAL GEOSPATIAL SCALE"
          />
          <MetricCard 
            label="Major Axis" 
            value={data?.geometry?.major_axis_km} 
            unit="km"
          />
          <MetricCard 
            label="Orientation" 
            value={data?.geometry?.orientation_deg} 
            unit="°"
          />
        </div>
      </div>
    </div>
  );
};
