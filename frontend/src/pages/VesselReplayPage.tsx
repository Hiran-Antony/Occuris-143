import { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Polyline, CircleMarker, Popup, ImageOverlay, Rectangle, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { vesselApi, forensicsApi } from '../api/client';
import StickyHonestyFooter from '../components/common/StickyHonestyFooter';

interface SuspectConfig {
  mmsi: string;
  name: string;
  type: string;
  flag: string;
  status: string;
  statusColor: string;
  corridor: string;
  desc: string;
  mapCenter: [number, number];
  mapZoom: number;
  anomalyStart: string;
  anomalyEnd: string;
  anomalyLabel: string;
  normalLabel: string;
  anomalyBadge: string;
  associatedSar: string;
  milestones: { time: string; label: string; highlight?: boolean }[];
}

const SUSPECT_VESSELS: SuspectConfig[] = [
  {
    mmsi: 'V004',
    name: 'TRUE SOURCE',
    type: 'Crude Oil Tanker',
    flag: '🇮🇳 India',
    status: 'Selected Candidate (94%)',
    statusColor: '#ff3366',
    corridor: 'Arabian Sea Transit (Gate A 59.0°E → Gate D 70.0°E)',
    desc: 'Matches SAR oil slick signature. Transponder remains online, but physical footprint correlates heavily with slick inception zone.',
    mapCenter: [18.5, 64.5],
    mapZoom: 6.5,
    anomalyStart: '2024-03-15T06:00:00Z',
    anomalyEnd: '2024-03-15T09:00:00Z',
    anomalyLabel: '🚨 CRUDE SPILL INCEPTION ZONE INTERSECTION',
    normalLabel: 'TRANSPONDER ONLINE · REGULAR PASSAGE',
    anomalyBadge: '🚨 SAR SLICK MATCH',
    associatedSar: 'sar_03.png',
    milestones: [
      { time: '00:00 UTC', label: 'Tracking Begins' },
      { time: '04:00 UTC', label: 'Entering Risk Zone' },
      { time: '07:30 UTC', label: 'Slick Intersection', highlight: true },
      { time: '08:40 UTC', label: 'S1 SAR Slick Detected' },
      { time: '11:59 UTC', label: 'Tracking Ends' }
    ]
  },
  {
    mmsi: 'V003',
    name: 'ARABIAN PHANTOM',
    type: 'Container Cargo',
    flag: '🇸🇬 Singapore',
    status: 'SECONDARY CANDIDATE (78%)',
    statusColor: '#ffb800',
    corridor: 'Arabian Sea Transit (Gate B 22.0°N → Gate C 14.5°N)',
    desc: 'Deliberate 35-minute transponder blackout recorded at 03:00 UTC.',
    mapCenter: [18.5, 64.5],
    mapZoom: 6.5,
    anomalyStart: '2024-03-15T03:00:00Z',
    anomalyEnd: '2024-03-15T03:40:00Z',
    anomalyLabel: 'AIS TRANSPONDER SILENCED (DARK VESSEL)',
    normalLabel: 'TRANSPONDER ONLINE · FAIRWAY TRANSIT 11.5 KTS',
    anomalyBadge: 'AIS BLACKOUT ACTIVE',
    associatedSar: 'sar_01.png',
    milestones: [
      { time: '00:00 UTC', label: 'Tracking Begins' },
      { time: '03:00 UTC', label: 'AIS Gap Begins', highlight: true },
      { time: '03:35 UTC', label: 'AIS Resumes', highlight: true },
      { time: '08:40 UTC', label: 'S1 SAR Detection' },
      { time: '11:59 UTC', label: 'Tracking Ends' }
    ]
  },
  {
    mmsi: 'V002',
    name: 'GULF CARRIER',
    type: 'Product Tanker',
    flag: '🇲🇾 Malaysia',
    status: 'OFFSHORE SUSPECT (55%)',
    statusColor: '#ff8800',
    corridor: 'Arabian Sea Transit (Gate A 59.0°E → Gate D 70.0°E)',
    desc: 'Implausible 150+ nautical mile position jump recorded at 02:00 UTC indicating AIS spoofing.',
    mapCenter: [18.5, 64.5],
    mapZoom: 6.5,
    anomalyStart: '2024-03-15T01:50:00Z',
    anomalyEnd: '2024-03-15T02:20:00Z',
    anomalyLabel: 'SEVERE POSITION JUMP (>150 NM) - SPOOFING DETECTED',
    normalLabel: 'TRANSPONDER ONLINE · SHELF CRUISE 10.0 KTS',
    anomalyBadge: 'SPOOFED LOCATION',
    associatedSar: 'sar_02.png',
    milestones: [
      { time: '00:00 UTC', label: 'Tracking Begins' },
      { time: '01:50 UTC', label: 'Last Valid Ping' },
      { time: '02:00 UTC', label: 'Position Jump (Spoofing)', highlight: true },
      { time: '08:40 UTC', label: 'S1 SAR Detection' },
      { time: '11:59 UTC', label: 'Tracking Ends' }
    ]
  }
];

function MapController({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo(center, zoom, { duration: 1.0 });
  }, [center[0], center[1], zoom, map]);
  return null;
}

