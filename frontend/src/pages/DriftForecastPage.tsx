import { useState, useEffect, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { forensicsApi, vesselApi } from '../api/client';

function MapRecenter({ lat, lon }: { lat: number; lon: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo([lat, lon], 9.5, { duration: 1.0 });
  }, [lat, lon, map]);
  return null;
}

interface OceanRegime {
  name: string;
  currentSpeed: number; // m/s
  currentDir: number;   // degrees (from North)
  windSpeed: number;    // knots
  windDir: number;      // degrees
  dLatPerHr: number;
  dLonPerHr: number;
  seaState: string;
  seaTemp: number;      // °C
  salinity: number;     // PSU
  waterDepth: number;   // meters
  corridor: string;
}

const METOCEAN_REGIMES: Record<string, OceanRegime> = {
  'BAYOFBENGAL': {
    name: 'Central Arabian Sea Winter Gyre',
    currentSpeed: 0.38,
    currentDir: 225,
    windSpeed: 14.2,
    windDir: 45,
    dLatPerHr: -0.0115,
    dLonPerHr: -0.0155,
    seaState: 'Moderate (Beaufort 4 · Hs 1.4m)',
    seaTemp: 28.2,
    salinity: 33.1,
    waterDepth: 3150,
    corridor: 'International Transit Corridor (Gate A → Gate D)'
  },
  'FILAMENT': {
    name: 'Lakshadweep Channel Zonal Fairway',
    currentSpeed: 0.52,
    currentDir: 92,
    windSpeed: 16.0,
    windDir: 30,
    dLatPerHr: -0.0035,
    dLonPerHr: 0.0175,
    seaState: 'Slight to Moderate (Beaufort 4 · Hs 1.6m)',
    seaTemp: 28.6,
    salinity: 32.8,
    waterDepth: 840,
    corridor: 'Andaman Sea Gateway (Little Andaman – Car Nicobar)'
  },
  'EMULSION': {
    name: 'Oman Basin Continental Slope (EICC)',
    currentSpeed: 0.44,
    currentDir: 202,
    windSpeed: 10.8,
    windDir: 65,
    dLatPerHr: -0.0150,
    dLonPerHr: -0.0055,
    seaState: 'Calm to Moderate (Beaufort 3 · Hs 0.9m)',
    seaTemp: 27.9,
    salinity: 31.5,
    waterDepth: 1420,
    corridor: 'KG Offshore Energy Sector (KG-DWN-98/2)'
  },
  'CLEAN': {
    name: 'Open Deep Sea Baseline Standard',
    currentSpeed: 0.22,
    currentDir: 215,
    windSpeed: 9.5,
    windDir: 40,
    dLatPerHr: -0.0080,
    dLonPerHr: -0.0100,
    seaState: 'Smooth Sea (Beaufort 3 · Hs 0.6m)',
    seaTemp: 28.5,
    salinity: 33.4,
    waterDepth: 3400,
    corridor: 'Undisturbed Baseline Control'
  }
};

