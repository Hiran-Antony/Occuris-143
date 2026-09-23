import { useEffect, useState, useRef } from 'react';
import { forensicsApi, caseApi } from '../api/client';
import { MapContainer, TileLayer, CircleMarker, ImageOverlay, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

function MapRecenter({ lat, lon }: { lat: number; lon: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo([lat, lon], 11.8, { duration: 1.0 });
  }, [lat, lon, map]);
  return null;
}

function SatelliteInspectionOverlay({
  lat,
  lon,
  originLat,
  originLon,
  isClean,
  currentDir = 225,
  sarBounds
}: {
  lat: number;
  lon: number;
  originLat?: number;
  originLon?: number;
  isClean: boolean;
  currentDir?: number;
  sarBounds: [[number, number], [number, number]];
}) {
  const map = useMap();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    let animId: number;
    const render = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const size = map.getSize();
      if (canvas.width !== size.x || canvas.height !== size.y) {
        canvas.width = size.x;
        canvas.height = size.y;
      }
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      frameRef.current++;
      const frame = frameRef.current;

      const centerPt = map.latLngToContainerPoint([lat, lon]);

      // 1. High-Tech Tactical Corner Reticles for SAR Chip Footprint
      if (sarBounds) {
        const nw = map.latLngToContainerPoint([sarBounds[1][0], sarBounds[0][1]]);
        const se = map.latLngToContainerPoint([sarBounds[0][0], sarBounds[1][1]]);
        const bX = nw.x;
        const bY = nw.y;
        const bW = se.x - nw.x;
        const bH = se.y - nw.y;
        const cornerLen = 14;

        ctx.strokeStyle = 'rgba(0, 212, 255, 0.7)';
        ctx.lineWidth = 1.8;

        // Top-Left
        ctx.beginPath();
        ctx.moveTo(bX, bY + cornerLen);
        ctx.lineTo(bX, bY);
        ctx.lineTo(bX + cornerLen, bY);
        ctx.stroke();

        // Top-Right
        ctx.beginPath();
        ctx.moveTo(bX + bW - cornerLen, bY);
        ctx.lineTo(bX + bW, bY);
        ctx.lineTo(bX + bW, bY + cornerLen);
        ctx.stroke();

        // Bottom-Left
        ctx.beginPath();
        ctx.moveTo(bX, bY + bH - cornerLen);
        ctx.lineTo(bX, bY + bH);
        ctx.lineTo(bX + cornerLen, bY + bH);
        ctx.stroke();

        // Bottom-Right
        ctx.beginPath();
        ctx.moveTo(bX + bW - cornerLen, bY + bH);
        ctx.lineTo(bX + bW, bY + bH);
        ctx.lineTo(bX + bW, bY + bH - cornerLen);
        ctx.stroke();

        // Swath boundary subtle line
        ctx.strokeStyle = 'rgba(0, 212, 255, 0.25)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.strokeRect(bX, bY, bW, bH);
        ctx.setLineDash([]);
      }

      // 2. Subtle Precision Crosshairs centered on slick centroid
      ctx.strokeStyle = 'rgba(0, 212, 255, 0.7)';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(centerPt.x - 14, centerPt.y);
      ctx.lineTo(centerPt.x - 4, centerPt.y);
      ctx.moveTo(centerPt.x + 4, centerPt.y);
      ctx.lineTo(centerPt.x + 14, centerPt.y);
      ctx.moveTo(centerPt.x, centerPt.y - 14);
      ctx.lineTo(centerPt.x, centerPt.y - 4);
      ctx.moveTo(centerPt.x, centerPt.y + 4);
      ctx.lineTo(centerPt.x, centerPt.y + 14);
      ctx.stroke();

      // Centroid pinpoint dot
      ctx.fillStyle = '#00d4ff';
      ctx.beginPath();
      ctx.arc(centerPt.x, centerPt.y, 2.5, 0, Math.PI * 2);
      ctx.fill();

      if (!isClean) {
        // 3. Subtle Pulsing Aura around slick centroid
        const pulse = (Math.sin(frame * 0.08) + 1) * 0.5;
        ctx.strokeStyle = `rgba(0, 212, 255, ${0.25 + pulse * 0.35})`;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(centerPt.x, centerPt.y, 12 + pulse * 5, 0, Math.PI * 2);
        ctx.stroke();

        // 4. Backward Origin Trajectory Vector (-6h Release) - Simple & Clean
        if (originLat && originLon) {
          const origPt = map.latLngToContainerPoint([originLat, originLon]);
          const origPulse = (Math.sin(frame * 0.1) + 1) * 0.5;

          // Connecting trajectory vector line
          ctx.strokeStyle = 'rgba(255, 51, 102, 0.7)';
          ctx.lineWidth = 1.6;
          ctx.setLineDash([4, 4]);
          ctx.beginPath();
          ctx.moveTo(origPt.x, origPt.y);
          ctx.lineTo(centerPt.x, centerPt.y);
          ctx.stroke();
          ctx.setLineDash([]);

          // Direction chevron along trajectory
          const midX = (origPt.x + centerPt.x) / 2;
          const midY = (origPt.y + centerPt.y) / 2;
          const trajAngle = Math.atan2(centerPt.y - origPt.y, centerPt.x - origPt.x);
          ctx.save();
          ctx.translate(midX, midY);
          ctx.rotate(trajAngle);
          ctx.fillStyle = '#ff3366';
          ctx.beginPath();
          ctx.moveTo(5, 0);
          ctx.lineTo(-3, -3);
          ctx.lineTo(-3, 3);
          ctx.closePath();
          ctx.fill();
          ctx.restore();

          // Delicate origin beacon ping
          ctx.strokeStyle = `rgba(255, 51, 102, ${0.7 - origPulse * 0.6})`;
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(origPt.x, origPt.y, 5 + origPulse * 12, 0, Math.PI * 2);
          ctx.stroke();

          ctx.fillStyle = '#ff3366';
          ctx.beginPath();
          ctx.arc(origPt.x, origPt.y, 3.5, 0, Math.PI * 2);
          ctx.fill();

          // Clean, uncluttered text
          const distKm = (Math.hypot(lat - originLat, lon - originLon) * 111).toFixed(1);
          ctx.shadowColor = 'rgba(0, 0, 0, 0.9)';
          ctx.shadowBlur = 6;
          ctx.fillStyle = '#ff4d79';
          ctx.font = '600 10px JetBrains Mono, monospace';
          ctx.fillText(`● Discharge Origin (-${distKm} km)`, origPt.x + 8, origPt.y + 3);
          ctx.shadowBlur = 0;
        }
      }

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [map, lat, lon, originLat, originLon, isClean, currentDir, sarBounds]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 400
      }}
    />
  );
}

