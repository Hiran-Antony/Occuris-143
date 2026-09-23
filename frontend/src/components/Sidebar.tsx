import { NavLink } from 'react-router-dom';
import { Map, Brain, Droplets, Network, Wind, Search, Play, FileText } from 'lucide-react';

const NAV = [
  { to: '/monitoring', icon: <Map size={18} />, label: 'Regional Monitoring', part: 1 },
  { to: '/memory',     icon: <Brain size={18} />, label: 'Maritime Memory',     part: 1 },
  { to: '/spill',      icon: <Droplets size={18} />,  label: 'Spill Detection',    part: 2 },
  { to: '/spillsplit', icon: <Network size={18} />, label: 'SpillSplit',          part: 2 },
  { to: '/drift',      icon: <Wind size={18} />, label: 'Drift Forecast',      part: 2 },
  { to: '/incident',   icon: <Search size={18} />, label: 'Investigation',       part: 2 },
  { to: '/replay',     icon: <Play size={18} />,  label: 'Vessel Replay',      part: 2 },
  { to: '/report',     icon: <FileText size={18} />, label: 'Case Report',         part: 2 },
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

      <div className="sidebar-section-label">Part 2 — Forensics</div>
      <nav className="sidebar-nav">
        <NavLink to="/forensics" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon"><Droplets size={18} /></span>
          Spill Investigation
        </NavLink>
        <NavLink to="/spillsplit" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon"><Network size={18} /></span>
          SpillSplit
        </NavLink>
        <NavLink to="/drift" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon"><Wind size={18} /></span>
          Drift Forecast
        </NavLink>
        <NavLink to="/investigation" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon"><Search size={18} /></span>
          Investigation
        </NavLink>
        <NavLink to="/replay" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon"><Play size={18} /></span>
          Vessel Replay
        </NavLink>
        <NavLink to="/report" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon"><FileText size={18} /></span>
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
