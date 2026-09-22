/**
 * DashboardShell.tsx — Root layout: Sidebar + TopHeader + SyntheticBanner + MainContent.
 * One integrated application. No separate HTML pages.
 */
import React from 'react';
import { Sidebar } from './Sidebar';
import { TopHeader } from './TopHeader';
import { SyntheticBanner } from '../common/SyntheticBanner';
import { useDashboardStore } from '../../store/dashboardStore';

// Views
import { MonitoringView } from '../../views/MonitoringView';
import { MaritimeView } from '../../views/MaritimeView';
import { SpillView } from '../../views/SpillView';
import { SpillSplitView } from '../../views/SpillSplitView';
import { DriftView } from '../../views/DriftView';
import { InvestigationView } from '../../views/InvestigationView';
import { VesselReplayView } from '../../views/VesselReplayView';
import { CaseReportView } from '../../views/CaseReportView';

const VIEW_MAP = {
  monitoring:    MonitoringView,
  maritime:      MaritimeView,
  spill:         SpillView,
  spillsplit:    SpillSplitView,
  drift:         DriftView,
  investigation: InvestigationView,
  replay:        VesselReplayView,
  report:        CaseReportView,
};

export const DashboardShell: React.FC = () => {
  const activeView = useDashboardStore((s) => s.activeView);
  const sidebarCollapsed = useDashboardStore((s) => s.sidebarCollapsed);

  const ActiveViewComponent = VIEW_MAP[activeView];

  return (
    <div className={`dashboard-shell${sidebarCollapsed ? ' dashboard-shell--collapsed' : ''}`}>
      <Sidebar />
      <div className="dashboard-shell__main">
        <TopHeader />
        <SyntheticBanner />
        <div className="dashboard-shell__content">
          <ActiveViewComponent />
        </div>
      </div>
    </div>
  );
};
