/**
 * GatewayLayer — Leaflet overlay for the four demo gateways.
 *
 * Usage (drop inside any <MapContainer>):
 *   import GatewayLayer from './GatewayLayer';
 *   <MapContainer ...>
 *     <GatewayLayer />
 *   </MapContainer>
 *
 * Renders each gateway as a coloured polyline with a tooltip.
 * Shows a live crossing-event badge that auto-refreshes every 15 s.
 */
import { useEffect, useState } from 'react';
import { Polyline, Tooltip } from 'react-leaflet';
import { fetchGateways, fetchCrossings } from '../api/gatewayApi';
import type { GatewayFeature, GatewayCrossing } from '../api/gatewayApi';

const REFRESH_MS = 15_000;

export default function GatewayLayer() {
  const [gateways,  setGateways]  = useState<GatewayFeature[]>([]);
  const [crossings, setCrossings] = useState<GatewayCrossing[]>([]);

  // Load gateways once
  useEffect(() => {
    fetchGateways()
      .then(fc => setGateways(fc.features))
      .catch(console.error);
  }, []);

  // Poll crossings
  useEffect(() => {
    const load = () =>
      fetchCrossings({ limit: 20 })
        .then(r => setCrossings(r.crossings))
        .catch(console.error);

    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <>
      {gateways.map(gw => {
        // GeoJSON coords are [lon, lat]; Leaflet wants [lat, lon]
        const positions = gw.geometry.coordinates.map(
          ([lon, lat]) => [lat, lon] as [number, number],
        );

        const recentCrossings = crossings.filter(
          c => c.gateway_id === gw.properties.id,
        );

        return (
          <Polyline
            key={gw.properties.id}
            positions={positions}
            pathOptions={{
              color:     gw.properties.color,
              weight:    4,
              opacity:   0.85,
              dashArray: '4 8',
              lineCap: 'round',
            }}
          >
            <Tooltip sticky>
              <div style={{ fontFamily: 'monospace', fontSize: 12 }}>
                <strong style={{ color: gw.properties.color }}>
                  {gw.properties.name}
                </strong>
                <br />
                {gw.properties.description}
                {recentCrossings.length > 0 && (
                  <>
                    <hr style={{ margin: '4px 0' }} />
                    <span style={{ color: '#aaa' }}>Recent crossings:</span>
                    {recentCrossings.slice(0, 3).map(c => (
                      <div key={c.id} style={{ marginTop: 2 }}>
                        🚢 {c.mmsi} — {c.direction} &nbsp;
                        <span style={{ color: '#888' }}>
                          {new Date(c.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                    ))}
                  </>
                )}
              </div>
            </Tooltip>
          </Polyline>
        );
      })}
    </>
  );
}
