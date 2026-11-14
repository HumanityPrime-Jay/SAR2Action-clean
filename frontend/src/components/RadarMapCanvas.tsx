import React, { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import {
  CaseSummary,
  LayerMetadataResponse,
  RevealMode,
} from '../types/api';

interface RadarMapCanvasProps {
  activeCase: CaseSummary | null;
  revealMode: RevealMode;
  layers: Record<string, LayerMetadataResponse>;
  selectedBbox: [number, number, number, number];
  agentFocusBbox?: [number, number, number, number] | null;
  rankedRegions?: { bbox_wgs84: [number, number, number, number]; rank: number }[];
  onSelectBbox: (bbox: [number, number, number, number], label?: string) => void;
}

export const RadarMapCanvas: React.FC<RadarMapCanvasProps> = ({
  activeCase,
  revealMode,
  layers,
  selectedBbox,
  agentFocusBbox,
  rankedRegions = [],
  onSelectBbox,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [swipePercent, setSwipePercent] = useState<number>(50);
  const [drawMode, setDrawMode] = useState<boolean>(false);
  const [dragStartLonLat, setDragStartLonLat] = useState<[number, number] | null>(null);
  const [mapAppliedFocus, setMapAppliedFocus] = useState('');
  const [agentOverlay, setAgentOverlay] = useState<{ width: number; height: number;
    regions: { rank: number; x: number; y: number; width: number; height: number }[];
    focus: { x: number; y: number; width: number; height: number } | null }>({ width: 1, height: 1, regions: [], focus: null });

  const isSwipeMode = revealMode === 'swipe_hh' || revealMode === 'swipe_hv';
  const primaryLayerKey =
    revealMode === 'swipe_hh'
      ? 't0_hh'
      : revealMode === 'swipe_hv'
      ? 't0_hv'
      : revealMode;
  const compareLayerKey =
    revealMode === 'swipe_hh'
      ? 't1_hh'
      : revealMode === 'swipe_hv'
      ? 't1_hv'
      : null;

  const activeLayerMeta = layers[primaryLayerKey] || null;
  const compareLayerMeta = compareLayerKey ? layers[compareLayerKey] || null : null;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || typeof map.project !== 'function' || typeof map.off !== 'function') return;
    const update = () => {
      const rect = (bbox: [number, number, number, number]) => {
        const topLeft = map.project([bbox[0], bbox[3]]);
        const bottomRight = map.project([bbox[2], bbox[1]]);
        return { x: topLeft.x, y: topLeft.y, width: bottomRight.x - topLeft.x,
          height: bottomRight.y - topLeft.y };
      };
      const container = mapContainerRef.current;
      setAgentOverlay({ width: container?.clientWidth || 1, height: container?.clientHeight || 1,
        regions: rankedRegions.map((region) => ({ rank: region.rank, ...rect(region.bbox_wgs84) })),
        focus: agentFocusBbox ? rect(agentFocusBbox) : null });
    };
    map.on('move', update);
    map.on('resize', update);
    update();
    return () => { map.off('move', update); map.off('resize', update); };
  }, [agentFocusBbox, rankedRegions]);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    try {
      const centerLon = (selectedBbox[0] + selectedBbox[2]) / 2;
      const centerLat = (selectedBbox[1] + selectedBbox[3]) / 2;

      const map = new maplibregl.Map({
        container: mapContainerRef.current,
        style: {
          version: 8,
          sources: {
            // NOTE (Phase 3C): the keyless CARTO URL now returns "API KEY REQUIRED" placeholder
            // tiles. R&D demo uses the OSM standard tile server (low-volume use per OSMF tile
            // policy). A production / competition deployment must use a keyed or self-hosted provider.
            osmBase: {
              type: 'raster',
              tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
              tileSize: 256,
              maxzoom: 19,
              attribution: '© OpenStreetMap contributors | NISAR L2 GCOV (NASA/JPL)',
            },
          },
          layers: [
            {
              id: 'basemap-osm-dimmed',
              type: 'raster',
              source: 'osmBase',
              paint: {
                'raster-saturation': -0.7,
                'raster-brightness-max': 0.45,
              },
            },
          ],
        },
        center: [centerLon, centerLat],
        zoom: 10.2,
        pitch: 0,
        maxPitch: 0, // Strictly 2D WebGIS (no 3D globe/tilt)
      });

      mapRef.current = map;
    } catch {
      // Headless / jsdom fallback when WebGL context is unavailable in unit tests
    }

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  // Sync MapLibre camera and image overlay when activeLayerMeta or selectedBbox changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || typeof map.getStyle !== 'function') return;

    const applyOverlay = () => {
      try {
        if (map.getLayer('sar-overlay-layer')) {
          map.removeLayer('sar-overlay-layer');
        }
        if (map.getSource('sar-overlay-source')) {
          map.removeSource('sar-overlay-source');
        }

        if (activeLayerMeta && !isSwipeMode) {
          const [west, south, east, north] = activeLayerMeta.bbox_wgs84;
          map.addSource('sar-overlay-source', {
            type: 'image',
            url: activeLayerMeta.image_url,
            coordinates: [
              [west, north],
              [east, north],
              [east, south],
              [west, south],
            ],
          });
          map.addLayer({
            id: 'sar-overlay-layer',
            type: 'raster',
            source: 'sar-overlay-source',
            paint: { 'raster-opacity': 0.88, 'raster-resampling': 'nearest' },
          });
        }

        map.fitBounds(
          [
            [selectedBbox[0] - 0.02, selectedBbox[1] - 0.02],
            [selectedBbox[2] + 0.02, selectedBbox[3] + 0.02],
          ],
          { duration: 400 }
        );
      } catch {
        // Ignore if style is still loading
      }
    };

    if (map.isStyleLoaded()) {
      applyOverlay();
    } else {
      map.once('load', applyOverlay);
    }
  }, [activeLayerMeta, isSwipeMode, selectedBbox]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const update = () => {
      try {
        if (map.getLayer('agent-region-outline')) map.removeLayer('agent-region-outline');
        if (map.getSource('agent-region-source')) map.removeSource('agent-region-source');
        if (!agentFocusBbox) { setMapAppliedFocus(''); return; }
        const [w, s, e, n] = agentFocusBbox;
        map.addSource('agent-region-source', { type: 'geojson', data: {
          type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [[[w,s],[e,s],[e,n],[w,n],[w,s]]] },
        }});
        map.addLayer({ id: 'agent-region-outline', type: 'line', source: 'agent-region-source',
          paint: { 'line-color': '#22d3ee', 'line-width': 4 } });
        map.fitBounds([[w, s], [e, n]], { padding: 75, maxZoom: 13, duration: 450 });
        setMapAppliedFocus(agentFocusBbox.join(','));
      } catch { /* Map style may still be loading. */ }
    };
    if (map.isStyleLoaded()) update(); else map.once('load', update);
  }, [agentFocusBbox]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const update = () => {
      try {
        if (map.getLayer('agent-ranked-line')) map.removeLayer('agent-ranked-line');
        if (map.getLayer('agent-ranked-fill')) map.removeLayer('agent-ranked-fill');
        if (map.getSource('agent-ranked-source')) map.removeSource('agent-ranked-source');
        if (!rankedRegions.length) return;
        map.addSource('agent-ranked-source', { type: 'geojson', data: {
          type: 'FeatureCollection', features: rankedRegions.map((region) => {
            const [w, s, e, n] = region.bbox_wgs84;
            return { type: 'Feature' as const, properties: { rank: region.rank },
              geometry: { type: 'Polygon' as const, coordinates: [[[w,s],[e,s],[e,n],[w,n],[w,s]]] } };
          }),
        }});
        map.addLayer({ id: 'agent-ranked-fill', type: 'fill', source: 'agent-ranked-source', paint: { 'fill-color': '#fbbf24', 'fill-opacity': 0.13 } });
        map.addLayer({ id: 'agent-ranked-line', type: 'line', source: 'agent-ranked-source', paint: { 'line-color': '#fbbf24', 'line-width': 2 } });
      } catch { /* Map style may still be loading. */ }
    };
    if (map.isStyleLoaded()) update(); else map.once('load', update);
  }, [rankedRegions]);

  // Interactive 2-click AOI box drawing on the map
  const handleOverlayClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!drawMode) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const relX = (e.clientX - rect.left) / Math.max(rect.width, 1);
    const relY = (e.clientY - rect.top) / Math.max(rect.height, 1);

    const viewBbox = activeLayerMeta?.bbox_wgs84 || selectedBbox;
    const lon = Number((viewBbox[0] + relX * (viewBbox[2] - viewBbox[0])).toFixed(4));
    const lat = Number((viewBbox[3] - relY * (viewBbox[3] - viewBbox[1])).toFixed(4));

    if (!dragStartLonLat) {
      setDragStartLonLat([lon, lat]);
    } else {
      const [lon0, lat0] = dragStartLonLat;
      const minLon = Number(Math.min(lon0, lon).toFixed(4));
      const maxLon = Number(Math.max(lon0, lon, minLon + 0.02).toFixed(4));
      const minLat = Number(Math.min(lat0, lat).toFixed(4));
      const maxLat = Number(Math.max(lat0, lat, minLat + 0.02).toFixed(4));
      setDragStartLonLat(null);
      setDrawMode(false);
      onSelectBbox([minLon, minLat, maxLon, maxLat], 'Custom Drawn AOI');
    }
  };

  return (
    <div className="map-section" data-testid="radar-map-section">
      <div className="map-toolbar">
        <div className="map-toolbar-left">
          <span className="badge badge-crs">2D WebGIS • EPSG:{activeCase?.crs_epsg || 32748} (10 m GCOV)</span>
          <span className="badge badge-bbox" data-testid="active-aoi-bbox-display">
            AOI WGS84: [{selectedBbox.map((v) => v.toFixed(3)).join(', ')}]
          </span>
        </div>
        <div className="map-toolbar-right">
          <button
            type="button"
            className={`btn-draw-aoi ${drawMode ? 'active' : ''}`}
            data-testid="btn-draw-aoi"
            onClick={() => {
              setDrawMode(!drawMode);
              setDragStartLonLat(null);
            }}
          >
            {drawMode
              ? dragStartLonLat
                ? 'Click 2nd Corner to Finish AOI'
                : 'Click 1st Corner on Map...'
              : 'Draw Custom AOI on Map'}
          </button>
        </div>
      </div>

      <div
        className={`map-viewport ${drawMode ? 'cursor-crosshair' : ''}`}
        onClick={handleOverlayClick}
        data-testid="map-viewport"
        data-agent-focus-bbox={agentFocusBbox?.join(',') || ''}
        data-maplibre-focus-applied={mapAppliedFocus}
        data-ranked-region-count={rankedRegions.length}
      >
        <div ref={mapContainerRef} className="maplibre-container" />
        {rankedRegions.length > 0 && <svg className="agent-region-overlay" viewBox={`0 0 ${agentOverlay.width} ${agentOverlay.height}`} preserveAspectRatio="none" aria-label="Georeferenced ranked radar change regions">
          {agentOverlay.regions.map((region) => <rect key={region.rank} {...region} className="agent-region-rect" />)}
          {agentOverlay.focus && <rect {...agentOverlay.focus} className="agent-focus-rect" />}
        </svg>}

        {/* Direct High-Resolution Georeferenced Raster Overlay & T0/T1 Swipe Curtain */}
        {activeLayerMeta && (
          <div className="raster-stage" data-testid="raster-stage">
            {!isSwipeMode ? (
              <img
                src={activeLayerMeta.image_url}
                alt={activeLayerMeta.title}
                className="raster-overlay-img"
                data-testid="active-layer-img"
              />
            ) : (
              <div className="swipe-stage" data-testid="swipe-stage">
                {compareLayerMeta && (
                  <img
                    src={compareLayerMeta.image_url}
                    alt={compareLayerMeta.title}
                    className="raster-overlay-img swipe-img-right"
                    data-testid="swipe-t1-img"
                  />
                )}
                <div
                  className="swipe-left-clip"
                  style={{ width: `${swipePercent}%` }}
                  data-testid="swipe-left-clip"
                >
                  <img
                    src={activeLayerMeta.image_url}
                    alt={activeLayerMeta.title}
                    className="raster-overlay-img swipe-img-left"
                    data-testid="swipe-t0-img"
                  />
                </div>
                <div
                  className="swipe-divider-line"
                  style={{ left: `${swipePercent}%` }}
                >
                  <span className="swipe-tag-left">T0 ({activeLayerMeta.t0_acquisition_utc.slice(0, 10)})</span>
                  <span className="swipe-tag-right">T1 ({compareLayerMeta?.t1_acquisition_utc?.slice(0, 10) || 'T1'})</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Interactive T0 / T1 Swipe Slider Control */}
        {isSwipeMode && (
          <div className="swipe-slider-bar" data-testid="swipe-slider-bar">
            <label htmlFor="swipe-range-input">
              T0 / T1 Split-Screen Swipe ({swipePercent}% T0 / {100 - swipePercent}% T1):
            </label>
            <input
              id="swipe-range-input"
              data-testid="swipe-range-input"
              type="range"
              min={0}
              max={100}
              value={swipePercent}
              onChange={(e) => setSwipePercent(Number(e.target.value))}
            />
          </div>
        )}

        {/* Scientific Legend Overlay (Section 3.2) */}
        {activeLayerMeta && (
          <div className="scientific-legend-card" data-testid="scientific-legend-card">
            <div className="legend-header">
              <strong>{activeLayerMeta.legend.title}</strong>
              <span className="legend-units">[{activeLayerMeta.legend.units}]</span>
            </div>
            <div className="legend-stops">
              {activeLayerMeta.legend.stops.map((stop, idx) => (
                <div key={idx} className="legend-stop-row">
                  <span
                    className="legend-color-swatch"
                    style={{ backgroundColor: stop.color }}
                  />
                  <span className="legend-stop-label">{stop.label}</span>
                </div>
              ))}
              <div className="legend-stop-row">
                <span className="legend-color-swatch swatch-invalid" />
                <span className="legend-stop-label">
                  Invalid / unavailable observation (mask == 0, mask == 255, or P ≤ 0 → NaN)
                </span>
              </div>
            </div>

            {activeLayerMeta.legend.positive_change_meaning && (
              <div className="legend-directional-note">
                <div>• {activeLayerMeta.legend.positive_change_meaning}</div>
                <div>• {activeLayerMeta.legend.negative_change_meaning}</div>
              </div>
            )}

            {activeLayerMeta.disclaimer && (
              <div className="legend-disclaimer" data-testid="combined-metric-disclaimer">
                ⚠️ {activeLayerMeta.disclaimer}
              </div>
            )}

            <div className="legend-guardrail-note">
              {activeLayerMeta.legend.prohibited_labels_notice}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

