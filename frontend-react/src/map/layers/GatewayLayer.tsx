/**
 * GatewayLayer.tsx — Renders virtual gateway corridors.
 */
import React, { useEffect, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import { useMap } from '../OccurisMap';
import { fetchGateways, type GatewayFeature } from '../../services/maritimeApi';

interface Props {
  visible?: boolean;
}

export const GatewayLayer: React.FC<Props> = ({ visible = true }) => {
  const { map } = useMap();
  const [geoJsonData, setGeoJsonData] = useState<GeoJSON.FeatureCollection | null>(null);

  useEffect(() => {
    fetchGateways().then((features) => {
      setGeoJsonData({ type: 'FeatureCollection', features });
    });
  }, []);

  useEffect(() => {
    if (!map || !geoJsonData) return;
    const sourceId = 'gateways-source';

    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: 'geojson',
        data: geoJsonData,
      });

      // Layer: Gateway Corridors
      map.addLayer({
        id: 'gateways-layer',
        type: 'line',
        source: sourceId,
        paint: {
          'line-color': ['get', 'color'],
          'line-width': 4,
          'line-opacity': visible ? 0.6 : 0,
        },
      });

      // Layer: Gateway Labels
      map.addLayer({
        id: 'gateways-labels',
        type: 'symbol',
        source: sourceId,
        layout: {
          'text-field': ['get', 'name'],
          'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
          'text-size': 12,
          'symbol-placement': 'line',
          'text-offset': [0, -1],
        },
        paint: {
          'text-color': ['get', 'color'],
          'text-opacity': visible ? 0.9 : 0,
          'text-halo-color': '#000000',
          'text-halo-width': 2,
        },
      });
    } else {
      (map.getSource(sourceId) as maplibregl.GeoJSONSource).setData(geoJsonData);
    }

    if (map.getLayer('gateways-layer')) {
      map.setPaintProperty('gateways-layer', 'line-opacity', visible ? 0.6 : 0);
      map.setPaintProperty('gateways-labels', 'text-opacity', visible ? 0.9 : 0);
    }
  }, [map, geoJsonData, visible]);

  return null;
};