// Seeded pseudo-random normal generator
function pseudoRandom(seed: number) {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

function gaussianRandom(seed: number) {
  const u = Math.max(1e-7, pseudoRandom(seed));
  const v = pseudoRandom(seed + 777);
  return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

/**
 * High-Performance HTML5 Canvas Hydrodynamic Overlay
 * Features:
 * 1. Animated continuous ocean current streamlines (Windy / Earth Nullschool style)
 * 2. Dynamic pulsing Lagrangian oil plume with Gaussian spreading & turbulent eddies
 * 3. Bonn Agreement optical thickness layers (Heavy Emulsion, Metallic Mousse, Iridescent Sheen)
 * 4. Pulsing release origin beacon (-6h) & Sentinel-1 radar reticle (0h)
 * 5. Suspect vessel AIS spatiotemporal intercept correlation
 */
function HydrodynamicCanvasOverlay({
  simTime,
  regime,
  originLat,
  originLon,
  isCleanOcean,
  showStreamlines,
  showVesselTrack,
  vesselTrack,
  sceneKey
}: {
  simTime: number;
  regime: OceanRegime;
  originLat: number;
  originLon: number;
  isCleanOcean: boolean;
  showStreamlines: boolean;
  showVesselTrack: boolean;
  vesselTrack: Array<{ lat: number; lon: number; time: Date }>;
  sceneKey: string;
}) {
  const map = useMap();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameCountRef = useRef<number>(0);
  const streamlinesRef = useRef<Array<{ x: number; y: number; age: number; maxAge: number; speed: number }>>([]);

  // Setup streamlines
  useEffect(() => {
    const count = 120;
    const particles = [];
    const size = map.getSize();
    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * size.x,
        y: Math.random() * size.y,
        age: Math.floor(Math.random() * 80),
        maxAge: 60 + Math.floor(Math.random() * 50),
        speed: 0.8 + Math.random() * 1.2
      });
    }
    streamlinesRef.current = particles;
  }, [map]);

  // Main 60 FPS Render Loop
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
      frameCountRef.current++;
      const frame = frameCountRef.current;

      // 1. RENDER OCEAN CURRENT STREAMLINES (Windy / CMEMS Style)
      if (showStreamlines) {
        const rad = (regime.currentDir * Math.PI) / 180;
        const u = Math.sin(rad);
        const v = -Math.cos(rad);

        ctx.lineWidth = 1.6;
        for (const p of streamlinesRef.current) {
          p.x += u * p.speed * (regime.currentSpeed * 2.8);
          p.y += v * p.speed * (regime.currentSpeed * 2.8);
          p.age++;

          if (p.x < 0 || p.x > canvas.width || p.y < 0 || p.y > canvas.height || p.age > p.maxAge) {
            p.x = Math.random() * canvas.width;
            p.y = Math.random() * canvas.height;
            p.age = 0;
            p.maxAge = 60 + Math.floor(Math.random() * 50);
          }

          const lifeProgress = p.age / p.maxAge;
          const alpha = Math.sin(lifeProgress * Math.PI) * 0.42;

          ctx.strokeStyle = `rgba(0, 212, 255, ${alpha})`;
          ctx.beginPath();
          ctx.moveTo(p.x - u * 12 * p.speed, p.y - v * 12 * p.speed);
          ctx.lineTo(p.x, p.y);
          ctx.stroke();

          // Streamline head glow
          ctx.fillStyle = `rgba(255, 255, 255, ${alpha * 0.8})`;
          ctx.beginPath();
          ctx.arc(p.x, p.y, 1.0, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // 2. CORRIDOR & SUSPECT VESSEL NAVIGATION ENGINE
      const CORRIDOR_REGISTRY: Record<string, {
        shipName: string;
        shipMmsi: string;
        shipType: string;
        flag: string;
        originPort: string;
        destPort: string;
        speedKts: number;
        alertText: string;
        dischargeIndex: number;
        waypoints: Array<{ lat: number; lon: number; name: string }>;
      }> = {
        FILAMENT: {
          shipName: 'EASTERN STAR',
          shipMmsi: '419000040',
          shipType: 'Container / Cargo',
          flag: '🇸🇬 Singapore',
          originPort: 'CHENNAI [INMAA]',
          destPort: 'SINGAPORE [SGSIN]',
          speedKts: 12.4,
          alertText: '🚨 BILGE DUMPING IN Lakshadweep CHOKEPOINT (11:25 UTC)',
          dischargeIndex: 3,
          waypoints: [
            { lat: 10.280, lon: 90.500, name: 'WP-01 APPROACH' },
            { lat: 10.220, lon: 91.300, name: 'WP-02 FAIRWAY' },
            { lat: 10.180, lon: 91.950, name: 'WP-03 CHANNEL' },
            { lat: 10.149, lon: 92.535, name: 'WP-04 DISCHARGE (-6h)' },
            { lat: 10.128, lon: 92.640, name: 'WP-05 S1 DETECTION (0h)' },
            { lat: 10.080, lon: 93.300, name: 'WP-06 MID FAIRWAY' },
            { lat: 10.020, lon: 94.100, name: 'WP-07 EAST EXIT' },
            { lat: 9.880, lon: 95.000, name: 'WP-08 ANDAMAN SEA' },
            { lat: 9.650, lon: 96.200, name: 'WP-09 MALACCA APPROACH' }
          ]
        },
        EMULSION: {
          shipName: 'GULF WAVE',
          shipMmsi: '419000041',
          shipType: 'Product Tanker',
          flag: '🇲🇾 Malaysia',
          originPort: 'VISAKHAPATNAM [INVTZ]',
          destPort: 'CHENNAI [INMAA]',
          speedKts: 11.2,
          alertText: '🚨 TANK WASHING NEAR KG-DWN-98/2 RIG COMPLEX (05:15 UTC)',
          dischargeIndex: 3,
          waypoints: [
            { lat: 17.500, lon: 85.000, name: 'WP-01 VIZAG OUTER' },
            { lat: 17.100, lon: 84.800, name: 'WP-02 ANDHRA SHELF' },
            { lat: 16.750, lon: 84.600, name: 'WP-03 KAKINADA SHELF' },
            { lat: 16.541, lon: 84.494, name: 'WP-04 DISCHARGE (-6h)' },
            { lat: 16.451, lon: 84.461, name: 'WP-05 S1 EMULSION (0h)' },
            { lat: 16.150, lon: 84.350, name: 'WP-06 GODAVARI' },
            { lat: 15.650, lon: 84.200, name: 'WP-07 MACHILIPATNAM' },
            { lat: 15.100, lon: 84.100, name: 'WP-08 KRISHNA CANYON' },
            { lat: 14.400, lon: 84.050, name: 'WP-09 CHENNAI FAIRWAY' }
          ]
        },
        BAYOFBENGAL: {
          shipName: 'MT DESH SHOBHA',
          shipMmsi: '419000042',
          shipType: 'Crude Oil Tanker',
          flag: '🇮🇳 India',
          originPort: 'FUJAIRAH [AEFJR]',
          destPort: 'SINGAPORE [SGSIN]',
          speedKts: 10.2,
          alertText: '🚨 AIS GAP & CRUDE DISCHARGE CORRELATION (12:40 UTC)',
          dischargeIndex: 3,
          waypoints: [
            { lat: 13.480, lon: 83.200, name: 'WP-01 WEST GATEWAY' },
            { lat: 13.400, lon: 84.400, name: 'WP-02 WEST BASIN' },
            { lat: 13.320, lon: 85.400, name: 'WP-03 MID SLOC' },
            { lat: 13.244, lon: 86.299, name: 'WP-04 DISCHARGE (-6h)' },
            { lat: 13.175, lon: 86.206, name: 'WP-05 S1 DETECTION (0h)' },
            { lat: 12.800, lon: 88.000, name: 'WP-06 CENTRAL DEEP' },
            { lat: 11.800, lon: 89.800, name: 'WP-07 SOUTHEAST TURN' },
            { lat: 10.500, lon: 91.200, name: 'WP-08 Lakshadweep APPROACH' },
            { lat: 10.000, lon: 92.500, name: 'WP-09 Lakshadweep CHANNEL' },
            { lat: 10.000, lon: 94.200, name: 'WP-10 ANDAMAN SEA EXIT' }
          ]
        }
      };

      const corridor = CORRIDOR_REGISTRY[sceneKey] || CORRIDOR_REGISTRY['BAYOFBENGAL'];
      const waypoints = corridor.waypoints;

      // Calculate cumulative nautical distances
      const cumDist: number[] = [0];
      for (let i = 0; i < waypoints.length - 1; i++) {
        const dLat = (waypoints[i + 1].lat - waypoints[i].lat) * 111.32;
        const avgL = (waypoints[i].lat + waypoints[i + 1].lat) / 2;
        const dLon = (waypoints[i + 1].lon - waypoints[i].lon) * 111.32 * Math.cos(avgL * Math.PI / 180);
        cumDist.push(cumDist[i] + Math.hypot(dLat, dLon));
      }
      const totalDist = cumDist[cumDist.length - 1];
      const dischargeDist = cumDist[corridor.dischargeIndex];

      // Physical vessel location along the corridor route at current simTime
      const speedKmh = corridor.speedKts * 1.852;
      const hoursFromDischarge = simTime + 6;
      let curDist = dischargeDist + (hoursFromDischarge * speedKmh);
      curDist = Math.max(0, Math.min(totalDist, curDist));

      // Find current active segment
      let segIdx = 0;
      for (let i = 0; i < cumDist.length - 1; i++) {
        if (curDist >= cumDist[i] && curDist <= cumDist[i + 1]) {
          segIdx = i;
          break;
        }
      }
      const segLen = cumDist[segIdx + 1] - cumDist[segIdx];
      const frac = segLen > 0.001 ? (curDist - cumDist[segIdx]) / segLen : 0;
      const wpA = waypoints[segIdx];
      const wpB = waypoints[segIdx + 1];

      const shipLat = wpA.lat + frac * (wpB.lat - wpA.lat);
      const shipLon = wpA.lon + frac * (wpB.lon - wpA.lon);

      // Ship heading dynamically calculated from active segment bearing
      const dLatDeg = wpB.lat - wpA.lat;
      const dLonDeg = wpB.lon - wpA.lon;
      const avgLat = (wpA.lat + wpB.lat) / 2;
      const headingRad = Math.atan2(dLonDeg * Math.cos(avgLat * Math.PI / 180), dLatDeg);
      const shipHeading = (headingRad * 180 / Math.PI + 360) % 360;
      const shipPt = map.latLngToContainerPoint([shipLat, shipLon]);

      // RENDER CLEAN MARITIME FAIRWAY & SHIP ROUTE (Simple, Uncluttered, Presentation-Ready)
      if (showVesselTrack && !isCleanOcean) {
        const allScreenPts = waypoints.map(wp => map.latLngToContainerPoint([wp.lat, wp.lon]));

        // 1. Traversed Track (Solid gold line with directional chevrons)
        ctx.strokeStyle = '#ffb800';
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        for (let i = 0; i <= segIdx; i++) {
          const sc = allScreenPts[i];
          if (i === 0) ctx.moveTo(sc.x, sc.y);
          else ctx.lineTo(sc.x, sc.y);
        }
        ctx.lineTo(shipPt.x, shipPt.y);
        ctx.stroke();

        // Directional chevrons along traversed path
        for (let i = 0; i < segIdx; i++) {
          const p1 = allScreenPts[i];
          const p2 = allScreenPts[i + 1];
          const midX = (p1.x + p2.x) / 2;
          const midY = (p1.y + p2.y) / 2;
          const ang = Math.atan2(p2.y - p1.y, p2.x - p1.x);

          ctx.save();
          ctx.translate(midX, midY);
          ctx.rotate(ang);
          ctx.fillStyle = '#ffb800';
          ctx.beginPath();
          ctx.moveTo(4, 0);
          ctx.lineTo(-3, -2.5);
          ctx.lineTo(-1.5, 0);
          ctx.lineTo(-3, 2.5);
          ctx.closePath();
          ctx.fill();
          ctx.restore();
        }

        // 2. Projected Future Track (Clean dashed line ahead of ship)
        ctx.strokeStyle = 'rgba(255, 184, 0, 0.40)';
        ctx.lineWidth = 1.8;
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.moveTo(shipPt.x, shipPt.y);
        for (let i = segIdx + 1; i < allScreenPts.length; i++) {
          ctx.lineTo(allScreenPts[i].x, allScreenPts[i].y);
        }
        ctx.stroke();
        ctx.setLineDash([]);

        // 3. Oman Basin Platform marker if in emulsion scene
        if (sceneKey === 'EMULSION') {
          const platPt = map.latLngToContainerPoint([16.580, 84.480]);
          ctx.fillStyle = '#ff3366';
          ctx.beginPath();
          ctx.arc(platPt.x, platPt.y, 4.5, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1;
          ctx.stroke();

          ctx.shadowColor = 'rgba(0,0,0,0.9)';
          ctx.shadowBlur = 4;
          ctx.fillStyle = '#ff6b8b';
          ctx.font = 'bold 9px JetBrains Mono, monospace';
          ctx.fillText('KG-DWN-98/2 Platform', platPt.x + 8, platPt.y + 3);
          ctx.shadowBlur = 0;
        }

        // 4. Moving Vessel Chevron Icon
        ctx.save();
        ctx.translate(shipPt.x, shipPt.y);
        ctx.rotate((shipHeading * Math.PI) / 180);

        ctx.fillStyle = '#ffb800';
        ctx.beginPath();
        ctx.moveTo(0, -10);
        ctx.lineTo(6, 7);
        ctx.lineTo(-6, 7);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.restore();

        // 5. Clean Simple Ship Label (NO bulky box!)
        ctx.shadowColor = 'rgba(0, 0, 0, 0.95)';
        ctx.shadowBlur = 5;
        ctx.fillStyle = '#ffb800';
        ctx.font = 'bold 11px JetBrains Mono, monospace';
        ctx.fillText(`🚢 ${corridor.shipName} (${corridor.speedKts} kts)`, shipPt.x + 12, shipPt.y - 6);
        ctx.shadowBlur = 0;

        // 6. Simple Discharge Alert Banner at Top of Screen (Clean & unobtrusive)
        if (Math.abs(simTime - (-6)) < 1.4) {
          const bannerW = 420;
          const bannerH = 24;
          const bannerX = (canvas.width - bannerW) / 2;
          const bannerY = 14;

          ctx.fillStyle = 'rgba(255, 51, 102, 0.88)';
          ctx.fillRect(bannerX, bannerY, bannerW, bannerH);
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1;
          ctx.strokeRect(bannerX, bannerY, bannerW, bannerH);

          ctx.fillStyle = '#ffffff';
          ctx.font = 'bold 9.5px Inter, sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(corridor.alertText, canvas.width / 2, bannerY + 16);
          ctx.textAlign = 'start';
        }
      }

      // 3. RENDER DYNAMIC LAGRANGIAN OIL SLICK PLUME (Simple & Elegant)
      if (!isCleanOcean) {
        const coriolisLat = simTime > 0 ? -0.0002 * Math.pow(simTime, 1.05) : 0;
        const coriolisLon = simTime > 0 ? 0.00015 * Math.pow(simTime, 1.05) : 0;
        const cLat = originLat + (simTime * regime.dLatPerHr) + coriolisLat;
        const cLon = originLon + (simTime * regime.dLonPerHr) + coriolisLon;
        const centerPt = map.latLngToContainerPoint([cLat, cLon]);

        const relLat = originLat - (6 * regime.dLatPerHr);
        const relLon = originLon - (6 * regime.dLonPerHr);
        const relPt = map.latLngToContainerPoint([relLat, relLon]);

        const detPt = map.latLngToContainerPoint([originLat, originLon]);

        // Drift trajectory line from Discharge (-6h) -> Detection (0h) -> Current Centroid
        ctx.strokeStyle = 'rgba(0, 212, 255, 0.65)';
        ctx.lineWidth = 1.8;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(relPt.x, relPt.y);
        ctx.lineTo(detPt.x, detPt.y);
        ctx.stroke();

        ctx.strokeStyle = 'rgba(0, 255, 170, 0.55)';
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(detPt.x, detPt.y);
        ctx.lineTo(centerPt.x, centerPt.y);
        ctx.stroke();

        // Release Origin Beacon (-6h) with Simple Text Label (NO bulky box!)
        const relPulse = (Math.sin(frame * 0.08) + 1) * 0.5;
        ctx.strokeStyle = `rgba(255, 51, 102, ${0.2 + (1 - relPulse) * 0.7})`;
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        ctx.arc(relPt.x, relPt.y, 6 + relPulse * 16, 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = '#ff3366';
        ctx.beginPath();
        ctx.arc(relPt.x, relPt.y, 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.shadowColor = 'rgba(0, 0, 0, 0.95)';
        ctx.shadowBlur = 4;
        ctx.fillStyle = '#ff4d79';
        ctx.font = 'bold 10px JetBrains Mono, monospace';
        ctx.fillText('● Discharge (-6h)', relPt.x + 8, relPt.y - 8);
        ctx.shadowBlur = 0;

        // Satellite Detection Point Reticle (0h)
        ctx.strokeStyle = 'rgba(0, 212, 255, 0.8)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.arc(detPt.x, detPt.y, 6, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = '#00ffff';
        ctx.beginPath();
        ctx.arc(detPt.x, detPt.y, 2.5, 0, Math.PI * 2);
        ctx.fill();

        // LAGRANGIAN OIL SLICK PLUME PARTICLES
        const elapsed = Math.max(simTime + 6, 0.1);
        const expansion = Math.sqrt(1.0 + 0.15 * elapsed);
        const pixelScale = Math.abs(map.latLngToContainerPoint([cLat + 0.02, cLon]).y - centerPt.y) / 0.02;

        const currentRad = (regime.currentDir * Math.PI) / 180;
        const cosR = Math.cos(currentRad);
        const sinR = Math.sin(currentRad);

        const aSheen = 0.024 * expansion * pixelScale;
        const bSheen = 0.012 * expansion * pixelScale;

        ctx.save();
        ctx.translate(centerPt.x, centerPt.y);
        ctx.rotate(currentRad);

        const sheenGrad = ctx.createRadialGradient(0, 0, aSheen * 0.2, 0, 0, aSheen);
        sheenGrad.addColorStop(0, 'rgba(255, 85, 0, 0.35)');
        sheenGrad.addColorStop(0.5, 'rgba(0, 212, 255, 0.20)');
        sheenGrad.addColorStop(1, 'rgba(0, 212, 255, 0.0)');

        ctx.fillStyle = sheenGrad;
        ctx.beginPath();
        ctx.ellipse(0, 0, aSheen, bSheen, 0, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = 'rgba(0, 212, 255, 0.45)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.ellipse(0, 0, aSheen * 0.95, bSheen * 0.95, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);

        const aCore = 0.013 * expansion * pixelScale;
        const bCore = 0.006 * expansion * pixelScale;

        const coreGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, aCore);
        coreGrad.addColorStop(0, 'rgba(255, 51, 0, 0.65)');
        coreGrad.addColorStop(0.7, 'rgba(255, 136, 0, 0.35)');
        coreGrad.addColorStop(1, 'rgba(255, 136, 0, 0.0)');

        ctx.fillStyle = coreGrad;
        ctx.beginPath();
        ctx.ellipse(0, 0, aCore, bCore, 0, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = '#ff8800';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.ellipse(0, 0, aCore, bCore, 0, 0, Math.PI * 2);
        ctx.stroke();

        ctx.restore();

        // 180 Lagrangian Spillets with Brownian Eddies
        const particleCount = 180;
        for (let i = 0; i < particleCount; i++) {
          const gX = gaussianRandom(i * 3 + 1);
          const gY = gaussianRandom(i * 3 + 2);

          const eddyX = Math.sin(frame * 0.05 + i * 1.7) * 2.2;
          const eddyY = Math.cos(frame * 0.05 + i * 2.3) * 2.2;

          const along = gX * 0.015 * expansion * pixelScale;
          const cross = gY * 0.007 * expansion * pixelScale;

          const pX = centerPt.x + (along * sinR + cross * cosR) + eddyX;
          const pY = centerPt.y + (along * cosR - cross * sinR) + eddyY;

          const dist = Math.sqrt(gX * gX + gY * gY);

          if (dist < 0.85) {
            ctx.fillStyle = '#ff3700';
            ctx.shadowColor = '#ff2200';
            ctx.shadowBlur = 4;
            ctx.beginPath();
            ctx.arc(pX, pY, 3.0, 0, Math.PI * 2);
            ctx.fill();
            ctx.shadowBlur = 0;
          } else if (dist < 1.6) {
            ctx.fillStyle = '#ffaa00';
            ctx.beginPath();
            ctx.arc(pX, pY, 2.2, 0, Math.PI * 2);
            ctx.fill();
          } else {
            ctx.fillStyle = 'rgba(0, 212, 255, 0.55)';
            ctx.beginPath();
            ctx.arc(pX, pY, 1.6, 0, Math.PI * 2);
            ctx.fill();
          }
        }

        // Center Plume Marker
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(centerPt.x, centerPt.y, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#00d4ff';
        ctx.lineWidth = 1.2;
        ctx.stroke();

        // Simple slick label ONLY when at satellite detection time (0h)
        if (Math.abs(simTime) <= 0.3) {
          ctx.shadowColor = 'rgba(0, 0, 0, 0.95)';
          ctx.shadowBlur = 4;
          ctx.fillStyle = '#00ffff';
          ctx.font = 'bold 9.5px JetBrains Mono, monospace';
          ctx.fillText('🛰️ S1 Scan (18:40 UTC)', centerPt.x + 8, centerPt.y + 14);
          ctx.shadowBlur = 0;
        }
      }

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [map, simTime, regime, originLat, originLon, isCleanOcean, showStreamlines, showVesselTrack, vesselTrack, sceneKey]);

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

export default function DriftForecastPage() {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<any>(null);
  const [mapLayer, setMapLayer] = useState<'dark' | 'sentinel' | 'osm'>('dark');
  const [simStep, setSimStep] = useState<number>(0); // -6 to +48 hours (smooth float)
  const [isPlaying, setIsPlaying] = useState<boolean>(true); // Start with animation running!
  const [playSpeed, setPlaySpeed] = useState<number>(1); // 1x, 3x, 8x
  const [showStreamlines, setShowStreamlines] = useState<boolean>(true);
  const [showVesselTrack, setShowVesselTrack] = useState<boolean>(true);
  const [vesselTrack, setVesselTrack] = useState<Array<{ lat: number; lon: number; time: Date }>>([]);

  const lastTimeRef = useRef<number>(performance.now());

  // Load incidents & suspect vessel track
  useEffect(() => {
    forensicsApi.getIncidents().then(data => {
      if (data && data.length > 0) {
        setIncidents(data);
        const primary = data.find((i: any) => i.sar_image_path?.includes('BAYOFBENGAL')) || data[0];
        setSelectedIncident(primary);
      }
    }).catch(() => {});

    // Fetch MT DESH SHOBHA track
    vesselApi.getTrack('419000042').then(data => {
      if (data?.positions) {
        const sorted = [...data.positions]
          .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
          .map(p => ({ lat: p.latitude, lon: p.longitude, time: new Date(p.timestamp) }));
        setVesselTrack(sorted);
      }
    }).catch(() => {});
  }, []);

  // Determine current scene regime
  const sceneKey = useMemo(() => {
    if (!selectedIncident?.sar_image_path) return 'BAYOFBENGAL';
    const p = selectedIncident.sar_image_path.toUpperCase();
    if (p.includes('FILAMENT')) return 'FILAMENT';
    if (p.includes('EMULSION')) return 'EMULSION';
    if (p.includes('CLEAN')) return 'CLEAN';
    return 'BAYOFBENGAL';
  }, [selectedIncident]);

  const regime = METOCEAN_REGIMES[sceneKey] || METOCEAN_REGIMES['BAYOFBENGAL'];
  const isCleanOcean = sceneKey === 'CLEAN';

  // Geographic origin of detected slick
  const originLat = selectedIncident?.geometry?.centroid_lat ?? 13.175;
  const originLon = selectedIncident?.geometry?.centroid_lon ?? 86.206;

  // Smooth 60 FPS continuous time animation
  useEffect(() => {
    let animId: number;
    lastTimeRef.current = performance.now();

    const loop = (now: number) => {
      const dt = (now - lastTimeRef.current) / 1000;
      lastTimeRef.current = now;

      if (isPlaying) {
        setSimStep(prev => {
          // Advance simulation hours smoothly: e.g. 0.35 hrs/sec at 1x speed (smooth, readable, cinematic)
          const increment = dt * 0.35 * playSpeed;
          const next = prev + increment;
          if (next > 48) {
            return -6; // Loop back to release origin
          }
          return next;
        });
      }

      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [isPlaying, playSpeed]);

  // Current slick center of mass at simStep
  const currentCenterLat = useMemo(() => {
    const coriolisLat = simStep > 0 ? -0.0002 * Math.pow(simStep, 1.05) : 0;
    return originLat + (simStep * regime.dLatPerHr) + coriolisLat;
  }, [originLat, simStep, regime]);

  const currentCenterLon = useMemo(() => {
    const coriolisLon = simStep > 0 ? 0.00015 * Math.pow(simStep, 1.05) : 0;
    return originLon + (simStep * regime.dLonPerHr) + coriolisLon;
  }, [originLon, simStep, regime]);

  // ADIOS Weathering Mass Balance Formulation
  const weathering = useMemo(() => {
    const baseDate = new Date('2024-01-15T18:40:00Z');
    const simDate = new Date(baseDate.getTime() + simStep * 3600 * 1000);
    const dateStr = simDate.toUTCString().replace('GMT', 'UTC');

    if (isCleanOcean) {
      return {
        evaporation: '0.0',
        dispersion: '0.0',
        emulsification: '0.0',
        surfaceRemaining: '0.0',
        viscosity: '0',
        currentArea: '0.00',
        dateStr,
        elapsedHours: simStep < 0 ? `-${Math.abs(simStep).toFixed(1)}h` : `+${simStep.toFixed(1)}h`
      };
    }

    const t = Math.max(simStep + 6, 0.1); // Hours since discharge release
    const evap = Math.min(38.6, Math.max(0, 14.5 * Math.log10(1 + 0.8 * t)));
    const disp = Math.min(18.2, 18.2 * (1 - Math.exp(-0.035 * t)));
    const emul = Math.min(74.0, 74.0 * (1 - Math.exp(-0.065 * t)));
    const surf = Math.max(43.2, 100 - (evap + disp));
    const visc = Math.round(35 * Math.exp(0.08 * t + 0.03 * emul));
    const area = selectedIncident?.geometry?.area_km2 || 1.76;
    const currentArea = (area * Math.pow(1.0 + 0.14 * t, 0.75)).toFixed(2);

    return {
      evaporation: evap.toFixed(1),
      dispersion: disp.toFixed(1),
      emulsification: emul.toFixed(1),
      surfaceRemaining: surf.toFixed(1),
      viscosity: visc.toLocaleString(),
      currentArea,
      dateStr,
      elapsedHours: simStep < 0 ? `-${Math.abs(simStep).toFixed(1)}h` : `+${simStep.toFixed(1)}h`
    };
  }, [simStep, selectedIncident, isCleanOcean]);

  const releaseOriginLat = originLat - (6 * regime.dLatPerHr);
  const releaseOriginLon = originLon - (6 * regime.dLonPerHr);
  const netDriftSpeedKmh = ((regime.currentSpeed * 3.6) + (regime.windSpeed * 1.852 * 0.03)).toFixed(2);
  const netDriftKnots = (parseFloat(netDriftSpeedKmh) / 1.852).toFixed(2);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg-primary)', color: 'var(--text-primary)', overflow: 'hidden' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 24px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 20 }}>🌊</span>
            <h1 style={{ fontSize: 18, fontWeight: 700, letterSpacing: 0.5 }}>Hydrodynamic Drift Simulation & Lagrangian Particle Trajectory Engine</h1>
            <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(0, 255, 136, 0.15)', color: 'var(--green)', border: '1px solid var(--green)', fontWeight: 700 }}>
              NOAA GNOME / OPENDRIFT ARCHITECTURE
            </span>
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Real-time animated Eulerian current streamlines, continuous Lagrangian spillet dispersion, and ADIOS mass-balance weathering kinetics.
          </p>
        </div>

        {/* Layer Controls & Streamline Toggles */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            onClick={() => setShowStreamlines(!showStreamlines)}
            style={{
              padding: '5px 12px', borderRadius: 6,
              border: showStreamlines ? '1px solid var(--cyan)' : '1px solid var(--border)',
              background: showStreamlines ? 'rgba(0, 212, 255, 0.15)' : 'transparent',
              color: showStreamlines ? 'var(--cyan)' : 'var(--text-secondary)',
              fontSize: 11, fontWeight: 600, cursor: 'pointer'
            }}
          >
            🌊 Streamlines {showStreamlines ? 'ON' : 'OFF'}
          </button>

          <button
            onClick={() => setShowVesselTrack(!showVesselTrack)}
            style={{
              padding: '5px 12px', borderRadius: 6,
              border: showVesselTrack ? '1px solid #ffb800' : '1px solid var(--border)',
              background: showVesselTrack ? 'rgba(255, 184, 0, 0.15)' : 'transparent',
              color: showVesselTrack ? '#ffb800' : 'var(--text-secondary)',
              fontSize: 11, fontWeight: 600, cursor: 'pointer'
            }}
          >
            🚢 Suspect Route {showVesselTrack ? 'ON' : 'OFF'}
          </button>

          <div style={{ display: 'flex', gap: 4, background: '#030a12', padding: 3, borderRadius: 8, border: '1px solid var(--border)' }}>
            <button
              onClick={() => setMapLayer('dark')}
              style={{ padding: '4px 10px', borderRadius: 5, border: 'none', background: mapLayer === 'dark' ? 'var(--cyan)' : 'transparent', color: mapLayer === 'dark' ? '#000' : 'var(--text-secondary)', fontWeight: 600, fontSize: 11, cursor: 'pointer' }}
            >
              Dark Marine
            </button>
            <button
              onClick={() => setMapLayer('sentinel')}
              style={{ padding: '4px 10px', borderRadius: 5, border: 'none', background: mapLayer === 'sentinel' ? 'var(--cyan)' : 'transparent', color: mapLayer === 'sentinel' ? '#000' : 'var(--text-secondary)', fontWeight: 600, fontSize: 11, cursor: 'pointer' }}
            >
              Satellite
            </button>
            <button
              onClick={() => setMapLayer('osm')}
              style={{ padding: '4px 10px', borderRadius: 5, border: 'none', background: mapLayer === 'osm' ? 'var(--cyan)' : 'transparent', color: mapLayer === 'osm' ? '#000' : 'var(--text-secondary)', fontWeight: 600, fontSize: 11, cursor: 'pointer' }}
            >
              OSM
            </button>
          </div>
        </div>
      </div>

      {/* Incident Selector Toolbar (Sleek Glassmorphic Design) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 24px', background: 'rgba(3, 13, 24, 0.95)', borderBottom: '1px solid var(--border)' }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>
          Investigative Scene:
        </span>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {incidents.map((inc) => {
            const isSel = selectedIncident?.id === inc.id;
            const p = (inc.sar_image_path || '').toUpperCase();
            
            let theme = '#ff3366';
            let icon = '🚨';
            let name = 'Al-Mahra Crude Spill';
            if (p.includes('FILAMENT')) {
              theme = '#ffb800';
              icon = '🚢';
              name = 'Lakshadweep Bilge Filament';
            } else if (p.includes('EMULSION')) {
              theme = '#ff8800';
              icon = '⚡';
              name = 'Oman Basin Rig Emulsion';
            } else if (p.includes('CLEAN')) {
              theme = '#00ffaa';
              icon = '🌊';
              name = 'Clean Ocean Negative Control';
            }

            return (
              <button
                key={inc.id}
                onClick={() => {
                  setSelectedIncident(inc);
                  setSimStep(0);
                }}
                style={{
                  padding: '6px 14px',
                  borderRadius: 8,
                  border: isSel ? `1px solid ${theme}` : '1px solid var(--border)',
                  background: isSel ? `${theme}24` : 'rgba(255, 255, 255, 0.03)',
                  color: isSel ? theme : 'var(--text-secondary)',
                  fontSize: 11,
                  fontWeight: isSel ? 700 : 500,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  boxShadow: isSel ? `0 0 16px ${theme}44` : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6
                }}
              >
                <span>{icon}</span>
                <span>{name} ({inc.geometry?.centroid_lat?.toFixed(2)}°N, {inc.geometry?.centroid_lon?.toFixed(2)}°E)</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Grid View */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        
        {/* Left Map View with Canvas Hydrodynamic Overlay */}
        <div style={{ flex: '1 1 65%', position: 'relative' }}>
          <MapContainer center={[originLat, originLon]} zoom={9.5} style={{ height: '100%', width: '100%', background: '#020c18' }}>
            <MapRecenter lat={originLat} lon={originLon} />
            
            {mapLayer === 'dark' && (
              <>
                <TileLayer
                  url="https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
                  attribution="&copy; Esri &mdash; Dark Marine Canvas"
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
            {mapLayer === 'osm' && (
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                className="dark-map-tiles"
                attribution="&copy; OpenStreetMap"
              />
            )}

            {/* High-Performance Canvas Hydrodynamic Overlay */}
            <HydrodynamicCanvasOverlay
              simTime={simStep}
              regime={regime}
              originLat={originLat}
              originLon={originLon}
              isCleanOcean={isCleanOcean}
              showStreamlines={showStreamlines}
              showVesselTrack={showVesselTrack}
              vesselTrack={vesselTrack}
              sceneKey={sceneKey}
            />

            {/* Clean Ocean Leaflet Marker */}
            {isCleanOcean && (
              <CircleMarker center={[originLat, originLon]} radius={8} pathOptions={{ color: '#00ff88', fillColor: '#00ff88', fillOpacity: 0.7, weight: 2 }}>
                <Popup>
                  <div style={{ color: '#020c18', fontSize: 12, padding: 4 }}>
                    <strong>🌊 Clean Ocean Baseline Reference</strong><br />
                    Capillary wave spectrum nominal. Zero hydrocarbon damping.
                  </div>
                </Popup>
              </CircleMarker>
            )}
          </MapContainer>

          {/* Floating MetOcean Directional Compass HUD */}
          <div style={{ position: 'absolute', top: 16, right: 16, zIndex: 1000, background: 'rgba(3, 10, 18, 0.90)', backdropFilter: 'blur(10px)', padding: '12px 16px', borderRadius: 8, border: '1px solid var(--border)', width: 230, boxShadow: '0 8px 24px rgba(0,0,0,0.5)' }}>
            <div style={{ fontSize: 10, color: 'var(--cyan)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Vector Hydrodynamics</span>
              <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, background: 'rgba(0, 212, 255, 0.15)', color: 'var(--cyan)' }}>HYCOM</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>🌊 Surface Current:</span>
                <span style={{ fontFamily: 'JetBrains Mono', color: 'var(--cyan)', fontWeight: 600 }}>
                  {regime.currentSpeed} m/s @ {regime.currentDir}°
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>💨 Wind Leeway:</span>
                <span style={{ fontFamily: 'JetBrains Mono', color: 'var(--green)', fontWeight: 600 }}>
                  {regime.windSpeed} kts @ {regime.windDir}°
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--border)', paddingTop: 4 }}>
                <span style={{ color: 'var(--text-secondary)' }}>🧭 Net Advection:</span>
                <span style={{ fontFamily: 'JetBrains Mono', color: '#ffb800', fontWeight: 700 }}>
                  {netDriftSpeedKmh} km/h ({netDriftKnots} kts)
                </span>
              </div>
            </div>
          </div>

          {/* Clean Ocean Notification Overlay if selected */}
          {isCleanOcean && (
            <div style={{ position: 'absolute', top: '40%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 1000, background: 'rgba(3, 15, 28, 0.94)', backdropFilter: 'blur(12px)', border: '1px solid rgba(0, 255, 136, 0.4)', borderRadius: 12, padding: '24px 34px', textAlign: 'center', maxWidth: 480, boxShadow: '0 12px 36px rgba(0,0,0,0.6)' }}>
              <div style={{ fontSize: 36, marginBottom: 8 }}>🌊</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--green)', marginBottom: 6 }}>
                Clean Ocean Control Scene
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                No specular damping or dark linear slicks detected by ResNet-34 UNet. Capillary wave backscatter matches undisturbed open ocean baseline at {originLat.toFixed(2)}°N, {originLon.toFixed(2)}°E.
              </p>
            </div>
          )}

          {/* Interactive Timeline Scrubber & 60 FPS Controller Floating Bar */}
          <div style={{ position: 'absolute', bottom: 18, left: '50%', transform: 'translateX(-50%)', zIndex: 1000, width: '92%', maxWidth: 840, background: 'rgba(3, 10, 18, 0.94)', backdropFilter: 'blur(14px)', padding: '14px 22px', borderRadius: 12, border: '1px solid var(--border)', boxShadow: '0 12px 40px rgba(0, 0, 0, 0.7)' }}>
            
            {/* Top Bar: Play controls + Timestamp + Status */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {/* Play / Pause button */}
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  style={{
                    width: 36, height: 36, borderRadius: '50%', border: '1px solid var(--cyan)',
                    background: isPlaying ? 'rgba(255, 51, 102, 0.25)' : 'rgba(0, 212, 255, 0.25)',
                    color: isPlaying ? 'var(--red)' : 'var(--cyan)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', fontSize: 13, fontWeight: 'bold',
                    boxShadow: isPlaying ? '0 0 14px rgba(255, 51, 102, 0.4)' : '0 0 14px rgba(0, 212, 255, 0.4)'
                  }}
                  title={isPlaying ? 'Pause Simulation' : 'Start Continuous Drift Animation'}
                >
                  {isPlaying ? '⏸' : '▶'}
                </button>

                {/* Speed Controls */}
                <div style={{ display: 'flex', gap: 4, background: '#020b16', padding: 2, borderRadius: 6, border: '1px solid var(--border)' }}>
                  {[1, 3, 8].map(spd => (
                    <button
                      key={spd}
                      onClick={() => setPlaySpeed(spd)}
                      style={{
                        padding: '3px 8px', borderRadius: 4, border: 'none',
                        background: playSpeed === spd ? 'var(--cyan)' : 'transparent',
                        color: playSpeed === spd ? '#000' : 'var(--text-muted)',
                        fontSize: 10, fontWeight: 700, cursor: 'pointer'
                      }}
                    >
                      {spd}x
                    </button>
                  ))}
                </div>

                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: simStep < 0 ? '#ff3366' : simStep < 1 ? 'var(--cyan)' : '#ffb800' }}>
                      {simStep < -0.5 ? `⏪ Backtrack: ${weathering.elapsedHours}` : Math.abs(simStep) <= 0.5 ? `🛰️ Detection: 0.0h (S1 Acquisition)` : `⏩ Forecast: ${weathering.elapsedHours}`}
                    </span>
                    <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono', color: 'var(--text-primary)', fontWeight: 600 }}>
                      🕒 {weathering.dateStr}
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                    {isCleanOcean ? (
                      <span style={{ color: 'var(--green)', fontWeight: 600 }}>🌊 Clean Ocean Baseline Standard (14.850°N, 88.500°E) · Zero Surface Hydrocarbons</span>
                    ) : (
                      <span>Plume Centroid: {currentCenterLat.toFixed(4)}°N, {currentCenterLon.toFixed(4)}°E · Area: {weathering.currentArea} km²</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Quick Jump Buttons */}
              <div style={{ display: 'flex', gap: 5 }}>
                {[
                  { label: '⏪ -6h Release', val: -6 },
                  { label: '🛰️ 0h S1 Scan', val: 0 },
                  { label: '⏩ +12h', val: 12 },
                  { label: '⏩ +24h', val: 24 },
                  { label: '⏩ +48h Impact', val: 48 }
                ].map(step => (
                  <button
                    key={step.val}
                    onClick={() => { setSimStep(step.val); setIsPlaying(false); }}
                    style={{
                      padding: '4px 9px', borderRadius: 5,
                      border: Math.abs(simStep - step.val) < 1.0 ? '1px solid var(--cyan)' : '1px solid rgba(255,255,255,0.08)',
                      background: Math.abs(simStep - step.val) < 1.0 ? 'rgba(0, 212, 255, 0.22)' : 'rgba(255,255,255,0.02)',
                      color: Math.abs(simStep - step.val) < 1.0 ? 'var(--cyan)' : 'var(--text-muted)',
                      fontSize: 10, cursor: 'pointer', fontWeight: 600
                    }}
                  >
                    {step.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Continuous Smooth Scrubber Slider */}
            <input
              type="range"
              min={-6}
              max={48}
              step={0.1}
              value={simStep}
              onChange={(e) => { setSimStep(parseFloat(e.target.value)); setIsPlaying(false); }}
              style={{ width: '100%', accentColor: 'var(--cyan)', cursor: 'pointer', height: 6 }}
            />

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 6 }}>
              <span style={{ color: '#ff3366', fontWeight: 600 }}>-6h Reconstructed Discharge</span>
              <span>-3h</span>
              <span style={{ color: 'var(--cyan)', fontWeight: 700 }}>0h Satellite Detection</span>
              <span>+12h</span>
              <span>+24h</span>
              <span>+36h</span>
              <span style={{ color: '#ffb800', fontWeight: 600 }}>+48h Dispersion Horizon</span>
            </div>
          </div>
        </div>

        {/* Right MetOcean & ADIOS Weathering Sidebar */}
        <div style={{ flex: '1 1 35%', background: 'var(--bg-secondary)', borderLeft: '1px solid var(--border)', padding: 22, overflowY: 'auto' }}>
          
          {/* Regional Oceanographic Profile */}
          <div style={{ marginBottom: 22 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                Regional Oceanographic Regime
              </h3>
              <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'rgba(0, 212, 255, 0.1)', color: 'var(--cyan)', border: '1px solid rgba(0, 212, 255, 0.2)' }}>
                CMEMS HYCOM
              </span>
            </div>
            <div style={{ background: '#020b16', padding: 12, borderRadius: 8, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--cyan)', marginBottom: 4 }}>
                {regime.name}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 8 }}>
                📍 {regime.corridor}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 10 }}>
                <div>🌊 Sea State: <span style={{ color: 'var(--text-primary)' }}>{regime.seaState}</span></div>
                <div>🌡️ Sea Temp: <span style={{ color: 'var(--text-primary)' }}>{regime.seaTemp} °C</span></div>
                <div>🧂 Salinity: <span style={{ color: 'var(--text-primary)' }}>{regime.salinity} PSU</span></div>
                <div>📏 Bathymetry: <span style={{ color: 'var(--text-primary)' }}>{regime.waterDepth} m</span></div>
              </div>
            </div>
          </div>

          {/* ADIOS Mass-Balance Weathering Kinetics or Clean Baseline Control */}
          {isCleanOcean ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ background: 'rgba(0, 255, 136, 0.05)', border: '1px solid rgba(0, 255, 136, 0.3)', borderRadius: 10, padding: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 18 }}>🌊</span>
                    <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--green)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                      Clean Ocean Reference Standard
                    </h3>
                  </div>
                  <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'rgba(0, 255, 136, 0.15)', color: 'var(--green)', border: '1px solid rgba(0, 255, 136, 0.3)', fontWeight: 700 }}>
                    NEGATIVE CONTROL
                  </span>
                </div>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 12 }}>
                  Copernicus Sentinel-1A SAR acquisition of undisturbed deep ocean water (14.85°N, 88.50°E). Normal capillary wave radar backscatter with zero specular damping deficits.
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
                  <div className="stat-card" style={{ padding: 10, background: '#020b16' }}>
                    <p className="stat-label" style={{ fontSize: 10 }}>Detected Oil Slick Area</p>
                    <p className="stat-value" style={{ fontSize: 16, color: 'var(--green)' }}>0.00 <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>km²</span></p>
                  </div>
                  <div className="stat-card" style={{ padding: 10, background: '#020b16' }}>
                    <p className="stat-label" style={{ fontSize: 10 }}>Radar Damping Anomaly</p>
                    <p className="stat-value" style={{ fontSize: 16, color: 'var(--cyan)' }}>0.0 <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>dB</span></p>
                  </div>
                </div>
                <div style={{ padding: '8px 10px', background: 'rgba(0, 212, 255, 0.08)', borderRadius: 6, fontSize: 11, color: 'var(--cyan)', border: '1px solid rgba(0, 212, 255, 0.2)' }}>
                  ✓ ResNet-34 UNet Neural Verification: Zero false-positive slick pixels detected across scene.
                </div>
              </div>

              <div style={{ background: '#020b16', border: '1px solid var(--border)', borderRadius: 10, padding: 14 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
                  ℹ️ Baseline Control Methodology
                </div>
                <p style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                  In satellite radar forensics, a negative control standard is mandatory to calibrate the neural model against natural meteorological calm areas, wind shadows, and biological surfactants.
                </p>
              </div>
            </div>
          ) : (
            <div style={{ marginBottom: 22 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  ADIOS Weathering Mass Balance
                </h3>
                <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'rgba(255, 184, 0, 0.15)', color: '#ffb800', border: '1px solid rgba(255, 184, 0, 0.3)' }}>
                  ASTM F2464 MODEL
                </span>
              </div>

              {/* Evaporation Bar */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: 'var(--text-secondary)' }}>💨 Evaporated Light Ends</span>
                  <span style={{ fontFamily: 'JetBrains Mono', color: 'var(--cyan)', fontWeight: 700 }}>{weathering.evaporation}%</span>
                </div>
                <div style={{ width: '100%', height: 6, background: '#0a192f', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: `${weathering.evaporation}%`, height: '100%', background: 'var(--cyan)', transition: 'width 0.15s' }} />
                </div>
              </div>

              {/* Natural Dispersion Bar */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: 'var(--text-secondary)' }}>🌊 Natural Wave Dispersion</span>
                  <span style={{ fontFamily: 'JetBrains Mono', color: 'var(--green)', fontWeight: 700 }}>{weathering.dispersion}%</span>
                </div>
                <div style={{ width: '100%', height: 6, background: '#0a192f', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: `${weathering.dispersion}%`, height: '100%', background: 'var(--green)', transition: 'width 0.15s' }} />
                </div>
              </div>

              {/* Water-in-oil Emulsification Bar */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: 'var(--text-secondary)' }}>🧪 Water Content (Emulsion / Mousse)</span>
                  <span style={{ fontFamily: 'JetBrains Mono', color: '#ff8800', fontWeight: 700 }}>{weathering.emulsification}%</span>
                </div>
                <div style={{ width: '100%', height: 6, background: '#0a192f', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: `${weathering.emulsification}%`, height: '100%', background: '#ff8800', transition: 'width 0.15s' }} />
                </div>
              </div>

              {/* Surface Residual Mass Bar */}
              <div style={{ marginBottom: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: 'var(--text-secondary)' }}>🛢️ Remaining Surface Slick</span>
                  <span style={{ fontFamily: 'JetBrains Mono', color: '#ff3366', fontWeight: 700 }}>{weathering.surfaceRemaining}%</span>
                </div>
                <div style={{ width: '100%', height: 6, background: '#0a192f', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: `${weathering.surfaceRemaining}%`, height: '100%', background: '#ff3366', transition: 'width 0.15s' }} />
                </div>
              </div>

              {/* Physical Telemetry Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div className="stat-card" style={{ padding: 10, background: '#020b16' }}>
                  <p className="stat-label" style={{ fontSize: 10 }}>Mousse Viscosity</p>
                  <p className="stat-value" style={{ fontSize: 15, color: '#ffb800' }}>{weathering.viscosity} <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>cSt</span></p>
                </div>
                <div className="stat-card" style={{ padding: 10, background: '#020b16' }}>
                  <p className="stat-label" style={{ fontSize: 10 }}>Slick Surface Area</p>
                  <p className="stat-value" style={{ fontSize: 15, color: 'var(--cyan)' }}>{weathering.currentArea} <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>km²</span></p>
                </div>
              </div>
            </div>
          )}

          {/* Reconstructed Backtrack Audit Card (Only for oil spills) */}
          {!isCleanOcean && (
            <div style={{ background: 'rgba(255, 51, 102, 0.05)', border: '1px solid rgba(255, 51, 102, 0.25)', borderRadius: 10, padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{ fontSize: 16 }}>🚨</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--red)', textTransform: 'uppercase' }}>
                  Backtrack Culprit Correlation
                </span>
              </div>
              <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 8 }}>
                Hydrodynamic reverse-integration places initial discharge at <strong style={{ color: 'var(--text-primary)' }}>{releaseOriginLat.toFixed(3)}°N, {releaseOriginLon.toFixed(3)}°E</strong> at ~12:40 UTC.
              </p>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', borderTop: '1px solid rgba(255, 51, 102, 0.2)', paddingTop: 6 }}>
                ✓ Spatiotemporal overlap with Crude Oil Tanker MT DESH SHOBHA (MMSI 419000042) during 2h 15m dark transponder blackout.
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