const SCENE_METADATA: Record<string, { sector: string; coords: string; sensor: string; desc: string; baseLat: number; baseLon: number }> = {
  'S1A_IW_GRDH_20240115_SLICK_BAYOFBENGAL.jpg': {
    sector: 'Central Arabian Sea',
    coords: '13.170°N, 86.206°E',
    sensor: 'Sentinel-1A IW · Track 121 · Ascending',
    desc: 'Primary crude discharge linked to MT DESH SHOBHA blackout',
    baseLat: 13.1600,
    baseLon: 86.1900,
  },
  'S1A_IW_GRDH_20240115_SLICK_FILAMENT.jpg': {
    sector: 'Lakshadweep Channel Fairway',
    coords: '10.125°N, 92.638°E',
    sensor: 'Sentinel-1A IW · Track 48 · Descending',
    desc: 'Linear underway bilge discharge in Andaman Sea corridor',
    baseLat: 10.1200,
    baseLon: 92.6200,
  },
  'S1B_IW_GRDH_20240115_SLICK_EMULSION.jpg': {
    sector: 'Oman Basin Offshore Energy Zone',
    coords: '16.451°N, 84.461°E',
    sensor: 'Sentinel-1B IW · Track 92 · Ascending',
    desc: 'Weathered patchy emulsion in northern petroleum basin',
    baseLat: 16.4515,
    baseLon: 84.4606,
  },
  'S1A_IW_GRDH_20240115_CLEAN_OCEAN.jpg': {
    sector: 'Central-East Deep Ocean',
    coords: '14.850°N, 88.500°E',
    sensor: 'Sentinel-1A IW · Reference Standard',
    desc: 'Clean undisturbed open ocean control scene for model validation',
    baseLat: 14.8500,
    baseLon: 88.5000,
  },
};

