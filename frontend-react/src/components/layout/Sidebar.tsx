/**
 * Sidebar.tsx — Persistent navigation sidebar.
 * PART 1: MONITORING — Regional Monitoring, Maritime Memory
 * PART 2: FORENSICS  — Spill, SpillSplit, Drift, Investigation, Replay, Report
 *
 * Clicking a nav item changes the active view inside the same dashboard shell.
 * It does NOT navigate to a separate HTML page.
 */
import React from 'react';
import { useDashboardStore } from '../../store/dashboardStore';
import type { ViewId } from '../../types/investigation';

interface NavItem {
  id: ViewId;
  icon: string;
  label: string;
  badge: string;
  badgeVariant?: 'active' | 'pending';
}

const PART1: NavItem[] = [
  { id: 'monitoring', icon: '⊞', label: 'Regional Monitoring', badge: 'LIVE', badgeVariant: 'active' },
  { id: 'maritime',   icon: '🧠', label: 'Maritime Memory',    badge: 'M5',   badgeVariant: 'active' },
];

const PART2: NavItem[] = [
  { id: 'spill',         icon: '🛢',  label: 'Spill Investigation', badge: 'M1·M2', badgeVariant: 'active' },
  { id: 'spillsplit',    icon: '✂️',  label: 'SpillSplit',          badge: 'M4',    badgeVariant: 'active' },
  { id: 'drift',         icon: '🌊',  label: 'Drift Forecast',      badge: 'M3',    badgeVariant: 'active' },
  { id: 'investigation', icon: '🔎',  label: 'Investigation',       badge: 'M6-8',  badgeVariant: 'active' },
  { id: 'replay',        icon: '▶',   label: 'Vessel Replay',       badge: 'M5',    badgeVariant: 'active' },
  { id: 'report',        icon: '📄',  label: 'Case Report',         badge: 'M8',    badgeVariant: 'active' },
];

export const Sidebar: React.FC = () => {
  const activeView = useDashboardStore((s) => s.activeView);
  const setActiveView = useDashboardStore((s) => s.setActiveView);
  const sidebarCollapsed = useDashboardStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useDashboardStore((s) => s.toggleSidebar);

  const renderItem = (item: NavItem) => (
    <button
      key={item.id}
      className={`nav-item${activeView === item.id ? ' nav-item--active' : ''}`}
      onClick={() => setActiveView(item.id)}
      title={sidebarCollapsed ? item.label : undefined}
      aria-current={activeView === item.id ? 'page' : undefined}
    >
      <span className="nav-item__icon">{item.icon}</span>
      {!sidebarCollapsed && (
        <>
          <span className="nav-item__label">{item.label}</span>
          <span className={`nav-item__badge nav-item__badge--${item.badgeVariant ?? 'pending'}`}>
            {item.badge}
          </span>
        </>
      )}
    </button>
  );

  return (
    <aside className={`sidebar${sidebarCollapsed ? ' sidebar--collapsed' : ''}`}>
      {/* Logo */}
      <div className="sidebar__logo">
        <div className="sidebar__logo-icon">⬡</div>
        {!sidebarCollapsed && (
          <div className="sidebar__logo-text">
            <span className="sidebar__logo-title">OCCURIS</span>
            <span className="sidebar__logo-sub">MARITIME INTELLIGENCE · SIH 2026</span>
          </div>
        )}
        <button className="sidebar__collapse-btn" onClick={toggleSidebar} title="Toggle sidebar">
          {sidebarCollapsed ? '›' : '‹'}
        </button>
      </div>

      {/* Part 1 */}
      <div className="sidebar__section-label">{!sidebarCollapsed && 'PART 1 — MONITORING'}</div>
      <nav className="sidebar__nav">{PART1.map(renderItem)}</nav>

      {/* Part 2 */}
      <div className="sidebar__section-label sidebar__section-label--mt">{!sidebarCollapsed && 'PART 2 — FORENSICS'}</div>
      <nav className="sidebar__nav">{PART2.map(renderItem)}</nav>

      {/* Status footer */}
      <div className="sidebar__footer">
        <span className="sidebar__status-dot" />
        {!sidebarCollapsed && <span>Modules 0–8 Active</span>}
      </div>
    </aside>
  );
};
