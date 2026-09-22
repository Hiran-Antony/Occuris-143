/**
 * VesselTrackLayer.tsx — Renders vessel tracks and AIS gaps.
 * Uses dashed lines for AIS gaps, labeled as "AIS REPORTING GAP".
 * "DARK VESSEL SUSPICION" is strictly avoided.
 */
import React, { useEffect, useMemo } from 'react';
import * as maplibregl from 'maplibre-gl';
import { useMap } from '../OccurisMap';
import type { VesselTrack } from '../../types/investigation';
import { VESSEL_COLORS } from '../mapConfig';

interface Props {
  tracks: VesselTrack[];
  visible?: boolean;
}

export const VesselTrackLayer: React.FC<Props> = ({ tracks, visible = true }) => {
  const { map } = useMap();

  // Convert tracks to GeoJSON
  const geoJsonData = useMemo(() => {
    const features: GeoJSON.Feature[] = [];

    tracks.forEach((track) => {
      const color = VESSEL_COLORS[track.vessel_id] || '#ffffff';

      // Observed pings (solid line)
      if (track.pings.length > 1) {
        features.push({
          type: 'Feature',
          properties: {
            vessel_id: track.vessel_id,
            vessel_name: track.vessel_name,
            color,
            type: 'observed',
          },
          geometry: {
            type: 'LineString',
            coordinates: track.pings.map((p) => [p.lon, p.lat]),
          },
        });
      }

      // Scatter points for pings (to show actual observations)
      track.pings.forEach((p) => {
        features.push({
          type: 'Feature',
          properties: {
            vessel_id: track.vessel_id,
            color,
            type: 'ping',
            timestamp: p.timestamp,
            sog: p.sog,
          },
          geometry: {
            type: 'Point',
            coordinates: [p.lon, p.lat],
          },
        });
      });

      // AIS Gaps (dashed line)
      track.gaps.forEach((gap) => {
        features.push({
          type: 'Feature',
          properties: {
            vessel_id: track.vessel_id,
            vessel_name: track.vessel_name,
            color: '#ff5252', // Gaps highlighted in red
            type: 'gap',
            duration: gap.duration_minutes,
            label: 'AIS REPORTING GAP', // Strictly enforced terminology
          },
          geometry: {
            type: 'LineString',
            coordinates: [
              [gap.start_lon, gap.start_lat],
              [gap.end_lon, gap.end_lat],
            ],
          },
        });
      });
    });

    return { type: 'FeatureCollection', features } as GeoJSON.FeatureCollection;
  }, [tracks]);

  useEffect(() => {
    if (!map) return;
    const sourceId = 'vessel-tracks-source';

    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: 'geojson',
        data: geoJsonData,
      });

      // Layer: Observed paths
      map.addLayer({
        id: 'vessel-tracks-observed',
        type: 'line',
        source: sourceId,
        filter: ['==', 'type', 'observed'],
        paint: {
          'line-color': ['get', 'color'],
          'line-width': 2,
          'line-opacity': 0.8,
        },
      });

      // Layer: AIS Gaps (Dashed)
      map.addLayer({
        id: 'vessel-tracks-gaps',
        type: 'line',
        source: sourceId,
        filter: ['==', 'type', 'gap'],
        paint: {
          'line-color': ['get', 'color'],
          'line-width': 2,
          'line-dasharray': [3, 3],
          'line-opacity': 0.9,
        },
      });

      // Layer: Ping points
      map.addLayer({
        id: 'vessel-tracks-pings',
        type: 'circle',
        source: sourceId,
        filter: ['==', 'type', 'ping'],
        paint: {
          'circle-radius': 3,
          'circle-color': ['get', 'color'],
          'circle-stroke-width': 1,
          'circle-stroke-color': '#000',
        },
      });
    } else {
      (map.getSource(sourceId) as maplibregl.GeoJSONSource).setData(geoJsonData);
    }

    // Toggle visibility
    const opacity = visible ? 1 : 0;
    ['vessel-tracks-observed', 'vessel-tracks-gaps'].forEach((l) => {
      if (map.getLayer(l)) map.setPaintProperty(l, 'line-opacity', visible ? 0.8 : 0);
    });
    if (map.getLayer('vessel-tracks-pings')) {
      map.setPaintProperty('vessel-tracks-pings', 'circle-opacity', visible ? 1 : 0);
      map.setPaintProperty('vessel-tracks-pings', 'circle-stroke-opacity', visible ? 1 : 0);
    }
  }, [map, geoJsonData, visible]);

  return null;
};
