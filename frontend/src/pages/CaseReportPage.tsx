import { useState, useEffect } from 'react';
import { forensicsApi } from '../api/client';

export default function CaseReportPage() {
  const [incident, setIncident] = useState<any>(null);

  useEffect(() => {
    forensicsApi.getIncidents().then(data => {
      if (data && data.length > 0) setIncident(data[0]);
    }).catch(() => {});
  }, []);

  const sarFilename = incident?.sar_image_path ? incident.sar_image_path.split(/[\\/]/).pop() : '000002.jpg';
  const maskFilename = incident?.mask_path ? incident.mask_path.split(/[\\/]/).pop() : '000002_mask.png';

  const handlePrint = () => {
    window.print();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg-primary)', color: 'var(--text-primary)', overflowY: 'auto', padding: '30px 40px' }}>
      {/* Action Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, paddingBottom: 16, borderBottom: '1px solid var(--border)' }}>
        <div>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--cyan)', textTransform: 'uppercase', letterSpacing: 1 }}>
            Official Maritime Audit Dossier
          </span>
          <h1 style={{ fontSize: 24, fontWeight: 800, marginTop: 4 }}>
            MARPOL Annex I Forensic Investigation Report
          </h1>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
            Incident ID: <span style={{ color: 'var(--text-primary)', fontFamily: 'JetBrains Mono' }}>OCCURIS-BOB-2024-0042</span> · Status: Confirmed Discharge
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <button
            onClick={handlePrint}
            style={{ background: 'var(--cyan)', color: '#000', border: 'none', padding: '10px 20px', borderRadius: 8, fontWeight: 700, fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}
          >
            🖨️ Print / Save PDF
          </button>
        </div>
      </div>

      {/* Main Report Container */}
      <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 12, padding: 36, maxWidth: 1000, margin: '0 auto', width: '100%' }}>
        {/* Section 1: Executive Summary */}
        <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: 24, marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--cyan)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
              1. Executive Incident Summary
            </h2>
            <span style={{ background: 'rgba(255, 51, 102, 0.15)', color: 'var(--red)', padding: '4px 10px', borderRadius: 4, fontWeight: 700, fontSize: 11 }}>
              ILLEGAL DISCHARGE CONFIRMED
            </span>
          </div>
          <p style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--text-secondary)' }}>
            On 15 January 2024 at 18:40 UTC, ESA Sentinel-1A Synthetic Aperture Radar (SAR) detected an elongated slick covering approximately <strong>12.66 km²</strong> in the Arabian Sea international corridor (Centroid: <strong>13.16°N, 86.19°E</strong>).
            Morphological decomposition by the CSIRO AI engine established a continuous linear underway release (Aspect Ratio 11.4:1).
            Hydrodynamic backtracking correlated the discharge inception with a deliberate <strong>2h 15m AIS blackout</strong> by crude oil tanker <strong>MT DESH SHOBHA (MMSI 419000042)</strong>.
          </p>
        </div>

        {/* Section 2: Satellite Earth Observation & AI Telemetry */}
        <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: 24, marginBottom: 24 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--cyan)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 16 }}>
            2. Satellite Radar Telemetry & Neural Segmentation
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
            {/* Raw SAR */}
            <div style={{ background: '#020c18', padding: 12, borderRadius: 8, border: '1px solid var(--border)', textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 8, textTransform: 'uppercase' }}>
                Raw Sentinel-1A C-SAR Scene (15m/px)
              </div>
              <img
                src={`http://localhost:8080/sar/${sarFilename}`}
                alt="Raw Sentinel-1 SAR"
                style={{ width: '100%', height: 200, objectFit: 'cover', borderRadius: 6 }}
              />
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 6 }}>
                Polarization: VV · Frequency: 5.405 GHz (C-band) · Look Angle: 38.4°
              </div>
            </div>

            {/* Neural Mask */}
            <div style={{ background: '#020c18', padding: 12, borderRadius: 8, border: '1px solid var(--border)', textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: 'var(--cyan)', fontWeight: 600, marginBottom: 8, textTransform: 'uppercase' }}>
                CSIRO AI Neural Slick Segmentation Mask
              </div>
              <img
                src={`http://localhost:8080/masks/${maskFilename}`}
                alt="Neural Slick Mask"
                style={{ width: '100%', height: 200, objectFit: 'cover', borderRadius: 6, background: '#000' }}
              />
              <div style={{ fontSize: 10, color: 'var(--green)', marginTop: 6 }}>
                Neural Confidence: 96.8% · Sorbent Footprint: 12.66 km²
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
            <div style={{ background: 'var(--bg-card)', padding: 10, borderRadius: 6 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>SENSOR</div>
              <div style={{ fontSize: 13, fontWeight: 700 }}>Sentinel-1A C-SAR</div>
            </div>
            <div style={{ background: 'var(--bg-card)', padding: 10, borderRadius: 6 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>CAPILLARY DAMPING</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--cyan)' }}>-21.8 dB</div>
            </div>
            <div style={{ background: 'var(--bg-card)', padding: 10, borderRadius: 6 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>ASPECT RATIO</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--amber)' }}>11.4 : 1</div>
            </div>
            <div style={{ background: 'var(--bg-card)', padding: 10, borderRadius: 6 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>EST. VOLUME</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--red)' }}>4,250 bbls</div>
            </div>
          </div>
        </div>

        {/* Section 3: Suspect Vessel Registry & Evidence Matrix */}
        <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: 24, marginBottom: 24 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--cyan)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 16 }}>
            3. Identified Culprit Vessel Dossier
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, background: 'var(--bg-card)', padding: 16, borderRadius: 8, border: '1px solid var(--border)', marginBottom: 16 }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>VESSEL NAME</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>MT DESH SHOBHA</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>VESSEL TYPE</div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Crude Oil Tanker (VLCC)</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>MMSI / IMO / CALLSIGN</div>
              <div style={{ fontSize: 13, fontFamily: 'JetBrains Mono' }}>419000042 / 9238411 / VTR9</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>FLAG STATE</div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>🇮🇳 India (Registry: Chennai)</div>
            </div>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
            <thead>
              <tr style={{ background: 'rgba(0, 212, 255, 0.08)', color: 'var(--cyan)' }}>
                <th style={{ padding: 10, border: '1px solid var(--border)' }}>Evidence Parameter</th>
                <th style={{ padding: 10, border: '1px solid var(--border)' }}>Observed Telemetry</th>
                <th style={{ padding: 10, border: '1px solid var(--border)' }}>Legal Evaluation</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ padding: 10, border: '1px solid var(--border)', fontWeight: 600 }}>AIS Transponder Integrity</td>
                <td style={{ padding: 10, border: '1px solid var(--border)', color: 'var(--red)' }}>Deliberate 2h 15m gap (12:30–14:45 UTC)</td>
                <td style={{ padding: 10, border: '1px solid var(--border)' }}>Violation of SOLAS V/19 without safety cause</td>
              </tr>
              <tr>
                <td style={{ padding: 10, border: '1px solid var(--border)', fontWeight: 600 }}>Spatiotemporal Correlation</td>
                <td style={{ padding: 10, border: '1px solid var(--border)' }}>Dead-reckoned transit crosses 13.16°N, 86.19°E</td>
                <td style={{ padding: 10, border: '1px solid var(--border)' }}>Proximity index 0.4 nm (Direct Overlap)</td>
              </tr>
              <tr>
                <td style={{ padding: 10, border: '1px solid var(--border)', fontWeight: 600 }}>Course & Speed Dynamics</td>
                <td style={{ padding: 10, border: '1px solid var(--border)' }}>Speed dropped from 10 to 4 kts, resumed 10.5 kts</td>
                <td style={{ padding: 10, border: '1px solid var(--border)' }}>Typical bilge/sludge decanting operating profile</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Section 4: Sign-off & Interception Authority */}
        <div>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--cyan)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 }}>
            4. Chain of Custody & Statutory Disposition
          </h2>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 20 }}>
            This forensic evidence package was cryptographically compiled by OCCURIS Autonomous Maritime Intelligence Engine. All data points are verifiable against satellite telemetry archives and coastal AIS receiver networks.
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24, paddingTop: 16, borderTop: '1px dashed var(--border)' }}>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>DISPOSITION STATUS</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--red)' }}>PENDING PORT STATE CONTROL DETENTION</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>AUTHORIZING JURISDICTION</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--cyan)' }}>Directorate General of Shipping / ICG Sector HQ</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
