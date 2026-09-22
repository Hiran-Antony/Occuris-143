/**
 * MonitoringView.tsx — Default view.
 * Shows Arabian Sea overview with all cases' source zones / bounding boxes.
 */
import React from 'react';
import { OccurisMap } from '../map/OccurisMap';
import { KpiStrip } from '../components/monitoring/KpiStrip';
import { CaseSummaryPanel } from '../components/monitoring/CaseSummaryPanel';
import { ModulePipeline } from '../components/monitoring/ModulePipeline';
import { SpillLayer } from '../map/layers/SpillLayer';
import { CASE_LIST } from '../data/cases';
import { useDashboardStore } from '../store/dashboardStore';

export const MonitoringView: React.FC = () => {
  const selectedCase = useDashboardStore((s) => s.selectedCase);

  return (
    <div className="view-layout view-layout--monitoring">
      <div className="view-layout__main">
        <KpiStrip />
        <div className="view-layout__map-container">
          <OccurisMap>
            {/* Show SAR footprint for all cases (or just the selected one) */}
            {CASE_LIST.map((c) => {
              const visible = selectedCase === 'all' || selectedCase === c.id;
              return (
                <React.Fragment key={c.id}>
                  <SpillLayer caseId={c.id} type="sar" opacity={0.6} visible={visible} />
                  <SpillLayer caseId={c.id} type="mask" opacity={0.8} visible={visible} />
                </React.Fragment>
              );
            })}
          </OccurisMap>
        </div>
      </div>
      <div className="view-layout__side">
        <CaseSummaryPanel />
        <ModulePipeline />
      </div>
    </div>
  );
};
