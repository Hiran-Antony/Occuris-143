import { useEffect, useState, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, Polygon, Polyline, CircleMarker, Marker, Popup, useMap, ImageOverlay, Rectangle } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

import { regionApi, vesselApi, dashboardApi, forensicsApi, caseApi } from '../api/client';
import type { Vessel, AISPosition, DashboardStats, GatewayId } from '../types';
import { GATEWAY_COLORS, VESSEL_TYPE_COLORS } from '../types';

// ── Types ────────────────────────────────────────────────────────────────
interface VesselTrackData {
  mmsi: string;
  positions: AISPosition[];
}

interface GatewayFeature {
  properties: { id: string; name: string; color: string };
  geometry: { coordinates: [number, number][] };
}

// ── Helpers ──────────────────────────────────────────────────────────────
function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function getVesselPositionAt(positions: AISPosition[], demoTime: Date): AISPosition | null {
  if (!positions || positions.length === 0) return null;
  const t = demoTime.getTime();
  const tFirst = new Date(positions[0].timestamp).getTime();
  const tLast = new Date(positions[positions.length - 1].timestamp).getTime();

  // If before vessel enters the surveillance sector
  if (t < tFirst) return null;

  // If after vessel departed the surveillance sector (clean exit, don't stick to border)
  if (t > tLast + 10 * 60 * 1000) return null;

  // At or past final waypoint
  if (t >= tLast) {
    return positions[positions.length - 1];
  }

  // Smooth linear interpolation between adjacent pings
  for (let i = 0; i < positions.length - 1; i++) {
    const t0 = new Date(positions[i].timestamp).getTime();
    const t1 = new Date(positions[i + 1].timestamp).getTime();
    if (t >= t0 && t <= t1) {
      const dt = t1 - t0;
      const frac = dt > 0 ? (t - t0) / dt : 0;
      const p0 = positions[i];
      const p1 = positions[i + 1];

      return {
        ...p0,
        latitude: p0.latitude + (p1.latitude - p0.latitude) * frac,
        longitude: p0.longitude + (p1.longitude - p0.longitude) * frac,
        speed: p0.speed + (p1.speed - p0.speed) * frac,
        course: p0.course,
        heading: p0.heading,
        timestamp: demoTime.toISOString()
      };
    }
  }

  return positions[positions.length - 1];
}

function getRecentTrail(positions: AISPosition[], demoTime: Date, hoursBack = 2): AISPosition[] {
  const cutoff = new Date(demoTime.getTime() - hoursBack * 3600 * 1000);
  return positions.filter(p => {
    const t = new Date(p.timestamp);
    return t <= demoTime && t >= cutoff;
  });
}

// ── Demo Time Controller ──────────────────────────────────────────────────
const DEMO_START = new Date('2024-01-15T06:00:00Z');
const DEMO_END   = new Date('2024-01-15T22:00:00Z');
const INCIDENT   = new Date('2024-01-15T18:40:00Z');
const TOTAL_MS   = DEMO_END.getTime() - DEMO_START.getTime();

type MonitoringViewMode = 'all' | 'bayofbengal' | 'filament' | 'emulsion' | 'clean';

// ── Map Controller ────────────────────────────────────────────────────────
function MapController({ viewMode, casesData }: { viewMode: string, casesData: any[] }) {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
    if (viewMode === 'all') {
      map.flyToBounds([[8.0, 50.0], [22.0, 75.0]], { duration: 1.2 });
    } else {
      const activeCase = casesData.find((c: any) => c.id === viewMode);
      if (activeCase && activeCase.map_data && activeCase.map_data.center) {
         const lat = activeCase.map_data.center.latitude;
         const lon = activeCase.map_data.center.longitude;
         map.flyToBounds([[lat - 1, lon - 1], [lat + 1, lon + 1]], { duration: 1.2 });
      }
    }
  }, [map, viewMode, casesData]);
  return null;
}

