import { NavLink } from 'react-router-dom';

const NAV = [
  { to: '/monitoring', icon: '🗺️', label: 'Regional Monitoring', part: 1 },
  { to: '/memory',     icon: '🧠', label: 'Maritime Memory',     part: 1 },
  { to: '/spill',      icon: '🛢️',  label: 'Spill Detection',    part: 2 },
  { to: '/spillsplit', icon: '🔀', label: 'SpillSplit',          part: 2 },
  { to: '/drift',      icon: '🌊', label: 'Drift Forecast',      part: 2 },
  { to: '/incident',   icon: '🔍', label: 'Investigation',       part: 2 },
  { to: '/replay',     icon: '▶️',  label: 'Vessel Replay',      part: 2 },
  { to: '/report',     icon: '📄', label: 'Case Report',         part: 2 },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-name">OCCURIS</div>
        <div className="logo-sub">Maritime Intelligence · SIH 2026</div>
      </div>

      <div className="sidebar-section-label">Part 1 — Monitoring</div>
      <nav className="sidebar-nav">
        {NAV.filter(n => n.part === 1).map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-section-label" style={{ paddingLeft: 0 }}>Part 2 — Forensics</div>
      <nav className="sidebar-nav">
        <NavLink to="/forensics" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon">🛢️</span>
          Spill Investigation
        </NavLink>
        <NavLink to="/spillsplit" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon">🔀</span>
          SpillSplit
        </NavLink>
        <NavLink to="/drift" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon">🌊</span>
          Drift Forecast
        </NavLink>
        <NavLink to="/investigation" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon">🔍</span>
          Investigation
        </NavLink>
        <NavLink to="/replay" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon">▶️</span>
          Vessel Replay
        </NavLink>
        <NavLink to="/report" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon">📄</span>
          Case Report
        </NavLink>
      </nav>

      <div className="sidebar-footer">
        <span className="status-dot" />
        Maritime Memory Active
      </div>
    </aside>
  );
}
