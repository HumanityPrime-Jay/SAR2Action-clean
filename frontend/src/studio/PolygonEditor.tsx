import { useEffect, useRef, useState } from 'react';
import { LngLatBounds, Marker, type GeoJSONSource, type Map as MapLibreMap } from 'maplibre-gl';
import { polygonRings, type FieldGeometry, type LngLat } from '../data/champi';

const SOURCE = 'user-drawn-geometry';
const CASE_ID = 'CHAMPI-YUNLIN-TAIXI';
type Measurement = {
  area_m2: number;
  area_ha: number;
  perimeter_m: number;
  area_crs: string;
  geometry_source: 'USER_DRAWN';
  measurement_status: 'MEASURED_NOT_OFFICIAL';
};
type EditState = { draft: LngLat[]; geometry: FieldGeometry | null };
const EMPTY: EditState = { draft: [], geometry: null };

async function post<T>(path: string, body: object, signal: AbortSignal): Promise<T> {
  const response = await fetch(`/api/gis/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === 'string' ? error.detail : `HTTP ${response.status}`);
  }
  return response.json();
}

const measure = (geometry: unknown, signal: AbortSignal) =>
  post<Measurement>(
    'measure',
    {
      case_id: CASE_ID,
      geometry,
      input_crs: 'EPSG:4326',
      geometry_source: 'USER_DRAWN',
    },
    signal,
  );

function importedGeometry(value: unknown): unknown {
  if (typeof value !== 'object' || value === null) throw new Error('Expected GeoJSON geometry or a single Feature.');
  const item = value as { type?: string; geometry?: unknown; crs?: unknown };
  if (item.crs !== undefined) throw new Error('Import WGS84 GeoJSON in longitude, latitude order.');
  return item.type === 'Feature' ? item.geometry : item;
}

export function PolygonEditor({ map, onActive }: { map: MapLibreMap; onActive: (active: boolean) => void }) {
  const [active, setActive] = useState(false);
  const [history, setHistory] = useState<EditState[]>([EMPTY]);
  const current = history[history.length - 1];
  const [result, setResult] = useState<Measurement | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [point, setPoint] = useState<{ degrees: LngLat; projected?: LngLat }>({ degrees: [120.19, 23.7] });
  const operation = useRef<AbortController | null>(null);
  const pointRequest = useRef<AbortController | null>(null);
  const requestVersion = useRef(0);

  function invalidate() {
    requestVersion.current += 1;
    operation.current?.abort();
    setResult(null);
    setBusy(false);
    setError('');
  }

  function change(next: EditState) {
    invalidate();
    setHistory((previous) => [...previous.slice(-99), next]);
  }

  useEffect(
    () => () => {
      operation.current?.abort();
      pointRequest.current?.abort();
    },
    [],
  );

  useEffect(() => {
    map.addSource(SOURCE, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    map.addLayer({ id: SOURCE + '-fill', type: 'fill', source: SOURCE, paint: { 'fill-color': '#e879f9', 'fill-opacity': 0.25 } });
    map.addLayer({ id: SOURCE + '-line', type: 'line', source: SOURCE, paint: { 'line-color': '#e879f9', 'line-width': 3 } });
    return () => {
      if (!map.style) return;
      if (map.getLayer(SOURCE + '-fill')) map.removeLayer(SOURCE + '-fill');
      if (map.getLayer(SOURCE + '-line')) map.removeLayer(SOURCE + '-line');
      if (map.getSource(SOURCE)) map.removeSource(SOURCE);
    };
  }, [map]);

  useEffect(() => {
    const geometry =
      current.geometry ?? (current.draft.length >= 2 ? { type: 'LineString' as const, coordinates: current.draft } : null);
    (map.getSource(SOURCE) as GeoJSONSource | undefined)?.setData({
      type: 'FeatureCollection',
      features: geometry ? [{ type: 'Feature', geometry, properties: {} }] : [],
    });
  }, [map, current]);

  useEffect(() => {
    if (!active) return;
    const doubleClickEnabled = map.doubleClickZoom.isEnabled();
    map.doubleClickZoom.disable();
    const click = (event: { lngLat: { lng: number; lat: number } }) => {
      const degrees: LngLat = [event.lngLat.lng, event.lngLat.lat];
      setPoint({ degrees });
      pointRequest.current?.abort();
      const controller = new AbortController();
      pointRequest.current = controller;
      void post<{ x: number; y: number }>(
        'transform-point',
        {
          x: degrees[0],
          y: degrees[1],
          from_crs: 'EPSG:4326',
          to_crs: 'EPSG:3826',
        },
        controller.signal,
      )
        .then(({ x, y }) => {
          if (!controller.signal.aborted) setPoint({ degrees, projected: [x, y] });
        })
        .catch(() => {});
      if (!current.geometry && current.draft.length < 1999) {
        change({ draft: [...current.draft, degrees], geometry: null });
      }
    };
    map.on('click', click);
    return () => {
      map.off('click', click);
      if (doubleClickEnabled) map.doubleClickZoom.enable();
    };
  }, [active, current, map]);

  useEffect(() => {
    if (!active) return;
    const polygons = current.geometry ? polygonRings(current.geometry) : [[current.draft]];
    const markers = polygons.flatMap((polygon, p) =>
      polygon.flatMap((ring, r) =>
        (current.geometry ? ring.slice(0, -1) : ring).map((position, v) => {
          const element = document.createElement('button');
          element.type = 'button';
          element.className = 'gis-vertex';
          element.dataset.testid = `gis-vertex-${p}-${r}-${v}`;
          element.setAttribute('aria-label', `Vertex ${p + 1}.${r + 1}.${v + 1}`);
          element.addEventListener('click', (event) => event.stopPropagation());
          const marker = new Marker({ element, draggable: true }).setLngLat(position).addTo(map);
          marker.on('dragend', () => {
            const { lng, lat } = marker.getLngLat();
            const moved: LngLat = [lng, lat];
            if (!current.geometry) {
              change({ geometry: null, draft: current.draft.map((old, index) => (index === v ? moved : old)) });
              return;
            }
            const copy = structuredClone(current.geometry);
            const editable = polygonRings(copy)[p][r];
            editable[v] = moved;
            if (v === 0) editable[editable.length - 1] = moved;
            change({ draft: [], geometry: copy });
          });
          return marker;
        }),
      ),
    );
    return () => markers.forEach((marker) => marker.remove());
  }, [active, current, map]);

  async function validate(file?: File) {
    if (!file && !current.geometry) return;
    invalidate();
    const version = requestVersion.current;
    const controller = new AbortController();
    operation.current = controller;
    setBusy(true);
    try {
      if (file && file.size > 120 * 1024) throw new Error('GeoJSON import exceeds 120 KiB.');
      const geometry = file ? importedGeometry(JSON.parse(await file.text())) : current.geometry;
      const measured = await measure(geometry, controller.signal);
      if (version !== requestVersion.current || controller.signal.aborted) return;
      if (file) {
        const feature = geometry as FieldGeometry;
        setHistory((previous) => [...previous.slice(-99), { draft: [], geometry: feature }]);
        const bounds = new LngLatBounds();
        polygonRings(feature)
          .flat(2)
          .forEach((position) => bounds.extend(position));
        map.fitBounds(bounds, { padding: 40, maxZoom: 18, duration: 0 });
      }
      setResult(measured);
    } catch (failure) {
      if (version === requestVersion.current && !controller.signal.aborted) setError(String(failure));
    } finally {
      if (version === requestVersion.current && !controller.signal.aborted) setBusy(false);
    }
  }

  function download() {
    if (!result || !current.geometry) return;
    const blob = new Blob(
      [
        JSON.stringify(
          {
            type: 'Feature',
            geometry: current.geometry,
            properties: {
              case_id: CASE_ID,
              geometry_source: result.geometry_source,
              measurement_status: result.measurement_status,
            },
          },
          null,
          2,
        ),
      ],
      { type: 'application/geo+json' },
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'taixi-user-drawn.geojson';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <section className="studio-card" aria-label="Polygon editor">
      <h3>農地 Polygon 繪製與量測</h3>
      <button
        type="button"
        data-testid="gis-draw-toggle"
        aria-pressed={active}
        onClick={() => {
          setActive(!active);
          onActive(!active);
        }}
      >
        Polygon 編輯
      </button>
      {active && (
        <>
          <p>在地圖點選頂點，封閉後可拖曳頂點。圖形只保留於本次頁面。</p>
          <p>
            <strong>USER_DRAWN · NO_REGISTERED_SATELLITE_STATISTICS</strong>。下方衛星證據仍屬於已登錄的候選田區。
          </p>
          <p data-testid="gis-cursor-crs">
            WGS84 {point.degrees.map((value) => value.toFixed(6)).join(', ')}
            {' · '}TWD97 {point.projected?.map((value) => value.toFixed(2)).join(', ') ?? '—'}
          </p>
          <div className="studio-actions">
            <button
              type="button"
              data-testid="gis-close"
              disabled={!!current.geometry || current.draft.length < 3}
              onClick={() =>
                change({
                  draft: [],
                  geometry: { type: 'Polygon', coordinates: [[...current.draft, current.draft[0]]] },
                })
              }
            >
              封閉 Polygon
            </button>
            <button
              type="button"
              data-testid="gis-undo"
              disabled={history.length <= 1}
              onClick={() => {
                invalidate();
                setHistory((previous) => previous.slice(0, -1));
              }}
            >
              復原
            </button>
            <button
              type="button"
              data-testid="gis-clear"
              disabled={!current.geometry && !current.draft.length}
              onClick={() => change(EMPTY)}
            >
              清除
            </button>
            <button
              type="button"
              data-testid="gis-measure"
              disabled={!current.geometry || busy}
              onClick={() => void validate()}
            >
              量測面積
            </button>
            <button type="button" data-testid="gis-export" disabled={!result} onClick={download}>
              下載 GeoJSON
            </button>
            <label>
              匯入 WGS84 GeoJSON{' '}
              <input
                type="file"
                data-testid="gis-import-input"
                accept=".geojson,.json"
                onChange={(event) => {
                  const file = event.currentTarget.files?.[0];
                  event.currentTarget.value = '';
                  if (file) void validate(file);
                }}
              />
            </label>
          </div>
          {busy && <p role="status">量測中…</p>}
          {error && <p role="alert">{error}</p>}
          {result && (
            <output data-testid="gis-measure-result">
              {result.area_m2.toFixed(2)} m² · {result.area_ha.toFixed(6)} ha · 周長 {result.perimeter_m.toFixed(2)} m
              {' · '}
              {result.area_crs} · {result.measurement_status}。官方地籍面積和核定救助面積均未確認。
            </output>
          )}
        </>
      )}
    </section>
  );
}