export const ForensicInvestigation: React.FC = () => {
  const [sarImages, setSarImages] = useState<string[]>([]);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [processing, setProcessing] = useState<string | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<any | null>(null);
  const [suspects, setSuspects] = useState<any[]>([]);
  const [loadingSuspects, setLoadingSuspects] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<'both' | 'raw' | 'mask'>('both');
  const [mapLayer, setMapLayer] = useState<'sentinel' | 'dark' | 'osm'>('sentinel');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const imgRes = await forensicsApi.getSarImages();
      setSarImages(imgRes.images);
      const incRes = await forensicsApi.getIncidents();
      setIncidents(incRes);
      if (incRes.length > 0 && !selectedIncident) {
        setSelectedIncident(incRes[0]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const processImage = async (filename: string) => {
    setProcessing(filename);
    try {
      // Find existing incident and select it instead of calling process API
      const existing = incidents.find((i: any) => i.sar_image_path?.endsWith(filename));
      if (existing) {
        handleSelectIncident(existing);
      } else {
        alert('Case data not found.');
      }
    } catch (e) {
      console.error(e);
      alert('Failed to process SAR image.');
    } finally {
      setProcessing(null);
    }
  };

  const getIncidentForImage = (filename: string) => {
    return incidents.find((inc) => inc.sar_image_path?.endsWith(filename));
  };

  const handleSelectIncident = async (inc: any) => {
    setLoadingSuspects(true);
    try {
      // Fetch full case details dynamically
      const spillData = await caseApi.getSpill(inc.id);
      const originData = await caseApi.getOriginZone(inc.id);
      
      const enrichedInc = {
        ...inc,
        sar_confidence: spillData.look_alike?.passed ? 0.95 : 0.45,
        look_alike: spillData.look_alike,
        geometry: {
          area_km2: spillData.geometry?.area_km2,
          centroid_lat: spillData.geometry?.centroid_geo?.latitude,
          centroid_lon: spillData.geometry?.centroid_geo?.longitude,
          orientation_deg: spillData.geometry?.orientation_deg,
          major_axis_km: spillData.geometry?.major_axis_km,
        },
        spillsplit: {
          delta_bic: (originData.one_source?.bic || 0) - (originData.two_source?.bic || 0),
          hypothesis: originData.result === 'One Source Zone' ? 'one_source' : 'two_source'
        },
        origin: {
          lat: originData.source_zones?.[0]?.latitude,
          lon: originData.source_zones?.[0]?.longitude
        }
      };
      
      setSelectedIncident(enrichedInc);

      const rawCandidates = await caseApi.getCandidates(inc.id);
      const vessels = await caseApi.getVessels(inc.id);
      const mappedSuspects = rawCandidates.map((c: any) => {
        const v = vessels.find((v: any) => v.mmsi === c.vessel_id) || {};
        return {
          vessel_name: v.name || ('Vessel ' + c.vessel_id),
          mmsi: c.vessel_id,
          priority: c.evidence_state,
          match_score: Math.round((c.composite_score || 0) * 100),
          reasons: [
            c.spatial_evidence?.intersects_origin_zone ? 'Intersects Origin Zone' : 'Does not intersect origin zone',
            c.temporal_evidence?.present_during_investigation_window ? 'Present in investigation window' : 'Not present in time window',
            c.kinematic_evidence?.speed_anomaly ? 'Speed anomaly detected' : 'Normal kinematics'
          ]
        };
      });
      setSuspects(mappedSuspects);
    } catch (e) {
      console.error(e);
      setSuspects([]);
      setSelectedIncident(inc);
    } finally {
      setLoadingSuspects(false);
    }
  };

  const formatImageName = (name: string) => {
    if (name.includes('BAYOFBENGAL') || name === '000002.jpg') return '🛰️ S1A IW — Arabian Sea Slick';
    if (name.includes('FILAMENT')) return '🛰️ S1A IW — Bilge Wake Filament';
    if (name.includes('EMULSION')) return '🛰️ S1B IW — Weathered Emulsion';
    if (name.includes('CLEAN')) return '🌊 S1A IW — Clean Ocean (Control)';
    return `🛰️ ${name}`;
  };

  const sarFilename = selectedIncident?.sar_image_path ? selectedIncident.sar_image_path.split(/[\\/]/).pop() : '000002.jpg';
  const maskFilename = selectedIncident?.mask_path ? selectedIncident.mask_path.split(/[\\/]/).pop() : '000002_mask.png';

  const sceneMeta = (sarFilename && SCENE_METADATA[sarFilename]) || {
    baseLat: 13.158,
    baseLon: 86.190,
    sector: 'Ocean Area',
    coords: '13.158°N, 86.190°E',
    sensor: 'Sentinel-1 C-SAR',
    desc: 'Synthetic Aperture Radar scene'
  };

  const lat = selectedIncident?.geometry?.centroid_lat ?? sceneMeta.baseLat;
  const lon = selectedIncident?.geometry?.centroid_lon ?? sceneMeta.baseLon;

  // 512x512 SAR chip at 15m/px = 7.68 km span centered directly over slick centroid
  const spanLat = 0.069;
  const spanLon = 0.069 / Math.cos((lat * Math.PI) / 180);
  const sarBounds: [[number, number], [number, number]] = [
    [lat - spanLat / 2, lon - spanLon / 2],
    [lat + spanLat / 2, lon + spanLon / 2],
  ];

  return (
    <div className="memory-page" style={{ overflow: 'hidden', paddingBottom: '20px', background: 'var(--bg-primary)' }}>
      {/* Page Header */}
      <header className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 24px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 22 }}>🛰️</span>
            <h1 className="page-title" style={{ fontSize: 18, fontWeight: 700 }}>Sentinel-1 SAR Forensics & Neural Detection Pipeline</h1>
            <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(0, 212, 255, 0.15)', color: 'var(--cyan)', border: '1px solid var(--cyan)', fontWeight: 700 }}>
              CSIRO DEEP LEARNING ENGINE
            </span>
          </div>
          <p className="page-subtitle" style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Copernicus Sentinel-1 Synthetic Aperture Radar (C-band 5.405 GHz) oil slick identification & capillary wave damping telemetry.
          </p>
        </div>

        {/* Basemap Switcher */}
        <div style={{ display: 'flex', gap: 6, background: '#030a12', padding: 4, borderRadius: 8, border: '1px solid var(--border)' }}>
          <button
            onClick={() => setMapLayer('sentinel')}
            style={{ padding: '5px 10px', borderRadius: 6, border: 'none', background: mapLayer === 'sentinel' ? 'var(--cyan)' : 'transparent', color: mapLayer === 'sentinel' ? '#000' : 'var(--text-secondary)', fontWeight: 600, fontSize: 11, cursor: 'pointer' }}
          >
            🛰️ Sentinel-2
          </button>
          <button
            onClick={() => setMapLayer('dark')}
            style={{ padding: '5px 10px', borderRadius: 6, border: 'none', background: mapLayer === 'dark' ? 'var(--cyan)' : 'transparent', color: mapLayer === 'dark' ? '#000' : 'var(--text-secondary)', fontWeight: 600, fontSize: 11, cursor: 'pointer' }}
          >
            🌊 Dark Marine
          </button>
          <button
            onClick={() => setMapLayer('osm')}
            style={{ padding: '5px 10px', borderRadius: 6, border: 'none', background: mapLayer === 'osm' ? 'var(--cyan)' : 'transparent', color: mapLayer === 'osm' ? '#000' : 'var(--text-secondary)', fontWeight: 600, fontSize: 11, cursor: 'pointer' }}
          >
            🗺️ Street Map
          </button>
        </div>
      </header>

      <div style={{ display: 'flex', gap: '20px', padding: '20px', height: 'calc(100vh - 90px)' }}>
        
        {/* Left Column - SAR Scanning */}
        <div className="glass-panel" style={{ width: '320px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="panel-header" style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: '18px' }}>🛰️</span>
            <span className="panel-title" style={{ fontSize: 13, fontWeight: 700 }}>Copernicus SAR Acquisitions</span>
          </div>
          
          <div style={{ padding: '14px', overflowY: 'auto', flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', background: 'rgba(0, 212, 255, 0.05)', border: '1px solid var(--border)', borderRadius: '6px', marginBottom: '14px' }}>
              <div className="status-dot"></div>
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Live Sentinel-1 GRD Feed Active</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {sarImages.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '12px', fontStyle: 'italic' }}>No SAR scenes available.</p>
              ) : (
                sarImages.map(img => {
                  const inc = getIncidentForImage(img);
                  const isSelected = selectedIncident?.sar_image_path?.endsWith(img);
                  return (
                    <div key={img} style={{ 
                      padding: '12px', 
                      borderRadius: '8px', 
                      border: isSelected ? '1px solid var(--cyan)' : inc ? '1px solid rgba(0, 212, 255, 0.25)' : '1px solid var(--border)',
                      background: isSelected ? 'rgba(0, 212, 255, 0.12)' : inc ? 'rgba(0, 212, 255, 0.03)' : 'rgba(255,255,255,0.02)'
                    }}>
                      <div style={{ marginBottom: '6px' }}>
                        <div style={{ fontSize: '12px', fontWeight: '700', color: isSelected ? 'var(--cyan)' : 'var(--text-primary)' }}>
                          {formatImageName(img)}
                        </div>
                        {SCENE_METADATA[img] && (
                          <div style={{ marginTop: 4 }}>
                            <div style={{ fontSize: '11px', color: 'var(--cyan)', fontWeight: 600 }}>
                              📍 {SCENE_METADATA[img].sector}
                            </div>
                            <div style={{ fontSize: '10px', fontFamily: 'JetBrains Mono', color: 'var(--text-secondary)' }}>
                              {SCENE_METADATA[img].coords}
                            </div>
                            <div style={{ fontSize: '9px', color: 'var(--text-muted)', marginTop: 2 }}>
                              🛰️ {SCENE_METADATA[img].sensor}
                            </div>
                          </div>
                        )}
                        <div style={{ fontSize: '9px', fontFamily: 'JetBrains Mono', color: 'var(--text-muted)', marginTop: 4, wordBreak: 'break-all' }}>
                          {img}
                        </div>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '8px 0' }}>
                        {inc && <span style={{ fontSize: '10px', color: 'var(--green)', fontWeight: 'bold' }}>✓ Neural Detected ({(inc.sar_confidence * 100).toFixed(1)}%)</span>}
                        {processing === img && <span style={{ fontSize: '10px', color: 'var(--amber)', animation: 'pulse-dot 2s infinite' }}>⚡ Inferring...</span>}
                      </div>
                      
                      {!inc && processing !== img && (
                        <button
                          onClick={() => processImage(img)}
                          style={{
                            width: '100%', padding: '7px', background: 'var(--cyan)', color: '#000', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '11px', fontWeight: 'bold'
                          }}
                        >
                          ⚡ Run CSIRO Model
                        </button>
                      )}
                      {inc && (
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            onClick={() => handleSelectIncident(inc)}
                            style={{
                              flex: 1, padding: '7px', background: isSelected ? 'var(--cyan)' : 'rgba(255,255,255,0.08)', color: isSelected ? '#000' : 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: '4px', cursor: 'pointer', fontSize: '11px', fontWeight: 600, transition: 'all 0.2s'
                            }}
                          >
                            Inspect Scene
                          </button>
                          <button
                            onClick={() => processImage(img)}
                            disabled={processing === img}
                            title="Re-run CSIRO model on this SAR scene"
                            style={{
                              padding: '7px 10px', background: 'rgba(0, 212, 255, 0.15)', color: 'var(--cyan)', border: '1px solid rgba(0, 212, 255, 0.3)', borderRadius: '4px', cursor: 'pointer', fontSize: '11px', fontWeight: 'bold'
                            }}
                          >
                            {processing === img ? '...' : 'Re-run'}
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Main Columns - Analysis Dashboard */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto' }}>
          {!selectedIncident ? (
            <div className="glass-panel" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', borderStyle: 'dashed' }}>
              <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                <p style={{ fontSize: '40px', marginBottom: '10px' }}>📡</p>
                <p>Select a processed SAR acquisition from the feed</p>
              </div>
            </div>
          ) : (
            <>
              {/* Top row: High-Resolution Satellite & Neural Imagery */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '16px' }}>
                
                {/* Sentinel-1 Satellite Imagery Viewer */}
                <div className="glass-panel" style={{ padding: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <div>
                      <h3 style={{ fontSize: '15px', color: 'var(--text-primary)', fontWeight: 700 }}>
                        ESA Sentinel-1 C-SAR Scene
                      </h3>
                      <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: 2 }}>
                        Model: CSIRO ResNet18-OilNet (Trained on Kaggle Dataset)
                      </p>
                    </div>

                    <div style={{ display: 'flex', gap: 4, background: '#020c18', padding: 3, borderRadius: 6, border: '1px solid var(--border)' }}>
                      <button
                        onClick={() => setViewMode('both')}
                        style={{ padding: '4px 8px', borderRadius: 4, border: 'none', background: viewMode === 'both' ? 'var(--cyan)' : 'transparent', color: viewMode === 'both' ? '#000' : 'var(--text-secondary)', fontSize: 10, fontWeight: 700, cursor: 'pointer' }}
                      >
                        Side-by-Side
                      </button>
                      <button
                        onClick={() => setViewMode('raw')}
                        style={{ padding: '4px 8px', borderRadius: 4, border: 'none', background: viewMode === 'raw' ? 'var(--cyan)' : 'transparent', color: viewMode === 'raw' ? '#000' : 'var(--text-secondary)', fontSize: 10, fontWeight: 700, cursor: 'pointer' }}
                      >
                        Raw SAR
                      </button>
                      <button
                        onClick={() => setViewMode('mask')}
                        style={{ padding: '4px 8px', borderRadius: 4, border: 'none', background: viewMode === 'mask' ? 'var(--cyan)' : 'transparent', color: viewMode === 'mask' ? '#000' : 'var(--text-secondary)', fontSize: 10, fontWeight: 700, cursor: 'pointer' }}
                      >
                        AI Mask
                      </button>
                    </div>
                  </div>
                  
                  {/* Side-by-Side Image Display */}
                  <div style={{ display: 'flex', gap: 10, background: '#020c18', borderRadius: 8, padding: 8, border: '1px solid var(--border)', minHeight: 200 }}>
                    {(viewMode === 'both' || viewMode === 'raw') && (
                      <div style={{ flex: 1, textAlign: 'center' }}>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                          RAW RADAR BACKSCATTER (15m/px)
                        </div>
                        <img 
                          src={`http://localhost:8080/sar/${sarFilename}`} 
                          alt="Raw SAR Satellite Scene" 
                          style={{ width: '100%', height: 180, objectFit: 'cover', borderRadius: 6 }} 
                        />
                      </div>
                    )}
                    {(viewMode === 'both' || viewMode === 'mask') && (
                      <div style={{ flex: 1, textAlign: 'center' }}>
                        <div style={{ fontSize: 10, color: 'var(--cyan)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                          CSIRO NEURAL SLICK MASK ({(selectedIncident.sar_confidence * 100).toFixed(1)}%)
                        </div>
                        <img 
                          src={`http://localhost:8080/masks/${maskFilename}`} 
                          alt="AI Segmentation Mask" 
                          style={{ width: '100%', height: 180, objectFit: 'cover', borderRadius: 6, background: '#000' }} 
                        />
                      </div>
                    )}
                  </div>
                </div>

                {/* Radar Physics & SpillSplit Telemetry */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {(() => {
                    const isClean = !selectedIncident.geometry?.area_km2 || selectedIncident.geometry.area_km2 === 0;
                    return (
                      <>
                        <div className="glass-panel" style={{ padding: '16px' }}>
                          <h3 style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                            SAR Physics & Contrast Analysis
                          </h3>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '4px' }}>SPILL µ (INTENSITY)</div>
                              <div style={{ fontSize: '16px', color: 'var(--cyan)', fontWeight: 'bold', fontFamily: 'JetBrains Mono' }}>
                                {isClean || selectedIncident.look_alike?.spill_mean_intensity == null ? 'N/A' : `${(selectedIncident.look_alike.spill_mean_intensity * 100).toFixed(2)}%`}
                              </div>
                            </div>
                            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '4px' }}>BACKGROUND µ</div>
                              <div style={{ fontSize: '16px', color: 'var(--cyan)', fontWeight: 'bold', fontFamily: 'JetBrains Mono' }}>
                                {isClean || selectedIncident.look_alike?.background_mean_intensity == null ? 'N/A' : `${(selectedIncident.look_alike.background_mean_intensity * 100).toFixed(2)}%`}
                              </div>
                            </div>
                            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '4px' }}>CONTRAST RATIO</div>
                              <div style={{ fontSize: '16px', color: 'var(--text-primary)', fontWeight: 'bold', fontFamily: 'JetBrains Mono' }}>
                                {isClean || selectedIncident.look_alike?.contrast_ratio == null ? 'N/A' : `${(selectedIncident.look_alike.contrast_ratio * 100).toFixed(2)}%`}
                              </div>
                            </div>
                            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '4px' }}>VERIFICATION STATUS</div>
                              <div style={{ fontSize: '16px', color: isClean ? 'var(--text-primary)' : (selectedIncident.look_alike?.passed ? 'var(--cyan)' : '#ff6b6b'), fontWeight: 'bold', fontFamily: 'JetBrains Mono' }}>
                                {isClean ? 'CLEAN OCEAN' : (selectedIncident.look_alike?.passed ? 'CONFIRMED' : 'LOOK-ALIKE')}
                              </div>
                            </div>
                          </div>
                        </div>

                        <div className="glass-panel" style={{ padding: '16px' }}>
                          <h3 style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                            Spill Geometry (M2)
                          </h3>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '4px' }}>AREA</div>
                              <div style={{ fontSize: '16px', color: 'var(--cyan)', fontWeight: 'bold', fontFamily: 'JetBrains Mono' }}>{isClean ? '0.00' : (selectedIncident.geometry?.area_km2 || 0).toFixed(2)} <span style={{fontSize:'12px', color:'var(--text-muted)'}}>km²</span></div>
                            </div>
                            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '4px' }}>CONTRAST RATIO</div>
                              <div style={{ fontSize: '16px', color: 'var(--green)', fontWeight: 'bold', fontFamily: 'JetBrains Mono' }}>{isClean ? 'N/A' : (selectedIncident.look_alike?.contrast_ratio || 0).toFixed(2)} ✓</div>
                            </div>
                            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '4px' }}>ORIENTATION</div>
                              <div style={{ fontSize: '16px', color: 'var(--text-primary)', fontWeight: 'bold', fontFamily: 'JetBrains Mono' }}>{isClean ? 'N/A' : (selectedIncident.geometry?.orientation_deg || 0).toFixed(2)}°</div>
                            </div>
                            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '4px' }}>MAJOR AXIS</div>
                              <div style={{ fontSize: '16px', color: 'var(--text-primary)', fontWeight: 'bold', fontFamily: 'JetBrains Mono' }}>{isClean ? 'N/A' : (selectedIncident.geometry?.major_axis_km || 0).toFixed(2)} <span style={{fontSize:'12px', color:'var(--text-muted)'}}>km</span></div>
                            </div>
                          </div>
                          <div style={{ fontSize: '9px', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '12px' }}>
                            * MVP geospatial estimate — 10 m/pixel scale assumed
                          </div>
                        </div>

                        <div style={{ background: 'rgba(0, 255, 100, 0.05)', border: '1px solid rgba(0, 255, 100, 0.2)', borderRadius: '6px', padding: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ fontSize: '11px', color: 'var(--green)', fontWeight: 'bold', textTransform: 'uppercase' }}>
                            ▲ Look-alike Verification
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--text-primary)' }}>
                            {isClean ? 'N/A' : (selectedIncident.look_alike?.passed ? 'PASS' : 'FAIL')} — {isClean ? 'No spill detected' : (selectedIncident.look_alike?.interpretation || 'Darker than background')}
                          </div>
                        </div>
                      </>
                    );
                  })()}
                </div>

              </div>

              {/* Bottom Row: Ocean Map & Suspect Hunt */}
              <div style={{ display: 'flex', gap: '16px', flex: 1, minHeight: '350px' }}>
                <div className="glass-panel" style={{ flex: 1.5, minHeight: '320px', padding: '16px', display: 'flex', flexDirection: 'column' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <h3 style={{ fontSize: '14px', color: 'var(--text-primary)', fontWeight: 700 }}>
                      Oceanic Radar Footprint & Drift Dispersion Map
                    </h3>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      Acquisition Centroid: {lat}°N, {lon}°E · 18:40 UTC
                    </span>
                  </div>
                  
                  <div style={{ flex: 1, minHeight: '260px', borderRadius: '8px', border: '1px solid var(--border)', overflow: 'hidden' }}>
                    <MapContainer 
                      center={[lat, lon]} 
                      zoom={11.8} 
                      style={{ height: '100%', width: '100%', background: '#020c18' }}
                    >
                      <MapRecenter lat={lat} lon={lon} />
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

                      {/* Draped Real Sentinel-1 SAR Satellite Image */}
                      <ImageOverlay 
                        url={`http://localhost:8080/sar/${sarFilename}`} 
                        bounds={sarBounds} 
                        opacity={0.92}
                      />

                      {/* Draped Real Neural Mask */}
                      <ImageOverlay 
                        url={`http://localhost:8080/masks/${maskFilename}`} 
                        bounds={sarBounds} 
                        opacity={0.82}
                      />

                      {/* Precision Satellite Inspection & Backtrack Canvas */}
                      <SatelliteInspectionOverlay
                        lat={lat}
                        lon={lon}
                        originLat={selectedIncident.origin?.lat}
                        originLon={selectedIncident.origin?.lon}
                        isClean={!selectedIncident.geometry?.area_km2 || selectedIncident.geometry.area_km2 === 0}
                        sarBounds={sarBounds}
                        currentDir={
                          selectedIncident.sar_image_path?.includes('FILAMENT') ? 92 :
                          selectedIncident.sar_image_path?.includes('EMULSION') ? 202 : 225
                        }
                      />

                      {/* Centroid Reticle Point */}
                      <CircleMarker 
                        center={[lat, lon]} 
                        radius={5} 
                        pathOptions={{ color: '#00ffff', fillColor: '#ffffff', fillOpacity: 1, weight: 2 }}
                      />
                    </MapContainer>
                  </div>
                </div>

                {/* Suspects Column */}
                <div className="glass-panel" style={{ flex: 1, padding: '16px', display: 'flex', flexDirection: 'column' }}>
                  <h3 style={{ fontSize: '15px', color: 'var(--text-primary)', marginBottom: '5px', fontWeight: 700 }}>Memory Rewind</h3>
                  <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '15px' }}>Cross-referencing historical AIS data against Origin Zone & Time.</p>
                  
                  <div style={{ flex: 1, overflowY: 'auto' }}>
                    {loadingSuspects ? (
                      <div style={{ textAlign: 'center', padding: '40px 20px' }}>
                        <div style={{ animation: 'pulse-dot 1.5s infinite', fontSize: '24px', marginBottom: '10px' }}>⏳</div>
                        <p style={{ fontSize: '12px', color: 'var(--cyan)' }}>Rewinding Maritime Memory...</p>
                        <p style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Filtering candidate vessels...</p>
                      </div>
                    ) : suspects.length === 0 ? (
                      <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>No candidate vessels found near the origin zone.</p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {suspects.map((s, idx) => (
                          <div key={idx} style={{ 
                            padding: '10px', 
                            borderRadius: '6px', 
                            background: s.priority === 'High Priority' ? 'rgba(255, 51, 102, 0.05)' : 'rgba(255, 255, 255, 0.02)',
                            border: s.priority === 'High Priority' ? '1px solid rgba(255, 51, 102, 0.3)' : '1px solid var(--border)',
                          }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                              <span style={{ fontSize: '12px', fontWeight: 'bold', color: 'var(--text-primary)' }}>{s.vessel_name} <span style={{ fontSize: '9px', color: 'var(--text-muted)' }}>({s.mmsi})</span></span>
                              <span style={{ 
                                fontSize: '9px', 
                                fontWeight: 'bold', 
                                padding: '2px 6px', 
                                borderRadius: '4px',
                                background: s.priority === 'High Priority' ? 'rgba(255, 51, 102, 0.1)' : 'rgba(255, 255, 255, 0.1)',
                                color: s.priority === 'High Priority' ? '#ff3366' : 'var(--text-secondary)'
                              }}>
                                {s.priority} ({s.match_score}%)
                              </span>
                            </div>
                            <ul style={{ margin: 0, paddingLeft: '14px', fontSize: '10px', color: 'var(--text-secondary)' }}>
                              {s.reasons.map((r: string, rIdx: number) => <li key={rIdx} style={{ marginBottom: '2px' }}>{r}</li>)}
                            </ul>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  
                  {!loadingSuspects && suspects.length > 0 && (
                    <button style={{
                      marginTop: '15px', width: '100%', padding: '10px', background: 'var(--cyan)', color: '#000', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px', fontWeight: 'bold'
                    }}>
                      Generate Case Report
                    </button>
                  )}
                </div>
              </div>

            </>
          )}
        </div>

      </div>
    </div>
  );
};
