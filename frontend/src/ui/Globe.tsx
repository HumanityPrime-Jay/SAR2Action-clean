import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { NISAR_FRAME_CORNERS, NISAR_IMG, NISAR_SCENE } from '../data/nisar';
import type { Lang } from '../i18n';
// Let Vite bundle MapLibre's module worker (with its shared chunk) and hand MapLibre the URL;
// its default `new URL('./maplibre-gl-worker.mjs', import.meta.url)` breaks under dependency pre-bundling.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

maplibregl.setWorkerUrl(workerUrl);

/** Taixi Township, Yunlin County — the CHAMPI case location. */
export const YUNLIN: [number, number] = [120.19, 23.72];

const GIBS = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best';

export interface GlobeHandle {
  /** Fly the camera to Yunlin; resolves when the flight ends (immediately under reduced motion). */
  flyToTaiwan(): Promise<void>;
}

const prefersReducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/** Space reserved at the bottom for the entry buttons (stacked on narrow screens). */
function bottomPad(el: HTMLElement) {
  return el.clientWidth < 700 ? 260 : 110;
}

/** Zoom at which the globe's diameter is ~78% of the free area's short side. */
function fitZoom(el: HTMLElement) {
  const side = Math.min(el.clientWidth, el.clientHeight - bottomPad(el)) || 600;
  return Math.log2((side * 0.78 * Math.PI) / 512);
}

/**
 * 3D Earth on MapLibre's globe projection with NASA GIBS Blue Marble imagery.
 * Spins slowly until the user grabs it; WebGL failures fall back to a static message.
 */
const MARKER_LABEL: Record<Lang, string> = { zh: '雲林台西 · Taiwan', en: 'Taixi, Yunlin · Taiwan' };

const Globe = forwardRef<GlobeHandle, { borders: boolean; lang: Lang }>(function Globe({ borders, lang }, ref) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const labelRef = useRef<HTMLSpanElement | null>(null);
  const spinningRef = useRef(false);
  const [failed, setFailed] = useState(false);

  useImperativeHandle(ref, () => ({
    flyToTaiwan() {
      const map = mapRef.current;
      if (!map || prefersReducedMotion()) return Promise.resolve();
      return new Promise<void>((resolve) => {
        // Stop the idle spin first, so its `moveend` cannot resolve this flight early.
        spinningRef.current = false;
        map.stop();
        map.once('moveend', () => resolve());
        // Blue Marble tops out at z8 (~500 m); stopping at 5.5 keeps Taiwan sharp.
        map.flyTo({ center: YUNLIN, zoom: 5.5, duration: 1800, essential: true });
      });
    },
  }));

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: el,
        center: [112, 18],
        zoom: fitZoom(el),
        minZoom: 0.5,
        maxZoom: 8,
        attributionControl: { compact: true, customAttribution: `Imagery: NASA GIBS · Blue Marble · ${NISAR_SCENE.mission} ${NISAR_SCENE.postDate}` },
        style: {
          version: 8,
          projection: { type: 'globe' },
          sky: { 'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 5, 1, 7, 0] },
          sources: {
            bluemarble: {
              type: 'raster',
              tiles: [`${GIBS}/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg`],
              tileSize: 256,
              maxzoom: 8,
            },
            // Real NISAR swath (track 61 / frame 76) over western Taiwan.
            nisar: { type: 'image', url: NISAR_IMG.frame, coordinates: NISAR_FRAME_CORNERS },
            // Coastlines: transparent RGBA. (Reference_Features is an opaque palette PNG that blacks out the globe.)
            borders: {
              type: 'raster',
              tiles: [`${GIBS}/Coastlines_15m/default/GoogleMapsCompatible_Level13/{z}/{y}/{x}.png`],
              tileSize: 256,
              maxzoom: 13,
            },
          },
          layers: [
            { id: 'space', type: 'background', paint: { 'background-color': '#000' } },
            { id: 'bluemarble', type: 'raster', source: 'bluemarble' },
            // Fades in as the camera nears Taiwan.
            { id: 'nisar', type: 'raster', source: 'nisar', paint: { 'raster-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0, 5, 0.9], 'raster-fade-duration': 0 } },
            // brightness-min 1 turns the dark coastline strokes white; alpha keeps the rest clear.
            { id: 'borders', type: 'raster', source: 'borders', paint: { 'raster-opacity': 0.55, 'raster-brightness-min': 1 } },
          ],
        },
      });
    } catch {
      setFailed(true);
      return;
    }
    mapRef.current = map;
    map.setPadding({ top: 0, left: 0, right: 0, bottom: bottomPad(el) });
    map.on('error', (e: maplibregl.ErrorEvent) => {
      // A missing tile is harmless; only a broken WebGL context means no globe.
      if (String(e.error?.message ?? '').toLowerCase().includes('webgl')) setFailed(true);
    });

    // Taiwan marker with label.
    const markerEl = document.createElement('div');
    markerEl.className = 'globe-marker';
    markerEl.innerHTML = '<span class="globe-pulse"></span><span class="globe-dot"></span><span class="globe-label"></span>';
    labelRef.current = markerEl.querySelector('.globe-label');
    new maplibregl.Marker({ element: markerEl, anchor: 'left', offset: [-8, 0] }).setLngLat(YUNLIN).addTo(map);

    // Slow idle spin; any user interaction stops it for good.
    spinningRef.current = !prefersReducedMotion();
    const spin = () => {
      if (!spinningRef.current || map.getZoom() > 3) return;
      const c = map.getCenter();
      c.lng -= 4;
      map.easeTo({ center: c, duration: 1000, easing: (n: number) => n });
    };
    const stopSpin = () => {
      spinningRef.current = false;
    };
    map.on('mousedown', stopSpin);
    map.on('touchstart', stopSpin);
    map.on('wheel', stopSpin);
    map.on('moveend', spin);
    map.on('load', spin);

    const ro = new ResizeObserver(() => map.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (labelRef.current) labelRef.current.textContent = MARKER_LABEL[lang];
  }, [lang]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => map.setLayoutProperty('borders', 'visibility', borders ? 'visible' : 'none');
    if (map.isStyleLoaded()) apply();
    else map.once('load', apply);
  }, [borders]);

  if (failed) {
    return (
      <div className="globe globe-fallback" role="img" aria-label={lang === 'zh' ? '3D 地球無法載入' : '3D globe unavailable'}>
        <p className="cap">
          {lang === 'zh' ? '這個瀏覽器無法顯示 3D 地球（需要 WebGL）。下方按鈕仍可使用。' : 'This browser cannot show the 3D globe (WebGL needed). The buttons below still work.'}
        </p>
      </div>
    );
  }
  return <div ref={containerRef} className="globe" role="application" aria-label={lang === 'zh' ? '3D 地球：拖曳旋轉、滾輪縮放，標記為台灣雲林台西' : '3D globe: drag to rotate, scroll to zoom; marker at Taixi, Yunlin, Taiwan'} />;
});

export default Globe;
