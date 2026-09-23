/**
 * GatewayConnection — renders a dashed/dotted maritime boundary line connecting
 * the geographic centers of the 4 actual gateways.
 *
 * Gateway centers are derived from the real backend geometry — not hardcoded.
 * Connection order follows the configuration order in config/region.yaml (GATE_A → B → C → D).
 */
import { Polyline } from 'react-leaflet';

interface GatewayFeature {
  id: string;
  properties: { gateway_id: string; name: string };
  geometry: { type: string; coordinates: [number, number][][] };
}

/** Compute the geographic centroid of a polygon ring. */
function computeCenter(coords: [number, number][]): [number, number] {
  const n = coords.length;
  if (n === 0) return [0, 0];
  const sumLon = coords.reduce((s, [lon]) => s + lon, 0);
  const sumLat = coords.reduce((s, [, lat]) => s + lat, 0);
  return [sumLat / n, sumLon / n]; // returns [lat, lon] for Leaflet
}

interface Props {
  gateways: GatewayFeature[];
}

export default function GatewayConnection({ gateways }: Props) {
  if (gateways.length < 2) return null;

  // Derive centers from actual gateway geometry — never hardcoded
  const centers: [number, number][] = gateways.map(gw =>
    computeCenter(gw.geometry.coordinates[0])
  );

  return (
    <Polyline
      positions={centers}
      pathOptions={{
        color: 'rgba(0, 212, 255, 0.55)',
        weight: 1.5,
        dashArray: '6 10',
        lineCap: 'round',
        lineJoin: 'round',
      }}
    />
  );
}
