/**
 * SourceZoneLayer.tsx — Renders the Module 4 source/origin zone polygon.
 */
import React, { useEffect, useMemo } from 'react';
import * as maplibregl from 'maplibre-gl';
import { useMap } from '../OccurisMap';
import type { SourceZone } from '../../types/investigation';

interface Props {
  caseId: string;
  sourceZones: SourceZone[];
  visible?: boolean;
}

export const SourceZoneLayer: React.FC<Props> = ({ caseId, sourceZones, visible = true }) => {
  const { map } = useMap();

  const geoJsonData = useMemo(() => {
    if (!sourceZones || sourceZones.length === 0) return null;

    // Usually M4 outputs a cloud of points representing the origin zone.
    // If it's just points, we render them as a scatter, or we could compute a convex hull.
    // For MVP, we render the points directly as a heatmap or circle layer to represent the zone.
    
    const features: GeoJSON.Feature[] = sourceZones.map((z) => ({
      type: 'Feature',
      properties: {},
      geometry: {
        type: 'Point',
        coordinates: [z.longitude, z.latitude],
      },
    }));

    return { type: 'FeatureCollection', features } as GeoJSON.FeatureCollection;
  }, [sourceZones]);

  useEffect(() => {
    if (!map) return;
    const sourceId = `source-zone-src-${caseId}`;
    const layerId = `source-zone-layer-${caseId}`;

    if (!map.getSource(sourceId)) {
      if (geoJsonData) {
        map.addSource(sourceId, {
          type: 'geojson',
          data: geoJsonData,
        });

        map.addLayer({
          id: layerId,
          type: 'circle',
          source: sourceId,
          paint: {
            'circle-radius': 4,
            'circle-color': '#00e5ff',
            'circle-opacity': visible ? 0.6 : 0,
            'circle-blur': 0.5, // soft edge to look like a zone
          },
        });
      }
    } else if (geoJsonData) {
      (map.getSource(sourceId) as maplibregl.GeoJSONSource).setData(geoJsonData);
    }

    if (map.getLayer(layerId)) {
      map.setPaintProperty(layerId, 'circle-opacity', visible ? 0.6 : 0);
    }
  }, [map, geoJsonData, caseId, visible]);

  return null;
};
