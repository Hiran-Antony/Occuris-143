/**
 * GatewayLayer — renders the 4 virtual gateways as geographic polygons on the Leaflet map.
 *
 * Geometry comes exclusively from /api/cases/{caseId}/gateways (FastAPI → config/region.yaml).
 * No coordinates are hardcoded here. Gateway names are from the backend.
 *
 * Each gateway is rendered as:
 *   - A filled Polygon (transparent interior, colored boundary)
 *   - A permanent Tooltip showing the gateway ID and name
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

const GATEWAY_PALETTE: Record<string, string> = {
  GATE_A: '#00d4ff',
  GATE_B: '#ffb800',
  GATE_C: '#00ff88',
  GATE_D: '#ff6b6b',
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

  // Compute overall bounding box to render the outer "Transit Zone"
  let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
  features.forEach(gw => {
    gw.geometry.coordinates[0].forEach(([lon, lat]) => {
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lon < minLon) minLon = lon;
      if (lon > maxLon) maxLon = lon;
    });
  });

  const hasBounds = minLat !== Infinity && maxLat !== -Infinity && minLon !== Infinity && maxLon !== -Infinity;
  const outMinLat = minLat - 0.2;
  const outMaxLat = maxLat + 0.2;
  const outMinLon = minLon - 0.2;
  const outMaxLon = maxLon + 0.2;

  const outerBounds: [[number, number], [number, number]] = hasBounds
    ? [[outMinLat, outMinLon], [outMaxLat, outMaxLon]] // slight padding
    : [[0, 0], [0, 0]];

  return (
    <>
      {/* Unified Outer Maritime Transit Zone */}
      {hasBounds && (
        <Rectangle
          bounds={outerBounds}
          pathOptions={{
            color: '#00d4ff',
            weight: 2,
            opacity: 0.8,
            fillColor: '#00d4ff',
            fillOpacity: 0.03,
            dashArray: '8 8',
          }}
        />
      )}

      {/* Individual Gateways (Subtle internal rendering for labels) */}
      {features.map(gw => {
        const color = GATEWAY_PALETTE[gw.properties.gateway_id] || gw.properties.color || '#00d4ff';
        // GeoJSON coords are [lon, lat]; Leaflet wants [lat, lon]
        const positions: [number, number][] = gw.geometry.coordinates[0].map(
          ([lon, lat]) => [lat, lon]
        );

        // Pin label to the exact center of its corresponding side of the outer bounding box
        let labelLat = outMinLat + (outMaxLat - outMinLat) / 2;
        let labelLon = outMinLon + (outMaxLon - outMinLon) / 2;
        let alignClass = '';

        const gateId = gw.properties.gateway_id;
        if (gateId.includes('A')) {
          // GATE A (West) -> Left edge
          labelLon = outMinLon;
          alignClass = 'transform: translate(-110%, -50%);';
        } else if (gateId.includes('B')) {
          // GATE B (North) -> Top edge
          labelLat = outMaxLat;
          alignClass = 'transform: translate(-50%, -110%);';
        } else if (gateId.includes('C')) {
          // GATE C (South) -> Bottom edge
          labelLat = outMinLat;
          alignClass = 'transform: translate(-50%, 10%);';
        } else if (gateId.includes('D')) {
          // GATE D (East) -> Right edge
          labelLon = outMaxLon;
          alignClass = 'transform: translate(10%, -50%);';
        } else {
          // Fallback if there's a different gate
          labelLat = outMaxLat;
          alignClass = 'transform: translate(-50%, -110%);';
        }

        return (
          <div key={gw.id}>
            <Polygon
              positions={positions}
              pathOptions={{
                color: 'transparent',
                weight: 0,
                fillColor: 'transparent',
                fillOpacity: 0,
              }}
            />
            {/* Render gateway label projected to the outer boundary */}
            <Marker
              position={[labelLat, labelLon]}
              icon={L.divIcon({
                className: 'gateway-div-icon',
                html: `<div style="font-family: 'JetBrains Mono', monospace; font-size: 9px; text-align: center; color: ${color}; font-weight: 600; background: rgba(5, 15, 30, 0.85); padding: 3px 6px; border-radius: 4px; border: 1px solid ${color}60; white-space: nowrap; width: max-content; ${alignClass}">${gw.properties.gateway_id.replace('_', ' ')}</div>`,
                iconSize: [0, 0],
                iconAnchor: [0, 0]
              })}
            />
          </div>
        );
      })}
    </>
  );
}
