/**
 * VesselInspector.tsx — Details panel for vessels in Maritime Memory.
 */
import React, { useEffect, useState } from 'react';
import { useDashboardStore } from '../../store/dashboardStore';
import { fetchVessels, type VesselSummary } from '../../services/maritimeApi';
import { MetricCard } from '../common/MetricCard';

export const VesselInspector: React.FC = () => {
  const selectedVessel = useDashboardStore((s) => s.selectedVessel);
  const setSelectedVessel = useDashboardStore((s) => s.setSelectedVessel);
  
  const [vessels, setVessels] = useState<VesselSummary[]>([]);

  useEffect(() => {
    fetchVessels().then((data) => setVessels(data));
  }, []);

  const v = selectedVessel !== 'all' ? vessels.find(x => x.vessel_id === selectedVessel) : null;

  return (
    <div className="panel vessel-inspector">
      <div className="panel__header">
        <h2 className="panel__title">MARITIME TRACKING</h2>
        <div className="panel__subtitle">Select a vessel to inspect</div>
      </div>
      
      <div className="panel__content">
        <div className="vessel-list">
          {vessels.map(vessel => (
            <button
              key={vessel.vessel_id}
              className={`case-card${selectedVessel === vessel.vessel_id ? ' case-card--active' : ''}`}
              onClick={() => setSelectedVessel(vessel.vessel_id)}
            >
              <div className="case-card__header">
                <span className="case-card__id">{vessel.vessel_id}</span>
                <span className="case-card__time">MMSI: {vessel.mmsi}</span>
              </div>
              <div className="case-card__title">{vessel.vessel_name}</div>
              <div className="case-card__desc">Status: {vessel.status.replace(/_/g, ' ')}</div>
            </button>
          ))}
        </div>
      </div>

      {v && (
        <div className="panel__content" style={{ borderTop: '1px solid var(--border-light)' }}>
          <div className="panel__section-title">Current Telemetry</div>
          <div className="spill-metrics-grid">
            <MetricCard label="SOG" value={v.sog.toFixed(1)} unit="kn" />
            <MetricCard label="COG" value={v.cog.toFixed(1)} unit="°" />
          </div>
          <div style={{ marginTop: '12px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Nav Status: {v.nav_status_label}
          </div>
        </div>
      )}
    </div>
  );
};
