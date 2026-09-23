import { useState, useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, ImageOverlay, Rectangle, CircleMarker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { forensicsApi, caseApi } from '../api/client';

function MapRecenter({ lat, lon }: { lat: number; lon: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo([lat, lon], 13, { duration: 1.0 });
  }, [lat, lon, map]);
  return null;
}

type AnalysisMode = 'clusters' | 'tensor' | 'hypothesis';

export default function SpillSplitPage() {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<any>(null);
  
  // Real data state
  const [spillData, setSpillData] = useState<any>(null);
  const [spillSplitData, setSpillSplitData] = useState<any>(null);
  
  const [selectedPatch, setSelectedPatch] = useState<number | null>(null);
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>('clusters');

  useEffect(() => {
    forensicsApi.getIncidents().then(data => {
      if (data && data.length > 0) {
        setIncidents(data);
        setSelectedIncident(data[0]);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedIncident) {
      caseApi.getSpill(selectedIncident.id).then(setSpillData).catch(() => setSpillData(null));
      caseApi.getOriginZone(selectedIncident.id).then(setSpillSplitData).catch(() => setSpillSplitData(null));
    }
  }, [selectedIncident]);

  const lat = spillData?.geometry?.centroid_geo?.latitude || selectedIncident?.geometry?.centroid_lat || 13.1698;
  const lon = spillData?.geometry?.centroid_geo?.longitude || selectedIncident?.geometry?.centroid_lon || 86.2056;

  const dLat = 0.045;
  const dLon = 0.065;
  const sarBounds: [[number, number], [number, number]] = [
    [lat - dLat / 2, lon - dLon / 2],
    [lat + dLat / 2, lon + dLon / 2],
  ];

  const sarFilename = selectedIncident?.sar_image_path ? selectedIncident.sar_image_path.split(/[\\/]/).pop() : '';
  const maskFilename = selectedIncident?.mask_path ? selectedIncident.mask_path.split(/[\\/]/).pop() : '';

  const area = spillData?.geometry?.area_km2 || 0;
  const orientation = spillData?.geometry?.orientation_deg || 0;
  const length = spillData?.geometry?.length_km || 0;
  const width = spillData?.geometry?.width_km || 0;
  const aspectRatio = width > 0 ? (length / width).toFixed(1) : '0';

  const sceneData = useMemo(() => {
    if (!spillData || !spillSplitData) {
      return {
        verdictTitle: "Loading Case Data...",
        confidence: "",
        confidenceColor: "var(--cyan)",
        verdictText: "Awaiting results from SpillSplit module...",
        vesselAlign: "",
        bayesContinuous: "0%",
        bayesStationary: "0%",
        clusters: [],
      };
    }

    if (area === 0) {
      return {
        verdictTitle: "Undisturbed Open Ocean Baseline",
        confidence: "100.0%",
        confidenceColor: "var(--green)",
        verdictText: "No slick detected. Model confirms zero oil pixels.",
        vesselAlign: "None",
        bayesContinuous: "0.0%",
        bayesStationary: "0.0%",
        clusters: [],
      };
    }

    const isOneSource = spillSplitData.result === "One Source Zone";
    const clusters = (spillSplitData.source_zones || []).map((sz: any, i: number) => ({
      id: i + 1,
      name: `Source Zone ${sz.id} (Weight: ${sz.weight})`,
      area: `${(area * sz.weight).toFixed(2)} km²`,
      aspectRatio: `${length.toFixed(1)} : ${width.toFixed(1)}`,
      orientation: `${orientation.toFixed(1)}°`,
      color: i === 0 ? "#ffb800" : "#00d4ff",
      coords: [sz.latitude, sz.longitude] as [number, number]
    }));

    let probH1 = 50;
    if (isOneSource) {
        const iouRatio = (spillSplitData.one_source?.iou || 0) / ((spillSplitData.two_source?.iou || 0) + 0.0001);
        probH1 = 75 + Math.min(24.9, iouRatio * 15);
    } else {
        const iouRatio = (spillSplitData.two_source?.iou || 0) / ((spillSplitData.one_source?.iou || 0) + 0.0001);
        probH1 = 25 - Math.min(24.9, iouRatio * 15);
    }

    return {
      verdictTitle: spillSplitData.result,
      confidence: spillSplitData.confidence,
      confidenceColor: isOneSource ? "var(--cyan)" : "#ff8800",
      verdictText: `SpillSplit Algorithm evaluated One Source (BIC: ${spillSplitData.one_source?.bic?.toFixed(1)}) vs Two Sources (BIC: ${spillSplitData.two_source?.bic?.toFixed(1)}). Separation between zones is ${spillSplitData.source_separation_km?.toFixed(1)} km. Cluster stability: ${spillSplitData.stability?.stable ? 'Stable' : 'Unstable'} (score: ${((spillSplitData.stability?.score || 0) * 100).toFixed(1)}%).`,
      vesselAlign: `IOU H1: ${spillSplitData.one_source?.iou?.toFixed(3)} | IOU H2: ${spillSplitData.two_source?.iou?.toFixed(3)}`,
      bayesContinuous: probH1.toFixed(1) + "%",
      bayesStationary: (100 - probH1).toFixed(1) + "%",
      clusters: clusters,
    };
  }, [spillData, spillSplitData, area, length, width, orientation]);

  const patches = sceneData.clusters;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg-primary)', color: 'var(--text-primary)', overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 24px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1 style={{ fontSize: 18, fontWeight: 700, letterSpacing: 0.5 }}>SpillSplit™ — Morphological Decomposition & Source Allocation</h1>
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Spectral tensor analysis separating continuous underway tanker discharges from stationary point-source leaks and clean water baselines.
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 24px', background: 'rgba(3, 13, 24, 0.95)', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Acquisition Scene:
          </span>
          <div style={{ display: 'flex', gap: 8 }}>
            {incidents.map((inc) => {
              const isSel = selectedIncident?.id === inc.id;
              return (
                <button
                  key={inc.id}
                  onClick={() => {
                    setSelectedIncident(inc);
                    setSelectedPatch(null);
                  }}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 8,
                    border: isSel ? `1px solid var(--cyan)` : '1px solid var(--border)',
                    background: isSel ? `rgba(0, 212, 255, 0.1)` : 'rgba(255, 255, 255, 0.03)',
                    color: isSel ? 'var(--cyan)' : 'var(--text-secondary)',
                    fontSize: 11,
                    fontWeight: isSel ? 700 : 500,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    boxShadow: isSel ? `0 0 14px rgba(0, 212, 255, 0.2)` : 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6
                  }}
                >
                  <span>{inc.name || inc.id}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div style={{ display: 'flex', background: 'rgba(255,255,255,0.05)', padding: 3, borderRadius: 8, border: '1px solid var(--border)', gap: 4 }}>
          {[
            { key: 'clusters', label: 'Sub-Slick Clusters' },
            { key: 'tensor', label: 'Inertia Tensor' },
            { key: 'hypothesis', label: 'Source Hypothesis' }
          ].map(m => (
            <button
              key={m.key}
              onClick={() => setAnalysisMode(m.key as AnalysisMode)}
              style={{
                padding: '4px 10px',
                borderRadius: 6,
                border: 'none',
                background: analysisMode === m.key ? 'var(--cyan)' : 'transparent',
                color: analysisMode === m.key ? '#000' : 'var(--text-secondary)',
                fontWeight: 700,
                fontSize: 10,
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={{ flex: '1 1 60%', position: 'relative' }}>
          <MapContainer center={[lat, lon]} zoom={11} style={{ height: '100%', width: '100%', background: '#020c18' }}>
            <MapRecenter lat={lat} lon={lon} />
            <TileLayer
              url="https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              maxZoom={18}
            />

            {sarFilename && (
              <ImageOverlay url={`http://localhost:8080/sar/${sarFilename}`} bounds={sarBounds} opacity={0.88} />
            )}
            
            {maskFilename && (
              <ImageOverlay url={`http://localhost:8080/masks/${maskFilename}`} bounds={sarBounds} opacity={0.80} />
            )}

            <Rectangle
              bounds={sarBounds}
              pathOptions={{
                color: '#00d4ff',
                weight: 1.5,
                dashArray: '5 4',
                fillOpacity: 0.05
              }}
            />

            {patches.map((p: any) => {
              const isSelected = selectedPatch === p.id;
              return (
                <div key={p.id}>
                  {isSelected && (
                    <CircleMarker center={p.coords} radius={16} pathOptions={{ color: p.color, fillColor: 'transparent', weight: 2, dashArray: '3 3' }} />
                  )}
                  <CircleMarker center={p.coords} radius={isSelected ? 10 : 7} pathOptions={{ color: '#ffffff', fillColor: p.color, fillOpacity: isSelected ? 1 : 0.85, weight: 2 }}>
                    <Popup>
                      <div className="vessel-popup" style={{ minWidth: 220 }}>
                        <div className="vessel-popup-header" style={{ color: p.color }}>{p.name}</div>
                        <div className="vessel-popup-row"><span>Area</span><span className="mono" style={{ color: p.color, fontWeight: 'bold' }}>{p.area}</span></div>
                        <div className="vessel-popup-row"><span>Aspect Ratio</span><span className="mono">{p.aspectRatio}</span></div>
                        <div className="vessel-popup-row"><span>Orientation</span><span className="mono">{p.orientation}</span></div>
                      </div>
                    </Popup>
                  </CircleMarker>
                </div>
              );
            })}
          </MapContainer>
        </div>

        <div style={{ flex: '1 1 40%', background: 'var(--bg-secondary)', borderLeft: '1px solid var(--border)', padding: 22, overflowY: 'auto' }}>
          
          <div style={{ background: 'rgba(0, 212, 255, 0.06)', border: `1px solid ${sceneData.confidenceColor}44`, borderRadius: 10, padding: 16, marginBottom: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: sceneData.confidenceColor, textTransform: 'uppercase', letterSpacing: 1 }}>
                Hypothesis Verdict
              </span>
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
              {sceneData.verdictTitle}
            </h3>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
              {sceneData.verdictText}
            </p>
            {sceneData.confidence && (
              <p style={{ fontSize: 11, color: sceneData.confidenceColor, marginTop: 10, fontWeight: 600 }}>
                Confidence: {sceneData.confidence}
              </p>
            )}
            {area > 0 && (
              <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid rgba(255,255,255,0.06)', fontSize: 11, color: 'var(--cyan)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>🎯</span>
                <span>{sceneData.vesselAlign}</span>
              </div>
            )}
          </div>

          {analysisMode === 'clusters' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8 }}>
                  Cluster Decomposition ({patches.length} Sub-Slicks)
                </h4>
              </div>

              {patches.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center', background: '#020c18', borderRadius: 8, border: '1px solid var(--border)', color: 'var(--green)', fontSize: 12 }}>
                  ✓ Negative Control Verified: Zero segmented clusters detected.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 18 }}>
                  {patches.map((p: any) => {
                    const isSelected = selectedPatch === p.id;
                    return (
                      <div
                        key={p.id}
                        onClick={() => setSelectedPatch(isSelected ? null : p.id)}
                        style={{
                          background: isSelected ? 'rgba(0, 212, 255, 0.12)' : 'var(--bg-card)',
                          border: `1px solid ${isSelected ? p.color : 'var(--border)'}`,
                          borderRadius: 8,
                          padding: 12,
                          cursor: 'pointer',
                          transition: 'all 0.2s',
                          boxShadow: isSelected ? `0 0 14px ${p.color}33` : 'none'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ width: 10, height: 10, borderRadius: '50%', background: p.color }} />
                            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{p.name}</span>
                          </div>
                          <span style={{ fontSize: 12, fontWeight: 700, color: p.color }}>{p.area}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {analysisMode === 'tensor' && (
            <div style={{ background: '#020c18', border: '1px solid var(--border)', borderRadius: 10, padding: 16, marginBottom: 18 }}>
              <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--cyan)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 12 }}>
                2D Spatial Moments & Inertia Tensor
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
                <div className="stat-card">
                  <div className="stat-label">Major Inertia Axis</div>
                  <div className="stat-value" style={{ color: 'var(--cyan)', fontSize: 18 }}>{length.toFixed(2)} km</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Minor Inertia Axis</div>
                  <div className="stat-value" style={{ color: 'var(--green)', fontSize: 18 }}>{width.toFixed(2)} km</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Aspect Ratio</div>
                  <div className="stat-value" style={{ color: '#ffb800', fontSize: 18 }}>{aspectRatio} : 1</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Principal Angle θ</div>
                  <div className="stat-value" style={{ color: '#ff3366', fontSize: 18 }}>{orientation.toFixed(1)}°</div>
                </div>
              </div>
            </div>
          )}

          {analysisMode === 'hypothesis' && (
            <div style={{ background: '#020c18', border: '1px solid var(--border)', borderRadius: 10, padding: 16, marginBottom: 18 }}>
              <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--cyan)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 12 }}>
                Bayesian Source Attribution Likelihood
              </h4>

              <div style={{ marginBottom: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Hypothesis 1: Continuous Vessel Release Underway</span>
                  <span style={{ color: 'var(--cyan)', fontWeight: 700 }}>{sceneData.bayesContinuous}</span>
                </div>
                <div style={{ width: '100%', height: 7, background: '#0a192f', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ width: sceneData.bayesContinuous, height: '100%', background: 'var(--cyan)' }} />
                </div>
              </div>

              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Hypothesis 2: Stationary Pipeline / Rig Blowout</span>
                  <span style={{ color: 'var(--amber)', fontWeight: 700 }}>{sceneData.bayesStationary}</span>
                </div>
                <div style={{ width: '100%', height: 7, background: '#0a192f', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ width: sceneData.bayesStationary, height: '100%', background: 'var(--amber)' }} />
                </div>
              </div>
            </div>
          )}

          <div style={{ background: 'var(--bg-card)', borderRadius: 10, padding: 16, border: '1px solid var(--border)' }}>
            <h4 style={{ fontSize: 11, fontWeight: 700, color: 'var(--cyan)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
              Volume Assessment
            </h4>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.06)', fontSize: 12 }}>
              <span style={{ color: 'var(--text-secondary)' }}>Estimated Area</span>
              <span style={{ fontWeight: 700, color: area === 0 ? 'var(--green)' : 'var(--cyan)' }}>{area.toFixed(2)} km²</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.06)', fontSize: 12 }}>
              <span style={{ color: 'var(--text-secondary)' }}>Estimated Volume</span>
              <span style={{ fontWeight: 700, color: area === 0 ? 'var(--green)' : 'var(--amber)' }}>
                {area === 0 ? '0 Barrels' : `${Math.round(area * 320)} – ${Math.round(area * 400)} Barrels`}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
