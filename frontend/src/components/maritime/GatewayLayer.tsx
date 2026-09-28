/**
 * GatewayLayer — renders the 4 virtual gateways as side markers on the Leaflet map.
 *
 * Geometry comes exclusively from /api/cases/{caseId}/gateways (FastAPI → config/region.yaml).
 * Labels are placed exactly on each side of the monitoring square.
 */
import { useEffect, useState } from 'react';
import { Polygon, Rectangle, Marker } from 'react-leaflet';
import L from 'leaflet';
import { caseApi } from '../../api/client';

interface GatewayFeature {
  id: string;
  properties: {
    gateway_id: string;
    name: string;
    orientation: string;
    color?: string;
  };
  geometry: {
    type: string;
    coordinates: [number, number][][];
  };
}

const GATEWAY_PALETTE: Record<string, { color: string; label: string; sublabel: string }> = {
  GATE_A: { color: '#00d4ff', label: 'Gate A', sublabel: 'Alpha · West' },
  GATE_B: { color: '#00ff88', label: 'Gate B', sublabel: 'Bravo · North' },
  GATE_C: { color: '#ffb800', label: 'Gate C', sublabel: 'Charlie · South' },
  GATE_D: { color: '#ff6b6b', label: 'Gate D', sublabel: 'Delta · East' },
};

interface Props {
  caseId: string;
  onGatewaysLoaded?: (features: GatewayFeature[]) => void;
}

export default function GatewayLayer({ caseId, onGatewaysLoaded }: Props) {
  const [features, setFeatures] = useState<GatewayFeature[]>([]);

  useEffect(() => {
    caseApi.getGateways(caseId)
      .then((fc: any) => {
        const loaded = fc.features || [];
        setFeatures(loaded);
        onGatewaysLoaded?.(loaded);
      })
      .catch(() => {});
  }, [caseId]);

  // Compute overall bounding box from all gateway polygons
  let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
  features.forEach(gw => {
    gw.geometry.coordinates[0].forEach(([lon, lat]) => {
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lon < minLon) minLon = lon;
      if (lon > maxLon) maxLon = lon;
    });
  });

  // Clamp the outer bounding box to the known oceanic monitoring area
  // lon: 59–70E, lat: 14.5–22N
  const boxMinLat = 14.5;
  const boxMaxLat = 22.0;
  const boxMinLon = 59.0;
  const boxMaxLon = 70.0;

  const outerBounds: [[number, number], [number, number]] = [
    [boxMinLat, boxMinLon],
    [boxMaxLat, boxMaxLon],
  ];

  const midLat = (boxMinLat + boxMaxLat) / 2;
  const midLon = (boxMinLon + boxMaxLon) / 2;

  // Label positions: on each side, centered
  const labelPositions: Record<string, [number, number]> = {
    GATE_A: [midLat, boxMinLon],        // West side, centered vertically
    GATE_B: [boxMaxLat, midLon],        // North side, centered horizontally
    GATE_C: [boxMinLat, midLon],        // South side, centered horizontally
    GATE_D: [midLat, boxMaxLon],        // East side, centered vertically
  };

  // Anchor offsets for each label so they sit just inside/outside the box border
  const labelAnchors: Record<string, [number, number]> = {
    GATE_A: [100, 20], // label extends to the right (inside)
    GATE_B: [50, 50],  // label above
    GATE_C: [50, -10], // label below
    GATE_D: [-10, 20], // label extends to the left (inside)
  };

  return (
    <>
      {/* ── Main oceanic monitoring square ── */}
      <Rectangle
        bounds={outerBounds}
        pathOptions={{
          color: '#00d4ff',
          weight: 2,
          opacity: 0.85,
          fillColor: '#00d4ff',
          fillOpacity: 0.03,
          dashArray: '10 6',
        }}
      />

      {/* ── Individual gateway polygons (subtle colored highlight on each side) ── */}
      {features.map(gw => {
        const info = GATEWAY_PALETTE[gw.properties.gateway_id];
        const color = info?.color || '#00d4ff';
        const positions: [number, number][] = gw.geometry.coordinates[0].map(
          ([lon, lat]) => [lat, lon]
        );
        return (
          <Polygon
            key={gw.id}
            positions={positions}
            pathOptions={{
              color: color,
              weight: 2.5,
              opacity: 0.9,
              fillColor: color,
              fillOpacity: 0.12,
            }}
          />
        );
      })}

      {/* ── Gate labels: one on each side of the box ── */}
      {Object.entries(GATEWAY_PALETTE).map(([gateId, info]) => {
        const pos = labelPositions[gateId];
        if (!pos) return null;
        const anchor = labelAnchors[gateId] || [50, 20];

        const html = `
          <div style="
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            background: rgba(3, 12, 28, 0.88);
            border: 1px solid ${info.color};
            border-radius: 4px;
            padding: 2px 6px;
            color: ${info.color};
            font-weight: 700;
            line-height: 1.3;
            white-space: nowrap;
            box-shadow: 0 0 6px ${info.color}44;
            text-align: center;
          ">
            <div style="font-size: 9px; letter-spacing: 0.8px;">${info.label}</div>
            <div style="font-size: 7px; opacity: 0.7; letter-spacing: 0.3px;">${info.sublabel}</div>
          </div>
        `;

        return (
          <Marker
            key={gateId}
            position={pos}
            icon={L.divIcon({
              className: '',
              html,
              iconSize: [80, 30],
              iconAnchor: anchor as [number, number],
            })}
          />
        );
      })}
    </>
  );
}
