/**
 * SpillLayer.tsx — Renders SAR footprints and predicted masks as georeferenced rasters.
 * Respects the authoritative backend GeoTransform (bbox).
 * Does NOT perform unvalidated raster-to-polygon conversion.
 */
import React, { useEffect } from 'react';
import * as maplibregl from 'maplibre-gl';
import { useMap } from '../OccurisMap';
import { bboxToImageCoordinates } from '../mapConfig';
import { CASES } from '../../data/cases';

interface Props {
  caseId: string;
  type: 'sar' | 'mask';
  opacity?: number;
  visible?: boolean;
}

export const SpillLayer: React.FC<Props> = ({ caseId, type, opacity = 1.0, visible = true }) => {
  const { map } = useMap();
  const caseConfig = CASES[caseId];

  useEffect(() => {
    if (!map || !caseConfig) return;

    const sourceId = `spill-source-${caseId}-${type}`;
    const layerId = `spill-layer-${caseId}-${type}`;

    // Get the authoritative georeferenced coordinates from config
    const coordinates = bboxToImageCoordinates(caseConfig);

    // Build the image URL based on type
    const imageUrl = type === 'sar' 
      ? `/data/images/sar_${caseId.split('_')[1]}.png`
      : `/data/images/${caseId}_pred_mask.png`;

    // Add source
    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: 'image',
        url: imageUrl,
        coordinates: coordinates,
      });
    } else {
      // Update coordinates/url if changed
      const src = map.getSource(sourceId) as maplibregl.ImageSource;
      src.updateImage({ url: imageUrl, coordinates });
    }

    // Add layer
    if (!map.getLayer(layerId)) {
      map.addLayer({
        id: layerId,
        type: 'raster',
        source: sourceId,
        paint: {
          'raster-opacity': visible ? opacity : 0,
          'raster-fade-duration': 0,
        },
      });
    } else {
      map.setPaintProperty(layerId, 'raster-opacity', visible ? opacity : 0);
    }

    return () => {
      // Cleanup happens if component unmounts entirely, but often we just hide it
      // For stability in React Strict Mode, we'll leave the source/layer
      // but ensure visibility is controlled via props.
    };
  }, [map, caseId, type, opacity, visible, caseConfig]);

  return null; // This is a logic-only component
};
