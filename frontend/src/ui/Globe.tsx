import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { TYPHOON_DAY } from '../data/champi';
import { NISAR_FRAME_CORNERS, NISAR_IMG, NISAR_SCENE } from '../data/nisar';
import type { Lang } from '../i18n';
// Let Vite bundle MapLibre's module worker (with its shared chunk) and hand MapLibre the URL;
// its default `new URL('./maplibre-gl-worker.mjs', import.meta.url)` breaks under dependency pre-bundling.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

maplibregl.setWorkerUrl(workerUrl);

/** Taixi Township, Yunlin County — the CHAMPI case location. */
export const YUNLIN: [number, number] = [120.19, 23.72];

/** Clicks inside this box count as clicking Taiwan. */
const TAIWAN_BOX = { west: 119.2, east: 122.2, south: 21.8, north: 25.4 };
const TAIWAN_VIEW = { center: [120.85, 23.65] as [number, number], zoom: 7, pitch: 40, bearing: -12 };
const START_CENTER: [number, number] = [112, 18];
/** Length of the dive; the cloud veil animation in styles.css runs for the same time. */
const DIVE_MS = 3200;

const GIBS = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best';

/** Optional home layers; `shield` is a decorative ring, not data. */
export interface GlobeLayers {
  borders: boolean;
  clouds: boolean;
  rain: boolean;
  shield: boolean;
}

const DATA_LAYERS = { borders: 'borders', clouds: 'viirs', rain: 'imerg' } as const;

export interface GlobeHandle {
  /** Fly the camera to Yunlin; resolves when the flight ends (immediately under reduced motion). */
  flyToTaiwan(): Promise<void>;
}

const prefersReducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/** The point 89.5° due east of [lng, lat] along a great circle. */
function limbPoint(lng: number, lat: number): [number, number] {
  const r = Math.PI / 180;
  const d = 89.5 * r;
  const p = lat * r;
  const lat2 = Math.asin(Math.sin(p) * Math.cos(d));
  const lng2 = lng * r + Math.atan2(Math.sin(d) * Math.cos(p), Math.cos(d) - Math.sin(p) * Math.sin(lat2));
  return [lng2 / r, lat2 / r];
}

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
const DIVE_LABEL: Record<Lang, string> = { zh: '飛進台灣', en: 'Fly into Taiwan' };

