import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import RegionalMonitoring from './pages/RegionalMonitoring';
import MaritimeMemory from './pages/MaritimeMemory';
import { ForensicInvestigation } from './pages/ForensicInvestigation';
import SpillSplitPage from './pages/SpillSplitPage';
import DriftForecastPage from './pages/DriftForecastPage';
import DarkVesselInvestigationPage from './pages/DarkVesselInvestigationPage';
import VesselReplayPage from './pages/VesselReplayPage';
import CaseReportPage from './pages/CaseReportPage';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/monitoring" replace />} />
            <Route path="/monitoring" element={<RegionalMonitoring />} />
            <Route path="/memory"     element={<MaritimeMemory />} />
            <Route path="/forensics"  element={<ForensicInvestigation />} />
            <Route path="/spill"      element={<ForensicInvestigation />} />
            <Route path="/spillsplit" element={<SpillSplitPage />} />
            <Route path="/drift"      element={<DriftForecastPage />} />
            <Route path="/investigation" element={<DarkVesselInvestigationPage />} />
            <Route path="/incident"   element={<DarkVesselInvestigationPage />} />
            <Route path="/replay"     element={<VesselReplayPage />} />
            <Route path="/report"     element={<CaseReportPage />} />
            <Route path="*"           element={<Navigate to="/monitoring" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

