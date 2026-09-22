/**
 * ModulePipeline.tsx — Visual tracker of Modules 0-9 status.
 * Replaces the old HTML sidebar item "M8 · Ranking" with "M8 · Evidence Fusion".
 */
import React from 'react';

const MODULES = [
  { id: 'M0', name: 'Sentinel-1 Ingestion', status: 'done' },
  { id: 'M1', name: 'SAR Dark Spot Detection', status: 'done' },
  { id: 'M2', name: 'Look-Alike & Geometry', status: 'done' },
  { id: 'M3', name: 'Backward RK45 Drift', status: 'done' },
  { id: 'M4', name: 'SpillSplit BIC Test', status: 'done' },
  { id: 'M5', name: 'AIS Maritime Memory', status: 'done' },
  { id: 'M6', name: 'AIS Verification & Gaps', status: 'done' },
  { id: 'M7', name: 'Counterfactual Trajectory', status: 'done' },
  { id: 'M8', name: 'Evidence Fusion', status: 'done' }, // NO RANKING HERE
  { id: 'M9', name: 'Dashboard Integration', status: 'active' },
];

export const ModulePipeline: React.FC = () => {
  return (
    <div className="panel module-pipeline">
      <div className="panel__header">
        <h2 className="panel__title">PIPELINE STATUS</h2>
      </div>
      <div className="panel__content">
        <ul className="pipeline-list">
          {MODULES.map((m) => (
            <li key={m.id} className={`pipeline-item pipeline-item--${m.status}`}>
              <div className="pipeline-item__icon">
                {m.status === 'done' ? '✓' : m.status === 'active' ? '⟳' : '·'}
              </div>
              <div className="pipeline-item__label">
                <strong>{m.id}</strong> {m.name}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