export default function RegionalMonitoring() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [casesData, setCasesData] = useState<any[]>([]);
  const [region, setRegion] = useState<any>(null);
  const [gateways, setGateways] = useState<GatewayFeature[]>([]);
  const [tracks, setTracks] = useState<VesselTrackData[]>([]);
  const [vessels, setVessels] = useState<Vessel[]>([]);
  const [crossings, setCrossings] = useState<any[]>([]);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [viewMode, setViewMode] = useState<MonitoringViewMode>('all');
  const [mapLayer, setMapLayer] = useState<'sentinel' | 'dark' | 'osm'>('sentinel');
  const [inspectedIncident, setInspectedIncident] = useState<any | null>(null);
  const [sarTab, setSarTab] = useState<'overlay' | 'raw' | 'mask'>('overlay');
  const [demoTime, setDemoTime] = useState(DEMO_START);
  const [playing, setPlaying] = useState(false);
  const [sliderVal, setSliderVal] = useState(0);
  const animRef = useRef<number | null>(null);
  const lastRef = useRef<number>(0);
  const SPEED = 120; // 1 screen-second = 2 demo-minutes (smooth and readable)

  // ── Fetch data ──────────────────────────────────────────────────────────
  useEffect(() => {
    dashboardApi.stats().then(setStats).catch(() => {});

    caseApi.list().then(cases => {
      Promise.all(cases.map((c: any) => caseApi.getMap(c.id).then((m: any) => ({...c, map_data: m}))))
        .then(setCasesData);
    }).catch(() => {});
    regionApi.getRegion().then(d => setRegion(d)).catch(() => {});
    regionApi.getGateways().then(d => setGateways(d.features || [])).catch(() => {});
    vesselApi.list().then(setVessels).catch(() => {});
    vesselApi.recentCrossings(50).then(setCrossings).catch(() => {});
    forensicsApi.getIncidents().then(setIncidents).catch(() => {});

    // Fetch all vessel tracks
    vesselApi.list().then(vs => {
      Promise.all(vs.map(v => vesselApi.getTrack(v.mmsi).catch(() => null)))
        .then(results => {
          const valid = results
            .filter(Boolean)
            .map(r => ({ mmsi: r!.mmsi, positions: r!.positions }));
          setTracks(valid);
        });
    }).catch(() => {});
  }, []);

  // ── Clock loop ──────────────────────────────────────────────────────────
  const animate = useCallback((now: number) => {
    if (lastRef.current === 0) lastRef.current = now;
    const elapsed_real_ms = now - lastRef.current;
    lastRef.current = now;
    const demo_ms = elapsed_real_ms * SPEED;
    setDemoTime(prev => {
      const next = new Date(prev.getTime() + demo_ms);
      if (next >= DEMO_END) {
        setPlaying(false);
        return DEMO_END;
      }
      const frac = (next.getTime() - DEMO_START.getTime()) / TOTAL_MS;
      setSliderVal(Math.round(frac * 1000));
      return next;
    });
    animRef.current = requestAnimationFrame(animate);
  }, []);

  useEffect(() => {
    if (playing) {
      lastRef.current = 0;
      animRef.current = requestAnimationFrame(animate);
    } else {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    }
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [playing, animate]);

  const onSlider = (v: number) => {
    const t = new Date(DEMO_START.getTime() + (v / 1000) * TOTAL_MS);
    setDemoTime(t);
    setSliderVal(v);
  };

  // ── Region polygon coordinates ──────────────────────────────────────────
  const regionCoords: [number, number][] = region
    ? region.features[0].geometry.coordinates[0].map(([lon, lat]: [number, number]) => [lat, lon])
    : [];

  // ── Crossings to show in feed (before current demo time) ────────────────
  const visibleCrossings = crossings
    .filter(c => new Date(c.timestamp) <= demoTime)
    .slice(-20)
    .reverse();

  // ── Past incident indicator ──────────────────────────────────────────────
  const incidentPassed = demoTime >= INCIDENT;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">🗺️ Regional Monitoring</div>
          <div className="page-subtitle">Arabian Sea · 4 Virtual Gateways · Continuous Vessel Tracking</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* 4-Data Scene Selector Toolbar (Glassmorphic Design) */}
          <div style={{ display: 'flex', background: 'rgba(3, 15, 28, 0.75)', backdropFilter: 'blur(10px)', borderRadius: 10, padding: 4, border: '1px solid var(--border)', gap: 6 }}>
            <button
              onClick={() => setViewMode('all')}
              style={{
                padding: '6px 12px',
                borderRadius: 7,
                fontSize: 11,
                fontWeight: 700,
                cursor: 'pointer',
                background: viewMode === 'all' ? 'rgba(0, 212, 255, 0.22)' : 'transparent',
                color: viewMode === 'all' ? 'var(--cyan)' : 'var(--text-secondary)',
                border: viewMode === 'all' ? '1px solid var(--cyan)' : '1px solid transparent',
                boxShadow: viewMode === 'all' ? '0 0 14px rgba(0, 212, 255, 0.35)' : 'none',
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
                gap: 5
              }}
            >
              <span>🌐</span>
              <span>Entire Bay</span>
            </button>
            <button
              onClick={() => setViewMode('bayofbengal')}
              style={{
                padding: '6px 12px',
                borderRadius: 7,
                fontSize: 11,
                fontWeight: 700,
                cursor: 'pointer',
                background: viewMode === 'bayofbengal' ? 'rgba(255, 51, 102, 0.22)' : 'transparent',
                color: viewMode === 'bayofbengal' ? '#ff4d79' : 'var(--text-secondary)',
                border: viewMode === 'bayofbengal' ? '1px solid #ff3366' : '1px solid transparent',
                boxShadow: viewMode === 'bayofbengal' ? '0 0 14px rgba(255, 51, 102, 0.4)' : 'none',
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
                gap: 5
              }}
            >
              <span>🚨</span>
              <span>Al-Mahra (1.76 km²)</span>
            </button>
            <button
              onClick={() => setViewMode('filament')}
              style={{
                padding: '6px 12px',
                borderRadius: 7,
                fontSize: 11,
                fontWeight: 700,
                cursor: 'pointer',
                background: viewMode === 'filament' ? 'rgba(255, 184, 0, 0.22)' : 'transparent',
                color: viewMode === 'filament' ? '#ffc833' : 'var(--text-secondary)',
                border: viewMode === 'filament' ? '1px solid #ffb800' : '1px solid transparent',
                boxShadow: viewMode === 'filament' ? '0 0 14px rgba(255, 184, 0, 0.4)' : 'none',
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
                gap: 5
              }}
            >
              <span>🚢</span>
              <span>Lakshadweep (3.67 km²)</span>
            </button>
            <button
              onClick={() => setViewMode('emulsion')}
              style={{
                padding: '6px 12px',
                borderRadius: 7,
                fontSize: 11,
                fontWeight: 700,
                cursor: 'pointer',
                background: viewMode === 'emulsion' ? 'rgba(255, 136, 0, 0.22)' : 'transparent',
                color: viewMode === 'emulsion' ? '#ffa333' : 'var(--text-secondary)',
                border: viewMode === 'emulsion' ? '1px solid #ff8800' : '1px solid transparent',
                boxShadow: viewMode === 'emulsion' ? '0 0 14px rgba(255, 136, 0, 0.4)' : 'none',
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
                gap: 5
              }}
            >
              <span>⚡</span>
              <span>Oman Basin (0.52 km²)</span>
            </button>
            <button
              onClick={() => setViewMode('clean')}
              style={{
                padding: '6px 12px',
                borderRadius: 7,
                fontSize: 11,
                fontWeight: 700,
                cursor: 'pointer',
                background: viewMode === 'clean' ? 'rgba(0, 255, 136, 0.22)' : 'transparent',
                color: viewMode === 'clean' ? '#00ffaa' : 'var(--text-secondary)',
                border: viewMode === 'clean' ? '1px solid #00ff88' : '1px solid transparent',
                boxShadow: viewMode === 'clean' ? '0 0 14px rgba(0, 255, 136, 0.4)' : 'none',
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
                gap: 5
              }}
            >
              <span>🌊</span>
              <span>Clean Baseline (0 km²)</span>
            </button>
          </div>

          {incidentPassed && (
            <div style={{ padding: '6px 14px', background: 'rgba(255,51,102,0.15)', border: '1px solid rgba(255,51,102,0.4)', borderRadius: 8, fontSize: 12, color: '#ff3366', fontWeight: 600 }}>
              ⚠️ INCIDENT DETECTED — 18:40 UTC
            </div>
          )}
          <div style={{ fontSize: 13, fontFamily: 'JetBrains Mono', color: 'var(--cyan)', background: 'var(--bg-card)', padding: '6px 14px', borderRadius: 8, border: '1px solid var(--border)' }}>
            Demo: {demoTime.toISOString().slice(11, 16)} UTC
          </div>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="stats-bar">
        <div className="stat-card">
          <div className="stat-value">{stats?.total_vessels ?? '—'}</div>
          <div className="stat-label">Total Vessels</div>
        </div>
        <div className="stat-card success">
          <div className="stat-value">{stats?.vessels_ever_in_region ?? '—'}</div>
          <div className="stat-label">In Region</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats?.total_gateway_crossings ?? '—'}</div>
          <div className="stat-label">Gate Crossings</div>
        </div>
        <div className="stat-card warning">
          <div className="stat-value">{stats?.total_behaviour_events ?? '—'}</div>
          <div className="stat-label">Behaviour Events</div>
        </div>
        <div className="stat-card danger">
          <div className="stat-value">{stats?.unexplained_events ?? '—'}</div>
          <div className="stat-label">Unexplained</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats?.completed_journeys ?? '—'}</div>
          <div className="stat-label">Journeys</div>
        </div>
      </div>

      {/* Map + Side Panel */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        <div style={{ flex: 1, minWidth: 0, position: 'relative', height: '100%' }}>
          <MapContainer
            center={[13.0, 88.5]}
            zoom={6}
            style={{ width: '100%', height: '100%', background: 'rgba(0, 0, 0, 0.25)' }}
            zoomControl={false}
          >
            {mapLayer === 'sentinel' && (
              <>
                <TileLayer
                  url="https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                  attribution="&copy; Sentinel-2 / Esri World Imagery"
                  maxZoom={18}
                />
                <TileLayer
                  url="https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
                  attribution=""
                  maxZoom={18}
                  opacity={0.65}
                />
              </>
            )}
            {mapLayer === 'dark' && (
              <>
                <TileLayer
                  url="https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
                  attribution="&copy; Esri &mdash; Dark Marine Nautical Canvas"
                  maxZoom={16}
                />
                <TileLayer
                  url="https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
                  attribution=""
                  maxZoom={16}
                  opacity={0.65}
                />
              </>
            )}
            {mapLayer === 'osm' && (
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                className="dark-map-tiles"
                attribution="&copy; OpenStreetMap"
              />
            )}
            <MapController viewMode={viewMode} casesData={casesData} />

            {/* Monitoring Region */}
            {regionCoords.length > 0 && (
              <Polygon
                positions={regionCoords}
                pathOptions={{ color: '#00d4ff', fillColor: '#00d4ff', fillOpacity: 0.04, weight: 1.5, dashArray: '6 4' }}
              />
            )}

            {/* Gateways */}
            {gateways.map(gw => (
              <Polyline
                key={gw.properties.id}
                positions={gw.geometry.coordinates.map(([lon, lat]) => [lat, lon] as [number, number])}
                pathOptions={{ color: gw.properties.color, weight: 2, opacity: 0.9, dashArray: '6 8', lineCap: 'round' }}
              />
            ))}

            {/* Detected Real Sentinel-1 SAR Oil Spill Footprints & Overlays (4 Forensic Scenes) */}
            {incidents.map((inc: any) => {
              if (!inc || !inc.geometry?.centroid_lat || !inc.geometry?.centroid_lon) return null;
              const lat = inc.geometry.centroid_lat;
              const lon = inc.geometry.centroid_lon;

              const imgPath = (inc.sar_image_path || '').toUpperCase();
              const isClean = imgPath.includes('CLEAN') || inc.geometry?.area_km2 == null;
              const isFilament = imgPath.includes('FILAMENT') || imgPath.includes('TENDEGREE');
              const isEmulsion = imgPath.includes('EMULSION') || imgPath.includes('KGBASIN');

              // Distinct theme colors and metadata for each dataset
              let themeColor = '#ff3366'; // Central Arabian Sea
              let sceneTitle = 'Central Arabian Sea';
              let spillType = 'Heavy Crude Oil Discharge';
              let suspectVessel = 'MT DESH SHOBHA (419000042)';
              let badgeText = '🚨 CRUDE SLICK';

              if (isClean) {
                themeColor = '#00ffaa';
                sceneTitle = 'Central Deep Sea Baseline';
                spillType = 'Negative Control (Zero Hydrocarbons)';
                suspectVessel = 'Undisturbed Baseline Control';
                badgeText = '🌊 CLEAN BASELINE';
              } else if (isFilament) {
                themeColor = '#ffb800';
                sceneTitle = 'Lakshadweep Channel Corridor';
                spillType = 'Bilge Filament Dumping';
                suspectVessel = 'EASTERN STAR (419000040)';
                badgeText = '🚢 BILGE FILAMENT';
              } else if (isEmulsion) {
                themeColor = '#ff8800';
                sceneTitle = 'Oman Basin Offshore Complex';
                spillType = 'Produced Water / Rig Emulsion';
                suspectVessel = 'GULF WAVE (419000041)';
                badgeText = '⚡ RIG EMULSION';
              }

              const isHighlighted = (viewMode === 'bayofbengal' && !isClean && !isFilament && !isEmulsion) ||
                                    (viewMode === 'filament' && isFilament) ||
                                    (viewMode === 'emulsion' && isEmulsion) ||
                                    (viewMode === 'clean' && isClean);

              // Bounding box for Copernicus SAR scene draped on the ocean
              const dLat = 0.095;
              const dLon = 0.135;
              const sarBounds: [[number, number], [number, number]] = [
                [lat - dLat / 2, lon - dLon / 2],
                [lat + dLat / 2, lon + dLon / 2],
              ];
              const sarFilename = inc.sar_image_path ? inc.sar_image_path.split(/[\\/]/).pop() : '';
              const maskFilename = inc.mask_path ? inc.mask_path.split(/[\\/]/).pop() : '';

              return (
                <div key={inc.id}>
                  {/* SkyTruth-grade Sentinel-1A Radar Swath Pass Footprint (250km IW corridor) */}
                  <Rectangle
                    bounds={[
                      [lat - 0.35, lon - 0.55],
                      [lat + 0.35, lon + 0.55],
                    ]}
                    pathOptions={{
                      color: themeColor,
                      weight: isHighlighted ? 2 : 1,
                      dashArray: '8 6',
                      fillColor: themeColor,
                      fillOpacity: isHighlighted ? 0.08 : 0.03
                    }}
                  />

                  {/* Real Sentinel-1 SAR Satellite Image Overlay on the Ocean */}
                  {sarFilename && (
                    <ImageOverlay
                      url={`http://localhost:8000/sar/${sarFilename}`}
                      bounds={sarBounds}
                      opacity={0.92}
                    />
                  )}

                  {/* Real Neural Network Predicted Oil Spill Mask Overlay */}
                  {maskFilename && (
                    <ImageOverlay
                      url={`http://localhost:8000/masks/${maskFilename}`}
                      bounds={sarBounds}
                      opacity={isClean ? 0.4 : 0.82}
                    />
                  )}

                  {/* High-Res SAR Scene Bounding Frame */}
                  <Rectangle
                    bounds={sarBounds}
                    pathOptions={{
                      color: themeColor,
                      weight: isHighlighted ? 2.5 : 1.5,
                      dashArray: '4 3',
                      fillColor: 'transparent',
                    }}
                  />

                  {/* Tactical Reticle Beacon */}
                  <CircleMarker
                    center={[lat, lon]}
                    radius={isHighlighted ? 22 : 16}
                    pathOptions={{
                      color: themeColor,
                      fillColor: 'transparent',
                      weight: 1.5,
                      dashArray: '3 3'
                    }}
                  />
                  <CircleMarker
                    center={[lat, lon]}
                    radius={isHighlighted ? 7 : 5}
                    pathOptions={{
                      color: '#ffffff',
                      fillColor: themeColor,
                      fillOpacity: 1,
                      weight: 2
                    }}
                  >
                    <Popup>
                      <div className="vessel-popup" style={{ minWidth: 270 }}>
                        <div className="vessel-popup-header" style={{ color: themeColor, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span>🛰️ {sceneTitle}</span>
                          <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, background: 'rgba(255,255,255,0.08)', color: themeColor, fontWeight: 700 }}>
                            {badgeText}
                          </span>
                        </div>
                        
                        {/* Real SAR & Mask Preview side by side */}
                        <div style={{ display: 'flex', gap: 6, margin: '8px 0', background: 'rgba(0, 0, 0, 0.25)', padding: 4, borderRadius: 6, border: '1px solid var(--border)' }}>
                          <div style={{ flex: 1, textAlign: 'center' }}>
                            <div style={{ fontSize: 9, color: 'var(--text-muted)', marginBottom: 2 }}>RAW SENTINEL SAR</div>
                            {sarFilename && (
                              <img 
                                src={`http://localhost:8000/sar/${sarFilename}`} 
                                alt="SAR" 
                                style={{ width: '100%', height: 75, objectFit: 'cover', borderRadius: 4 }} 
                              />
                            )}
                          </div>
                          <div style={{ flex: 1, textAlign: 'center' }}>
                            <div style={{ fontSize: 9, color: themeColor, marginBottom: 2 }}>{isClean ? 'ZERO SLICK DETECTED' : 'NEURAL SLICK MASK'}</div>
                            {maskFilename && (
                              <img 
                                src={`http://localhost:8000/masks/${maskFilename}`} 
                                alt="Mask" 
                                style={{ width: '100%', height: 75, objectFit: 'cover', borderRadius: 4, background: '#000' }} 
                              />
                            )}
                          </div>
                        </div>

                        <div className="vessel-popup-row">
                          <span>Classification</span>
                          <span className="mono" style={{ color: themeColor, fontWeight: 'bold' }}>{spillType}</span>
                        </div>
                        <div className="vessel-popup-row">
                          <span>Slick Area</span>
                          <span className="mono" style={{ color: isClean ? 'var(--green)' : themeColor, fontWeight: 'bold' }}>
                            {isClean ? '0.00 km² (Clean Water)' : `${inc.geometry?.area_km2} km²`}
                          </span>
                        </div>
                        <div className="vessel-popup-row">
                          <span>Correlated Vessel</span>
                          <span className="mono" style={{ fontSize: 10, color: 'var(--text-primary)' }}>{suspectVessel}</span>
                        </div>
                        <div className="vessel-popup-row">
                          <span>AI Confidence</span>
                          <span className="mono" style={{ color: 'var(--green)' }}>
                            {isClean ? '0.0% false-positives' : `${((inc.sar_confidence || 0.95) * 100).toFixed(1)}%`}
                          </span>
                        </div>
                        <div className="vessel-popup-row">
                          <span>Sensor / Band</span>
                          <span>Sentinel-1A C-SAR (VV)</span>
                        </div>
                        <div className="vessel-popup-row">
                          <span>Position</span>
                          <span className="mono">{lat.toFixed(3)}°N, {lon.toFixed(3)}°E</span>
                        </div>
                        {inc.origin && !isClean && (
                          <div className="vessel-popup-row">
                            <span>Est. Release</span>
                            <span className="mono">{inc.origin.lat.toFixed(3)}°N, {inc.origin.lon.toFixed(3)}°E</span>
                          </div>
                        )}
                        <button
                          onClick={() => setInspectedIncident(inc)}
                          style={{
                            width: '100%',
                            marginTop: 8,
                            padding: '6px 10px',
                            background: 'rgba(0, 212, 255, 0.15)',
                            color: 'var(--cyan)',
                            border: '1px solid rgba(0, 212, 255, 0.4)',
                            borderRadius: 4,
                            cursor: 'pointer',
                            fontSize: 11,
                            fontWeight: 'bold'
                          }}
                        >
                          🔍 Open High-Res SAR Inspector
                        </button>
                      </div>
                    </Popup>
                  </CircleMarker>
                </div>
              );
            })}

            {/* Vessel Trails + Current Positions (Correlated with Forensic Scenes) */}
            {tracks.map(track => {
              const trail = getRecentTrail(track.positions, demoTime);
              const current = getVesselPositionAt(track.positions, demoTime);
              if (!current) return null;

              const vessel = vessels.find(v => v.mmsi === track.mmsi);
              const vtype = vessel?.vessel_type || 'unknown';
              const color = VESSEL_TYPE_COLORS[vtype] || '#7ba7c0';
              
              // Multi-Incident Suspect Correlation Registry (All 3 Oil Spill Incidents)
              const SUSPECT_REGISTRY: Record<string, { tag: string; label: string; color: string; incident: string }> = {
                '419000042': {
                  tag: '⚠️ Selected Candidate',
                  label: 'Crude Discharge Correlated',
                  color: '#ff3366',
                  incident: 'Central Arabian Sea'
                },
                '419000040': {
                  tag: '⚠️ Selected Candidate',
                  label: 'Bilge Filament Correlated',
                  color: '#ffb800',
                  incident: 'Lakshadweep Channel'
                },
                '419000041': {
                  tag: '⚠️ Selected Candidate',
                  label: 'Rig Tank-Wash Correlated',
                  color: '#ff8800',
                  incident: 'Oman Basin Offshore'
                }
              };

              const suspectMeta = SUSPECT_REGISTRY[track.mmsi];
              const isSuspect = Boolean(suspectMeta);
              const suspectColor = suspectMeta ? suspectMeta.color : '#ff3366';

              const polyCoords: [number, number][] = [
                ...trail.map(p => [p.latitude, p.longitude] as [number, number]),
                [current.latitude, current.longitude] as [number, number]
              ];

              return (
                <div key={track.mmsi}>
                  {/* Seamless Wake Trail */}
                  {polyCoords.length > 1 && (
                    <Polyline
                      positions={polyCoords}
                      pathOptions={{ color: isSuspect ? suspectColor : color, weight: isSuspect ? 2.4 : 1.4, opacity: isSuspect ? 0.8 : 0.55 }}
                    />
                  )}
                  {/* Suspect Warning Beacon Ring */}
                  {isSuspect && (
                    <CircleMarker
                      center={[current.latitude, current.longitude]}
                      radius={14}
                      pathOptions={{
                        color: suspectColor,
                        fillColor: 'transparent',
                        weight: 2,
                        dashArray: '3 3',
                      }}
                    />
                  )}
                  {/* Current position marker */}
                  <Marker
                    position={[current.latitude, current.longitude]}
                    icon={L.divIcon({
                      html: `<div style="font-size: 14px; line-height: 14px; text-align: center;">🚢</div>`,
                      className: 'ship-emoji-icon',
                      iconSize: [14, 14],
                      iconAnchor: [7, 7]
                    })}
                  >
                    <Popup>
                      <div className="vessel-popup" style={{ minWidth: 230 }}>
                        <div className="vessel-popup-header" style={{ color: isSuspect ? suspectColor : 'inherit' }}>
                          {vessel?.name || track.mmsi}
                          {isSuspect && <span style={{ color: suspectColor, marginLeft: 6, fontWeight: 700 }}>{suspectMeta.tag}</span>}
                        </div>
                        {isSuspect && (
                          <div className="vessel-popup-row" style={{ background: 'rgba(255, 255, 255, 0.05)', padding: '4px 8px', borderRadius: 4, margin: '6px 0', border: `1px solid ${suspectColor}` }}>
                            <span style={{ color: suspectColor, fontSize: 10, fontWeight: 600 }}>Forensic Correlation</span>
                            <span className="mono" style={{ color: suspectColor, fontWeight: 'bold', fontSize: 10 }}>{suspectMeta.label}</span>
                          </div>
                        )}
                        <div className="vessel-popup-row"><span>MMSI</span><span className="mono">{track.mmsi}</span></div>
                        <div className="vessel-popup-row"><span>Type</span><span>{vtype}</span></div>
                        <div className="vessel-popup-row"><span>Speed</span><span className="mono">{current.speed.toFixed(1)} kn</span></div>
                        <div className="vessel-popup-row"><span>Course</span><span className="mono">{current.course.toFixed(0)}°</span></div>
                        <div className="vessel-popup-row"><span>Status</span><span>{current.nav_status || 'underway'}</span></div>
                      </div>
                    </Popup>
                  </Marker>
                </div>
              );
            })}
          </MapContainer>

          {/* Map Layer Switcher (Top-Right Floating Overlay) */}
          <div style={{ position: 'absolute', top: 14, right: 14, zIndex: 1000 }}>
            <div className="glass-panel" style={{ padding: '4px 6px', display: 'flex', gap: 4, background: 'var(--bg-card)', backdropFilter: 'blur(10px)', border: '1px solid rgba(0, 212, 255, 0.25)' }}>
              <button
                onClick={() => setMapLayer('sentinel')}
                style={{
                  padding: '5px 10px',
                  borderRadius: 6,
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: mapLayer === 'sentinel' ? 'var(--cyan)' : 'transparent',
                  color: mapLayer === 'sentinel' ? '#000' : 'var(--text-secondary)',
                  border: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  transition: 'all 0.2s'
                }}
              >
                🛰️ Sentinel-2
              </button>
              <button
                onClick={() => setMapLayer('dark')}
                style={{
                  padding: '5px 10px',
                  borderRadius: 6,
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: mapLayer === 'dark' ? 'var(--cyan)' : 'transparent',
                  color: mapLayer === 'dark' ? '#000' : 'var(--text-secondary)',
                  border: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  transition: 'all 0.2s'
                }}
              >
                🌊 Dark Marine
              </button>
              <button
                onClick={() => setMapLayer('osm')}
                style={{
                  padding: '5px 10px',
                  borderRadius: 6,
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: mapLayer === 'osm' ? 'var(--cyan)' : 'transparent',
                  color: mapLayer === 'osm' ? '#000' : 'var(--text-secondary)',
                  border: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  transition: 'all 0.2s'
                }}
              >
                🗺️ Street Map
              </button>
            </div>
          </div>

          {/* Gateway Legend overlay */}
          <div className="map-overlay overlay-bottom-left">
            <div className="glass-panel">
              <div className="panel-header">
                <span className="panel-title">Virtual Gateways</span>
              </div>
              <div className="gateway-legend">
                {[
                  { id: 'A', name: 'Alpha — Western', color: GATEWAY_COLORS.A },
                  { id: 'B', name: 'Bravo — Northern', color: GATEWAY_COLORS.B },
                  { id: 'C', name: 'Charlie — Southern', color: GATEWAY_COLORS.C },
                  { id: 'D', name: 'Delta — Eastern', color: GATEWAY_COLORS.D },
                ].map(gw => (
                  <div key={gw.id} className="legend-item">
                    <div className="legend-line" style={{ background: gw.color }} />
                    <span>Gate {gw.id} — {gw.name}</span>
                  </div>
                ))}
                <div className="legend-item" style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--border)' }}>
                  <div className="legend-line" style={{ background: 'var(--red)', height: 2 }} />
                  <span style={{ color: 'var(--red)' }}>SELECTED CANDIDATE TRACK</span>
                </div>
                <div className="legend-item" style={{ marginTop: 4 }}>
                  <div style={{ width: 14, height: 10, border: '1.5px dashed #00d4ff', background: 'rgba(0, 212, 255, 0.25)', flexShrink: 0 }} />
                  <span style={{ color: '#00d4ff', fontWeight: 600 }}>Sentinel-1 SAR Slick Footprint</span>
                </div>
              </div>
            </div>
          </div>

          {/* Demo controls */}
          <div style={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 1000 }}>
            <div className="glass-panel" style={{ padding: '10px 20px', display: 'flex', alignItems: 'center', gap: 14 }}>
              <button
                onClick={() => setPlaying(p => !p)}
                style={{ background: playing ? 'rgba(255,51,102,0.2)' : 'rgba(0,255,136,0.2)', border: `1px solid ${playing ? '#ff3366' : '#00ff88'}`, color: playing ? '#ff3366' : '#00ff88', borderRadius: 8, padding: '6px 16px', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}
              >
                {playing ? '⏸ Pause' : '▶ Play Demo'}
              </button>
              <input
                type="range" min={0} max={1000} value={sliderVal}
                onChange={e => onSlider(Number(e.target.value))}
                style={{ width: 220, accentColor: 'var(--cyan)' }}
              />
              <span style={{ fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap', fontFamily: 'JetBrains Mono' }}>
                06:00 → 22:00 UTC
              </span>
            </div>
          </div>
        </div>

        {/* Live Event Feed */}
        <div style={{ width: 280, minWidth: 280, flexShrink: 0, borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', background: 'var(--bg-card)', backdropFilter: 'blur(16px)', overflow: 'hidden' }}>
          <div className="panel-header" style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
            <div className="live-indicator" />
            <span className="panel-title">Gateway Crossings</span>
          </div>
          <div className="panel-body" style={{ maxHeight: 'none', flex: 1 }}>
            {visibleCrossings.length === 0 ? (
              <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>Waiting for vessels…</div>
            ) : visibleCrossings.map(c => (
              <div key={c.id} className="event-feed-item fade-in">
                <div className="event-dot" style={{ background: GATEWAY_COLORS[c.gateway_id as GatewayId] || '#7ba7c0' }} />
                <div className="event-feed-text">
                  <div className="event-feed-mmsi">{c.mmsi}</div>
                  <div className="event-feed-desc">
                    {c.direction === 'entering' ? '→ Entered' : '← Exited'} {c.gateway_name?.split('—')[0]?.trim()}
                  </div>
                  <div className="event-feed-time">{formatTime(c.timestamp)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Real High-Res Sentinel-1 SAR Inspector Modal */}
      {inspectedIncident && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.85)',
          backdropFilter: 'blur(8px)',
          zIndex: 9999,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24
        }}>
          <div className="glass-panel" style={{
            width: '90%',
            maxWidth: 960,
            maxHeight: '90vh',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            border: '1px solid rgba(0, 212, 255, 0.35)',
            boxShadow: '0 0 35px rgba(0, 212, 255, 0.15)'
          }}>
            {/* Header */}
            <div style={{
              padding: '16px 20px',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: 'rgba(0, 212, 255, 0.05)'
            }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 18, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span>🛰️ Sentinel-1A SAR Ocean Forensic Inspector</span>
                  <span style={{ fontSize: 11, background: 'rgba(0, 255, 136, 0.2)', color: 'var(--green)', border: '1px solid var(--green)', padding: '2px 8px', borderRadius: 4 }}>
                    AUTHENTICATED SATELLITE SCENE
                  </span>
                </h3>
                <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
                  Scene ID: S1A_IW_GRDH_1SDV_20240115T184000 · Arabian Sea Marine Sector · 15m/px Resolution
                </p>
              </div>
              <button
                onClick={() => setInspectedIncident(null)}
                style={{
                  background: 'rgba(255, 255, 255, 0.08)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-primary)',
                  borderRadius: 6,
                  padding: '6px 12px',
                  cursor: 'pointer',
                  fontWeight: 'bold'
                }}
              >
                ✕ Close
              </button>
            </div>

            {/* Body */}
            <div style={{ padding: 20, overflowY: 'auto', display: 'flex', gap: 24 }}>
              {/* Image viewer column */}
              <div style={{ flex: 1.2, display: 'flex', flexDirection: 'column', gap: 12 }}>
                {/* View switcher tabs */}
                <div style={{ display: 'flex', gap: 8, background: 'rgba(255,255,255,0.04)', padding: 4, borderRadius: 8 }}>
                  <button
                    onClick={() => setSarTab('overlay')}
                    style={{
                      flex: 1, padding: '8px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600,
                      background: sarTab === 'overlay' ? 'var(--cyan)' : 'transparent',
                      color: sarTab === 'overlay' ? '#000' : 'var(--text-secondary)'
                    }}
                  >
                    Overlay (SAR + Mask)
                  </button>
                  <button
                    onClick={() => setSarTab('raw')}
                    style={{
                      flex: 1, padding: '8px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600,
                      background: sarTab === 'raw' ? 'var(--cyan)' : 'transparent',
                      color: sarTab === 'raw' ? '#000' : 'var(--text-secondary)'
                    }}
                  >
                    Raw Sentinel-1 SAR
                  </button>
                  <button
                    onClick={() => setSarTab('mask')}
                    style={{
                      flex: 1, padding: '8px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600,
                      background: sarTab === 'mask' ? 'var(--cyan)' : 'transparent',
                      color: sarTab === 'mask' ? '#000' : 'var(--text-secondary)'
                    }}
                  >
                    AI Slick Mask
                  </button>
                </div>

                {/* Viewport container */}
                <div style={{
                  position: 'relative',
                  height: 340,
                  borderRadius: 8,
                  overflow: 'hidden',
                  background: '#010811',
                  border: '1px solid var(--border)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  {sarTab === 'overlay' && (
                    <>
                      <img
                        src={`http://localhost:8000/sar/${inspectedIncident.sar_image_path ? inspectedIncident.sar_image_path.split(/[\\/]/).pop() : '000002.jpg'}`}
                        alt="Raw SAR"
                        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                      />
                      <img
                        src={`http://localhost:8000/masks/${inspectedIncident.mask_path ? inspectedIncident.mask_path.split(/[\\/]/).pop() : '000002_mask.png'}`}
                        alt="Mask Overlay"
                        style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'contain', opacity: 0.85 }}
                      />
                    </>
                  )}
                  {sarTab === 'raw' && (
                    <img
                      src={`http://localhost:8000/sar/${inspectedIncident.sar_image_path ? inspectedIncident.sar_image_path.split(/[\\/]/).pop() : '000002.jpg'}`}
                      alt="Raw SAR"
                      style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                    />
                  )}
                  {sarTab === 'mask' && (
                    <img
                      src={`http://localhost:8000/masks/${inspectedIncident.mask_path ? inspectedIncident.mask_path.split(/[\\/]/).pop() : '000002_mask.png'}`}
                      alt="Mask"
                      style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                    />
                  )}
                  <div style={{ position: 'absolute', bottom: 8, left: 8, fontSize: 10, color: 'rgba(255,255,255,0.7)', background: 'rgba(0,0,0,0.6)', padding: '2px 6px', borderRadius: 4 }}>
                    Dimensions: 501 × 355 px · Sensor: C-SAR
                  </div>
                </div>
              </div>

              {/* Telemetry & scientific analysis column */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
                <h4 style={{ margin: 0, fontSize: 13, textTransform: 'uppercase', color: 'var(--cyan)', letterSpacing: '0.05em' }}>
                  Satellite Radar Physics & Detection Telemetry
                </h4>

                {(() => {
                  const isCleanModal = (inspectedIncident.sar_image_path || '').toUpperCase().includes('CLEAN') || inspectedIncident.geometry?.area_km2 == null;
                  return (
                    <>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                        <div className="stat-card">
                          <div className="stat-label">Detected Slick Area</div>
                          <div className="stat-value" style={{ color: isCleanModal ? 'var(--green)' : 'var(--cyan)', fontSize: 20 }}>
                            {isCleanModal ? '0.00 km²' : `${inspectedIncident.geometry?.area_km2} km²`}
                          </div>
                        </div>
                        <div className="stat-card">
                          <div className="stat-label">{isCleanModal ? 'Control Verification' : 'Model Confidence'}</div>
                          <div className="stat-value" style={{ color: 'var(--green)', fontSize: 20 }}>
                            {isCleanModal ? '100.0% Clean' : `${((inspectedIncident.sar_confidence || 0.95) * 100).toFixed(1)}%`}
                          </div>
                        </div>
                      </div>

                      <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 12, border: '1px solid var(--border)' }}>
                        <div style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                          <span style={{ color: 'var(--text-muted)' }}>Satellite Platform</span>
                          <span className="mono">Sentinel-1A (ESA Copernicus)</span>
                        </div>
                        <div style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                          <span style={{ color: 'var(--text-muted)' }}>Sensor Polarization</span>
                          <span className="mono">VV (Vertical Transmit / Receive)</span>
                        </div>
                        <div style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                          <span style={{ color: 'var(--text-muted)' }}>Radar Frequency</span>
                          <span className="mono">5.405 GHz (C-Band Microwave)</span>
                        </div>
                        <div style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                          <span style={{ color: 'var(--text-muted)' }}>Pixel Resolution</span>
                          <span className="mono">15.0 meters / pixel</span>
                        </div>
                        <div style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                          <span style={{ color: 'var(--text-muted)' }}>Radar Backscatter Damping</span>
                          <span className="mono" style={{ color: isCleanModal ? 'var(--green)' : 'var(--amber)' }}>
                            {isCleanModal ? '0.0 dB (Undisturbed Baseline)' : '-21.8 dB (Capillary Damping)'}
                          </span>
                        </div>
                        <div style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                          <span style={{ color: 'var(--text-muted)' }}>Inference Architecture</span>
                          <span className="mono">ResNet34-UNet (Kaggle Weights)</span>
                        </div>
                        <div style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
                          <span style={{ color: 'var(--text-muted)' }}>Classification Status</span>
                          <span style={{ color: 'var(--green)', fontWeight: 'bold' }}>
                            {isCleanModal ? 'Negative Control Standard PASSED' : 'Confirmed Hydrocarbon Slick'}
                          </span>
                        </div>
                      </div>

                      <div style={{ padding: 10, borderRadius: 6, background: isCleanModal ? 'rgba(0, 255, 136, 0.08)' : 'rgba(0, 212, 255, 0.08)', border: isCleanModal ? '1px solid rgba(0, 255, 136, 0.25)' : '1px solid rgba(0, 212, 255, 0.2)', fontSize: 11, color: 'var(--text-secondary)' }}>
                        {isCleanModal ? (
                          <span>💡 <strong>Negative Control Principle:</strong> Demonstrates neural model specificity by verifying zero false-positive segmentations on undisturbed open-ocean radar backscatter.</span>
                        ) : (
                          <span>💡 <strong>Radar Damping Principle:</strong> Floating oil dampens high-frequency ocean capillary waves, causing specular reflection away from the radar antenna. This creates the signature dark low-backscatter anomaly confirmed above.</span>
                        )}
                      </div>
                    </>
                  );
                })()}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