const Globe = forwardRef<GlobeHandle, { layers: GlobeLayers; lang: Lang }>(function Globe({ layers, lang }, ref) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const labelRef = useRef<HTMLSpanElement | null>(null);
  const shieldRef = useRef<HTMLDivElement>(null);
  const veilRef = useRef<HTMLDivElement>(null);
  const spinningRef = useRef(false);
  const diveRef = useRef<() => void>(() => {});
  const [failed, setFailed] = useState(false);
  const [dived, setDived] = useState(false);

  // Click on Taiwan: dive through the typhoon-day clouds (they fade out with zoom) down to the island.
  diveRef.current = () => {
    const map = mapRef.current;
    if (!map || dived) return;
    spinningRef.current = false;
    map.stop();
    if (prefersReducedMotion()) {
      map.jumpTo(TAIWAN_VIEW);
      setDived(true);
      return;
    }
    const veil = veilRef.current;
    if (veil) {
      veil.classList.remove('pass');
      void veil.offsetWidth; // restart the CSS animation
      veil.classList.add('pass');
    }
    map.once('moveend', () => setDived(true));
    map.flyTo({ ...TAIWAN_VIEW, duration: DIVE_MS, curve: 1.6, essential: true });
  };

  const backToGlobe = () => {
    const map = mapRef.current;
    const el = containerRef.current;
    if (!map || !el) return;
    setDived(false);
    const view = { center: START_CENTER, zoom: fitZoom(el), pitch: 0, bearing: 0 };
    if (prefersReducedMotion()) map.jumpTo(view);
    else map.flyTo({ ...view, duration: 2200, essential: true });
  };

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
        center: START_CENTER,
        zoom: fitZoom(el),
        minZoom: 0.5,
        maxZoom: 8,
        attributionControl: { compact: true, customAttribution: `Imagery: NASA GIBS · Blue Marble · VIIRS & IMERG ${TYPHOON_DAY} · ${NISAR_SCENE.mission} ${NISAR_SCENE.postDate}` },
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
            // Daily true colour and rain rate on a warning-window day.
            viirs: {
              type: 'raster',
              tiles: [`${GIBS}/VIIRS_SNPP_CorrectedReflectance_TrueColor/default/${TYPHOON_DAY}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`],
              tileSize: 256,
              maxzoom: 9,
            },
            imerg: {
              type: 'raster',
              tiles: [`${GIBS}/IMERG_Precipitation_Rate/default/${TYPHOON_DAY}/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png`],
              tileSize: 256,
              maxzoom: 6,
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
            // The clouds thin out as the camera dives, so the island shows through.
            { id: 'viirs', type: 'raster', source: 'viirs', layout: { visibility: 'none' }, paint: { 'raster-opacity': ['interpolate', ['linear'], ['zoom'], 3.5, 1, 5, 0] } },
            { id: 'imerg', type: 'raster', source: 'imerg', layout: { visibility: 'none' }, paint: { 'raster-opacity': 0.7 } },
            // Fades in as the camera nears Taiwan, then eases off so the island shows under it.
            { id: 'nisar', type: 'raster', source: 'nisar', paint: { 'raster-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0, 5, 0.9, 6.5, 0.45], 'raster-fade-duration': 0 } },
            // brightness-min 1 turns the dark coastline strokes white; alpha keeps the rest clear.
            // Faded out close in: a few GIBS tiles there are opaque and would turn into grey blocks.
            { id: 'borders', type: 'raster', source: 'borders', paint: { 'raster-opacity': ['interpolate', ['linear'], ['zoom'], 4.5, 0.55, 5.5, 0], 'raster-brightness-min': 1 } },
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
    markerEl.innerHTML = '<span class="globe-pulse"></span><span class="globe-dot"></span><button type="button" class="globe-label"></button>';
    labelRef.current = markerEl.querySelector('.globe-label');
    labelRef.current?.addEventListener('click', () => diveRef.current());

    // Clicking anywhere on Taiwan also dives.
    const onTaiwan = (p: maplibregl.LngLat) => p.lng >= TAIWAN_BOX.west && p.lng <= TAIWAN_BOX.east && p.lat >= TAIWAN_BOX.south && p.lat <= TAIWAN_BOX.north;
    map.on('click', (e: maplibregl.MapMouseEvent) => {
      if (onTaiwan(e.lngLat)) diveRef.current();
    });
    map.on('mousemove', (e: maplibregl.MapMouseEvent) => {
      map.getCanvas().style.cursor = map.getZoom() < 6 && onTaiwan(e.lngLat) ? 'pointer' : '';
    });
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

    // Keep the ring on the globe's silhouette; it fades out as the camera closes in.
    const placeShield = () => {
      const ring = shieldRef.current;
      if (!ring) return;
      const z = map.getZoom();
      const c = map.getCenter();
      // With no pitch the view axis runs through the earth's centre, so the map centre marks it on screen;
      // a point just short of 90° away marks the visible edge (perspective makes it smaller than worldSize / 2π).
      const mid = map.project(c);
      const edge = map.project(limbPoint(c.lng, c.lat));
      ring.style.setProperty('--gx', `${mid.x}px`);
      ring.style.setProperty('--gy', `${mid.y}px`);
      ring.style.setProperty('--gr', `${Math.hypot(edge.x - mid.x, edge.y - mid.y)}px`);
      ring.style.opacity = String(Math.max(0, Math.min(1, 3 - z)));
    };
    map.on('move', placeShield);
    map.on('resize', placeShield);
    placeShield();

    const ro = new ResizeObserver(() => map.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const label = labelRef.current;
    if (!label) return;
    label.textContent = MARKER_LABEL[lang];
    label.setAttribute('aria-label', `${MARKER_LABEL[lang]}：${DIVE_LABEL[lang]}`);
  }, [lang]);

  const { borders, clouds, rain } = layers;
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const on = { borders, clouds, rain };
    const apply = () => {
      for (const [key, id] of Object.entries(DATA_LAYERS)) map.setLayoutProperty(id, 'visibility', on[key as keyof typeof on] ? 'visible' : 'none');
    };
    if (map.isStyleLoaded()) apply();
    else map.once('load', apply);
  }, [borders, clouds, rain]);

  if (failed) {
    return (
      <div className="globe globe-fallback" role="img" aria-label={lang === 'zh' ? '3D 地球無法載入' : '3D globe unavailable'}>
        <p className="cap">
          {lang === 'zh' ? '這個瀏覽器無法顯示 3D 地球（需要 WebGL）。下方按鈕仍可使用。' : 'This browser cannot show the 3D globe (WebGL needed). The buttons below still work.'}
        </p>
      </div>
    );
  }
  return (
    <>
      <div ref={containerRef} className="globe" role="application" aria-label={lang === 'zh' ? '3D 地球：拖曳旋轉、滾輪縮放，標記為台灣雲林台西' : '3D globe: drag to rotate, scroll to zoom; marker at Taixi, Yunlin, Taiwan'} />
      <div ref={shieldRef} className="globe-shield" hidden={!layers.shield} aria-hidden="true">
        <span className="sweep" />
      </div>
      <div ref={veilRef} className="cloud-veil" aria-hidden="true" onAnimationEnd={(e) => e.currentTarget.classList.remove('pass')} />
      {dived && (
        <button type="button" className="globe-back" onClick={backToGlobe}>
          ← {lang === 'zh' ? '返回地球' : 'Back to globe'}
        </button>
      )}
    </>
  );
});

export default Globe;