export default function VesselReplayPage() {
  const [mapLayer, setMapLayer] = useState<'sentinel' | 'dark' | 'osm'>('sentinel');
  const [selectedMmsi, setSelectedMmsi] = useState<string>('V004');
  const [positions, setPositions] = useState<any[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playSpeed, setPlaySpeed] = useState<number>(1);
  const [incidents, setIncidents] = useState<any[]>([]);
  const animRef = useRef<any>(null);

  const activeVessel = SUSPECT_VESSELS.find(v => v.mmsi === selectedMmsi) || SUSPECT_VESSELS[0];

  useEffect(() => {
    forensicsApi.getIncidents().then(data => setIncidents(data)).catch(() => {});
  }, []);

  // Fetch track when selected vessel changes
  useEffect(() => {
    setIsPlaying(false);
    setCurrentIndex(0);
    vesselApi.getTrack(selectedMmsi).then(data => {
      if (data?.positions && data.positions.length > 0) {
        const sorted = [...data.positions].sort(
          (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );
        setPositions(sorted);
      } else {
        setPositions([]);
      }
    }).catch(err => {
      console.error('Failed to load vessel track:', err);
      setPositions([]);
    });
  }, [selectedMmsi]);

  // Animation playback interval
  useEffect(() => {
    if (isPlaying && positions.length > 0) {
      const stepMs = Math.max(50, Math.floor(250 / playSpeed));
      animRef.current = setInterval(() => {
        setCurrentIndex(prev => {
          if (prev >= positions.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, stepMs);
    } else {
      if (animRef.current) clearInterval(animRef.current);
    }
    return () => {
      if (animRef.current) clearInterval(animRef.current);
    };
  }, [isPlaying, positions.length, playSpeed]);

  const currentPos = positions[currentIndex] || null;
  const currentTime = currentPos ? new Date(currentPos.timestamp) : new Date('2024-01-15T06:30:00Z');

  // Check if current position falls inside the vessel's anomaly window
  const anomStart = new Date(activeVessel.anomalyStart);
  const anomEnd = new Date(activeVessel.anomalyEnd);
  const isInsideAnomaly = currentTime >= anomStart && currentTime <= anomEnd;

  // Render past trail up to current index and remaining planned track
  const pastCoords: [number, number][] = positions.slice(0, currentIndex + 1).map(p => [p.lat || p.latitude, p.lon || p.longitude]);
  const fullCoords: [number, number][] = positions.map(p => [p.lat || p.latitude, p.lon || p.longitude]);

  // Jump to anomaly event helper
  const handleJumpToAnomaly = () => {
    setIsPlaying(false);
    const targetIdx = positions.findIndex(p => new Date(p.timestamp) >= anomStart);
    if (targetIdx !== -1) {
      setCurrentIndex(targetIdx);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg-primary)', color: 'var(--text-primary)', overflow: 'hidden' }}>
      {/* Top Header */}
      <div style={{ padding: '12px 24px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 20 }}>▶️</span>
            <h1 style={{ fontSize: 18, fontWeight: 700, letterSpacing: 0.5, margin: 0 }}>
              Vessel Replay & Spatiotemporal Track Reconstruction
            </h1>
            <span
              style={{
                fontSize: 10,
                padding: '3px 9px',
                borderRadius: 4,
                background: isInsideAnomaly ? 'rgba(255, 51, 102, 0.2)' : 'rgba(0, 212, 255, 0.15)',
                color: isInsideAnomaly ? 'var(--red)' : 'var(--cyan)',
                border: `1px solid ${isInsideAnomaly ? 'var(--red)' : 'var(--cyan)'}`,
                fontWeight: 700
              }}
            >
              {isInsideAnomaly ? activeVessel.anomalyBadge : 'TRANSPONDER ONLINE'}
            </span>
          </div>

          {/* Map Layers */}
          <div style={{ display: 'flex', gap: 6, background: '#030a12', padding: 4, borderRadius: 8, border: '1px solid var(--border)' }}>
            <button
              onClick={() => setMapLayer('sentinel')}
              style={{
                padding: '4px 10px',
                borderRadius: 6,
                border: 'none',
                background: mapLayer === 'sentinel' ? 'var(--cyan)' : 'transparent',
                color: mapLayer === 'sentinel' ? '#000' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: 11,
                cursor: 'pointer'
              }}
            >
              🛰️ Sentinel-2
            </button>
            <button
              onClick={() => setMapLayer('dark')}
              style={{
                padding: '4px 10px',
                borderRadius: 6,
                border: 'none',
                background: mapLayer === 'dark' ? 'var(--cyan)' : 'transparent',
                color: mapLayer === 'dark' ? '#000' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: 11,
                cursor: 'pointer'
              }}
            >
              🌊 Dark Marine
            </button>
            <button
              onClick={() => setMapLayer('osm')}
              style={{
                padding: '4px 10px',
                borderRadius: 6,
                border: 'none',
                background: mapLayer === 'osm' ? 'var(--cyan)' : 'transparent',
                color: mapLayer === 'osm' ? '#000' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: 11,
                cursor: 'pointer'
              }}
            >
              🗺️ Street Map
            </button>
          </div>
        </div>

        {/* 3 Suspect Ship Selector Bar */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Target Vessel:
          </span>
          {SUSPECT_VESSELS.map(v => {
            const isSel = v.mmsi === selectedMmsi;
            return (
              <button
                key={v.mmsi}
                onClick={() => setSelectedMmsi(v.mmsi)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '7px 14px',
                  borderRadius: 8,
                  border: isSel ? `1.5px solid ${v.statusColor}` : '1px solid rgba(255, 255, 255, 0.1)',
                  background: isSel ? `${v.statusColor}22` : 'rgba(255, 255, 255, 0.03)',
                  boxShadow: isSel ? `0 0 12px ${v.statusColor}44` : 'none',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  textAlign: 'left'
                }}
              >
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: v.statusColor, boxShadow: isSel ? `0 0 6px ${v.statusColor}` : 'none' }} />
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: isSel ? '#ffffff' : 'var(--text-primary)' }}>
                    {v.name}
                  </div>
                  <div style={{ fontSize: 10, color: isSel ? v.statusColor : 'var(--text-muted)' }}>
                    {v.type} · MMSI {v.mmsi}
                  </div>
                </div>
              </button>
            );
          })}

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
              {activeVessel.corridor}
            </span>
            <button
              onClick={handleJumpToAnomaly}
              style={{
                padding: '6px 12px',
                borderRadius: 6,
                background: 'rgba(255, 51, 102, 0.15)',
                border: '1px solid #ff3366',
                color: '#ff3366',
                fontWeight: 700,
                fontSize: 11,
                cursor: 'pointer'
              }}
            >
              ⚡ Jump to Anomaly Window
            </button>
          </div>
        </div>
      </div>

      {/* Main Map View */}
      <div style={{ flex: 1, position: 'relative' }}>
        <MapContainer center={activeVessel.mapCenter} zoom={activeVessel.mapZoom} style={{ height: '100%', width: '100%', background: '#020c18' }}>
          <MapController center={activeVessel.mapCenter} zoom={activeVessel.mapZoom} />

          {mapLayer === 'sentinel' && (
            <>
              <TileLayer
                url="https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                attribution="&copy; Esri World Imagery"
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

          {/* Oceanic Corridor Gateways (Arabian Sea) */}
          <Polyline positions={[[14.5, 59.0], [22.0, 59.0]]} pathOptions={{ color: '#00ff88', weight: 2.5, dashArray: '6 4' }} />
          <Polyline positions={[[14.5, 70.0], [22.0, 70.0]]} pathOptions={{ color: '#ff6b35', weight: 2.5, dashArray: '6 4' }} />

          {/* Real Sentinel SAR Oil Spill Overlays */}
          {incidents.map((inc: any) => {
            const lat = inc.geometry?.centroid_lat || 18.5;
            const lon = inc.geometry?.centroid_lon || 64.5;
            const sarFile = inc.sar_image_path ? inc.sar_image_path.split(/[\\/]/).pop() : '000002.jpg';
            const maskFile = inc.mask_path ? inc.mask_path.split(/[\\/]/).pop() : '000002_mask.png';
            const isAssociated = sarFile === activeVessel.associatedSar;

            const spanLat = 0.05;
            const spanLon = 0.05 / Math.cos((lat * Math.PI) / 180);
            const b: [[number, number], [number, number]] = [
              [lat - spanLat, lon - spanLon],
              [lat + spanLat, lon + spanLon]
            ];

            return (
              <div key={inc.id}>
                <ImageOverlay url={`http://localhost:8080/sar/${sarFile}`} bounds={b} opacity={isAssociated ? 0.95 : 0.4} />
                <ImageOverlay url={`http://localhost:8080/masks/${maskFile}`} bounds={b} opacity={isAssociated ? 0.85 : 0.3} />
                <Rectangle
                  bounds={b}
                  pathOptions={{
                    color: isAssociated ? activeVessel.statusColor : '#00d4ff',
                    weight: isAssociated ? 2 : 1,
                    dashArray: '4 4'
                  }}
                />
                <CircleMarker
                  center={[lat, lon]}
                  radius={isAssociated ? 8 : 5}
                  pathOptions={{
                    color: isAssociated ? activeVessel.statusColor : '#00d4ff',
                    fillColor: isAssociated ? activeVessel.statusColor : '#00d4ff',
                    fillOpacity: 0.9
                  }}
                >
                  <Popup>
                    <div style={{ color: '#020c18', fontSize: 11, minWidth: 160 }}>
                      <strong>Sentinel-1 SAR Slick #{inc.id}</strong><br />
                      Acquisition: 18:40 UTC<br />
                      Area: {inc.geometry?.area_km2?.toFixed(2)} km²<br />
                      Sector: {lat.toFixed(2)}°N, {lon.toFixed(2)}°E<br />
                      {isAssociated && (
                        <div style={{ marginTop: 4, color: activeVessel.statusColor, fontWeight: 'bold' }}>
                          ⚡ Linked to {activeVessel.name}
                        </div>
                      )}
                    </div>
                  </Popup>
                </CircleMarker>
              </div>
            );
          })}

          {/* Full Planned/Track Line (subtle faint dashed line) */}
          <Polyline positions={fullCoords} pathOptions={{ color: 'rgba(255, 255, 255, 0.2)', weight: 2, dashArray: '4 6' }} />

          {/* Replayed Past Vessel Trail (glowing vibrant line) */}
          <Polyline
            positions={pastCoords}
            pathOptions={{
              color: isInsideAnomaly ? '#ff3366' : 'var(--cyan)',
              weight: 3.5,
              dashArray: isInsideAnomaly ? '6 4' : undefined
            }}
          />

          {/* Current Animated Vessel Marker */}
          {currentPos && (
            <CircleMarker
              center={[currentPos.lat || currentPos.latitude, currentPos.lon || currentPos.longitude]}
              radius={isInsideAnomaly ? 11 : 8}
              pathOptions={{
                color: isInsideAnomaly ? '#ff3366' : '#00ffff',
                fillColor: isInsideAnomaly ? '#ff3366' : '#00d4ff',
                fillOpacity: 1,
                weight: 2.5
              }}
            >
              <Popup>
                <div style={{ color: '#020c18', fontSize: 12, minWidth: 190 }}>
                  <strong style={{ fontSize: 13 }}>{activeVessel.name}</strong><br />
                  <span style={{ fontSize: 10, color: '#555' }}>MMSI: {activeVessel.mmsi} · {activeVessel.flag}</span><br />
                  <strong>Time:</strong> {new Date(currentPos.timestamp).toUTCString()}<br />
                  <strong>Speed:</strong> {currentPos.speed} kts · <strong>Course:</strong> {currentPos.course}°<br />
                  {isInsideAnomaly ? (
                    <div style={{ marginTop: 4, color: '#ff3366', fontWeight: 'bold' }}>
                      {activeVessel.anomalyBadge}
                    </div>
                  ) : (
                    <div style={{ marginTop: 4, color: '#008800', fontWeight: 'bold' }}>
                      ✓ Normal Underway Transit
                    </div>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          )}
        </MapContainer>

        {/* Floating Replay Control Panel */}
        <div
          style={{
            position: 'absolute',
            bottom: 20,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 1000,
            width: '92%',
            maxWidth: 900,
            background: 'rgba(3, 10, 18, 0.94)',
            backdropFilter: 'blur(12px)',
            padding: '16px 24px',
            borderRadius: 14,
            border: '1px solid var(--border)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.6)'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                style={{
                  background: isPlaying ? 'var(--amber)' : 'var(--cyan)',
                  color: '#000',
                  border: 'none',
                  padding: '9px 20px',
                  borderRadius: 8,
                  fontWeight: 800,
                  fontSize: 13,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  boxShadow: isPlaying ? '0 0 10px rgba(255, 184, 0, 0.4)' : '0 0 10px rgba(0, 212, 255, 0.4)'
                }}
              >
                {isPlaying ? '⏸ Pause' : '▶ Play Replay'}
              </button>

              {/* Speed Multipliers */}
              <div style={{ display: 'flex', gap: 4, background: 'rgba(255,255,255,0.05)', padding: 3, borderRadius: 6, border: '1px solid var(--border)' }}>
                {[1, 3, 8].map(spd => (
                  <button
                    key={spd}
                    onClick={() => setPlaySpeed(spd)}
                    style={{
                      padding: '3px 8px',
                      borderRadius: 4,
                      border: 'none',
                      background: playSpeed === spd ? 'var(--cyan)' : 'transparent',
                      color: playSpeed === spd ? '#000' : 'var(--text-secondary)',
                      fontWeight: 700,
                      fontSize: 10,
                      cursor: 'pointer'
                    }}
                  >
                    {spd}x
                  </button>
                ))}
              </div>

              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace' }}>
                  {currentTime.toUTCString()}
                </div>
                <div style={{ fontSize: 11, color: isInsideAnomaly ? 'var(--red)' : 'var(--text-secondary)', fontWeight: isInsideAnomaly ? 700 : 500 }}>
                  {isInsideAnomaly ? activeVessel.anomalyLabel : activeVessel.normalLabel}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 20, textAlign: 'right' }}>
              <div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>SPEED</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--cyan)', fontFamily: 'JetBrains Mono, monospace' }}>
                  {currentPos?.sog?.toFixed(1) || '10.0'} kts
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>HEADING</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--cyan)', fontFamily: 'JetBrains Mono, monospace' }}>
                  {currentPos?.cog ? `${Math.round(currentPos.cog)}°` : '092°'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>PROGRESS</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace' }}>
                  {positions.length > 0 ? Math.round((currentIndex / (positions.length - 1)) * 100) : 0}%
                </div>
              </div>
            </div>
          </div>

          {/* Smooth Drag-to-Scrub Slider with AIS Gaps Shaded Red */}
          {(() => {
            let anomStartPct = 20;
            let anomEndPct = 35;
            if (positions.length > 1) {
              const sIdx = positions.findIndex(p => new Date(p.timestamp) >= anomStart);
              const eIdx = positions.findIndex(p => new Date(p.timestamp) >= anomEnd);
              const s = sIdx >= 0 ? sIdx : 0;
              const e = eIdx >= 0 ? eIdx : positions.length - 1;
              anomStartPct = Math.round((s / (positions.length - 1)) * 100);
              anomEndPct = Math.round((e / (positions.length - 1)) * 100);
            }
            return (
              <div style={{ position: 'relative', width: '100%', marginBottom: 8, height: '24px', display: 'flex', alignItems: 'center' }}>
                <div
                  style={{
                    position: 'absolute',
                    top: '50%',
                    left: 0,
                    right: 0,
                    height: '6px',
                    transform: 'translateY(-50%)',
                    borderRadius: '3px',
                    background: `linear-gradient(to right, rgba(0, 212, 255, 0.3) 0%, rgba(0, 212, 255, 0.3) ${anomStartPct}%, rgba(255, 51, 102, 0.85) ${anomStartPct}%, rgba(255, 51, 102, 0.85) ${anomEndPct}%, rgba(0, 212, 255, 0.3) ${anomEndPct}%, rgba(0, 212, 255, 0.3) 100%)`,
                    pointerEvents: 'none',
                  }}
                />
                <input
                  type="range"
                  min={0}
                  max={Math.max(0, positions.length - 1)}
                  value={currentIndex}
                  onChange={(e) => {
                    setIsPlaying(false);
                    setCurrentIndex(parseInt(e.target.value));
                  }}
                  style={{
                    position: 'relative',
                    width: '100%',
                    accentColor: isInsideAnomaly ? 'var(--red)' : 'var(--cyan)',
                    cursor: 'pointer',
                    background: 'transparent',
                    zIndex: 2,
                  }}
                />
              </div>
            );
          })()}

          {/* Dynamic Milestones for the active vessel */}
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)' }}>
            {activeVessel.milestones.map((m, idx) => (
              <span
                key={idx}
                style={{
                  color: m.highlight ? 'var(--red)' : 'var(--text-muted)',
                  fontWeight: m.highlight ? 700 : 500
                }}
              >
                {m.time} ({m.label})
              </span>
            ))}
          </div>
        </div>
      </div>
      <StickyHonestyFooter />
    </div>
  );
}
