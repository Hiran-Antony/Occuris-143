/**
 * OccurisMap.tsx — MapLibre GL JS map wrapper.
 * Provides: map instance ref, style switching, base layers.
 * All child layers are passed as children using a React context pattern.
 */
import React, { useEffect, useRef, useState, createContext, useContext } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { TILE_SOURCES, ARABIAN_SEA_CENTER, ARABIAN_SEA_ZOOM, type MapStyle } from './mapConfig';

// ── Map Context ───────────────────────────────────────────────────────────────

interface MapContextValue {
  map: maplibregl.Map | null;
}
export const MapContext = createContext<MapContextValue>({ map: null });
export const useMap = () => useContext(MapContext);

// ── Props ─────────────────────────────────────────────────────────────────────

interface OccurisMapProps {
  children?: React.ReactNode;
  center?: [number, number];
  zoom?: number;
  className?: string;
}

// ── Component ─────────────────────────────────────────────────────────────────

export const OccurisMap: React.FC<OccurisMapProps> = ({
  children,
  center = ARABIAN_SEA_CENTER,
  zoom = ARABIAN_SEA_ZOOM,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [activeStyle, setActiveStyle] = useState<MapStyle>('dark');

  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          'base-tiles': {
            type: 'raster',
            tiles: [TILE_SOURCES.dark],
            tileSize: 256,
            attribution: '© CartoDB',
          },
        },
        layers: [{ id: 'base', type: 'raster', source: 'base-tiles' }],
      },
      center,
      zoom,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');

    map.on('load', () => {
      mapRef.current = map;
      setReady(true);
    });

    return () => {
      map.remove();
      mapRef.current = null;
      setReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Style switcher
  function switchStyle(style: MapStyle) {
    const map = mapRef.current;
    if (!map) return;
    setActiveStyle(style);
    const src = map.getSource('base-tiles') as maplibregl.RasterTileSource | undefined;
    if (src) {
      // Update tiles URL by re-adding source
      map.removeLayer('base');
      map.removeSource('base-tiles');
      map.addSource('base-tiles', {
        type: 'raster',
        tiles: [TILE_SOURCES[style]],
        tileSize: 256,
      });
      map.addLayer({ id: 'base', type: 'raster', source: 'base-tiles' }, map.getStyle().layers[1]?.id);
    }
  }

  return (
    <div className={`occuris-map-wrapper ${className}`}>
      {/* Map toolbar */}
      <div className="map-toolbar">
        {(['dark', 'satellite', 'street'] as MapStyle[]).map((s) => (
          <button
            key={s}
            className={`map-toolbar__btn${activeStyle === s ? ' map-toolbar__btn--active' : ''}`}
            onClick={() => switchStyle(s)}
          >
            {s === 'dark' ? '🌑 Dark Marine' : s === 'satellite' ? '⊛ Sentinel-2' : '🗺 Street'}
          </button>
        ))}
      </div>

      {/* Map container */}
      <div ref={containerRef} className="occuris-map-canvas" />

      {/* Inject children (layers) once map is ready */}
      <MapContext.Provider value={{ map: ready ? mapRef.current : null }}>
        {ready && children}
      </MapContext.Provider>
    </div>
  );
};
