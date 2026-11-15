import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { CASE, type LngLat, NISAR_TAIXI, OFFICIAL_LOSS, PARCELS, TOWNSHIPS, YUNLIN_AREA, type Parcel, TREND_COLOR, bigNtd, TREND_LABEL, type Trend, geometryPath, parcelById, polygonRings, trendOf } from '../data/champi';
import { type FarmerInfo, cropName } from '../data/farmer';
import { formatDb } from '../demo/fields';
import { type Lang, type Text, useLang, useT } from '../i18n';
import { FieldRow, Icon, TrendTag } from '../ui/shared';
import { PixelPlayground } from '../ui/PixelPlayground';
import { EventPicker } from './EventPicker';
import type { ScreenProps } from './types';

const POPUP_W = 250;

const md = (d: string) => d.slice(5).replace('-', '/');
const round100 = (ha: number) => Math.max(100, Math.round(ha / 100) * 100);
const changedHa = round100(YUNLIN_AREA.excessHa);
const [flatLow, flatHigh] = YUNLIN_AREA.flattenedHa.map(round100);

type Filter = Trend | 'all';

/**
 * Local equirectangular projection around the five candidate fields, in SVG units.
 * Width is fixed; height follows the true aspect ratio of the padded extent.
 */
const PROJ = (() => {
  const pts = PARCELS.flatMap((p) => polygonRings(p.geometry).flat(2));
  const lngs = pts.map((p) => p[0]);
  const lats = pts.map((p) => p[1]);
  const pad = 0.3;
  const dLng = Math.max(...lngs) - Math.min(...lngs);
  const dLat = Math.max(...lats) - Math.min(...lats);
  const west = Math.min(...lngs) - dLng * pad;
  const east = Math.max(...lngs) + dLng * pad;
  const north = Math.max(...lats) + dLat * pad;
  const south = Math.min(...lats) - dLat * pad;
  const cos = Math.cos((((north + south) / 2) * Math.PI) / 180);
  const W = 772;
  const s = W / ((east - west) * cos);
  const H = (north - south) * s;
  const xy = ([lng, lat]: LngLat): [number, number] => [(lng - west) * cos * s, (north - lat) * s];
  return { W, H, xy, west, east, north, south, pxPerKm: s / 111.32 };
})();

const TOWN_SHAPES = TOWNSHIPS.map((town) => ({ key: town.name.en, d: geometryPath(town.geometry, PROJ.xy) }));
const SHAPES = PARCELS.map((p) => {
  const pts = polygonRings(p.geometry).flat(2).map(PROJ.xy);
  return { id: p.id, path: geometryPath(p.geometry, PROJ.xy), right: Math.max(...pts.map((q) => q[0])), left: Math.min(...pts.map((q) => q[0])), top: Math.min(...pts.map((q) => q[1])) };
});

type Landuse = 'paddy' | 'dry' | 'orchard';

/** 國土利用現況調查 level-3 farmland classes, clipped to this map's extent (public/studio/landuse_farmland_taixi.geojson). */
const LANDUSE_COLOR: Record<Landuse, string> = { paddy: '#7EE8FA', dry: '#F5E663', orchard: '#8BE38B' };
const LANDUSE_LABEL: Record<Landuse, Text> = { paddy: { zh: '水田', en: 'Paddy' }, dry: { zh: '旱田', en: 'Dry field' }, orchard: { zh: '果園', en: 'Orchard' } };

/** Loads the farmland layer the first time it is switched on; null until then, 'error' if it failed. */
function useLanduse(on: boolean) {
  const [shapes, setShapes] = useState<{ cls: Landuse; d: string }[] | null | 'error'>(null);
  useEffect(() => {
    if (!on || shapes !== null) return;
    let live = true;
    fetch('/studio/landuse_farmland_taixi.geojson')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((fc: { features: { properties: { class: Landuse }; geometry: Parcel['geometry'] }[] }) => {
        if (live) setShapes(fc.features.map((f) => ({ cls: f.properties.class, d: geometryPath(f.geometry, PROJ.xy) })));
      })
      .catch(() => live && setShapes('error'));
    return () => {
      live = false;
    };
  }, [on, shapes]);
  return shapes;
}

/** Axis-aligned placement of a NISAR scene from its corner coordinates (display only). */
function sceneRect(corners: LngLat[]) {
  const pts = corners.map(PROJ.xy);
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  return { x: Math.min(...xs), y: Math.min(...ys), width: Math.max(...xs) - Math.min(...xs), height: Math.max(...ys) - Math.min(...ys) };
}

function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setSize({ w: el.clientWidth, h: el.clientHeight });
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, size] as const;
}

function downloadCsv(rows: Parcel[], lang: Lang) {
  const header =
    lang === 'zh'
      ? '田區編號,鄉鎮,面積(公頃),VH變化 颱風前→後(dB),VH變化 颱風前→警報期間(dB),與2025同期差(dB)'
      : 'Field ID,Township,Area (ha),VH change pre→post (dB),VH change pre→warning (dB),Difference vs 2025 (dB)';
  const body = rows.map((p) => [p.id, p.town[lang], p.areaHa, p.preToPost, p.preToWarning, p.vsLastYear].join(','));
  const blob = new Blob(['﻿' + [header, ...body].join('\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'sar2action-champi-taixi-candidates.csv';
  a.click();
  URL.revokeObjectURL(url);
}

export function MapScreen({ eventId, onEvent, farmer, onFarmer, savedFarmers, ...props }: ScreenProps) {
  const [changing, setChanging] = useState(false);
  if (!eventId || changing) {
    return (
      <>
        <EventPicker
          initialId={eventId}
          initialFarmer={farmer}
          saved={savedFarmers}
          onPick={(id, info) => {
            onEvent(id);
            onFarmer(info, id);
            setChanging(false);
          }}
        />
        <PixelPlayground />
      </>
    );
  }
  return <DamageMap {...props} farmer={farmer} onChangeEvent={() => setChanging(true)} />;
}

// Mounted only once an event is chosen, so its size observer sees the real sheet.
function DamageMap({
  selectedId,
  onSelect,
  go,
  farmer,
  onChangeEvent,
}: Pick<ScreenProps, 'selectedId' | 'onSelect' | 'go' | 'farmer'> & { onChangeEvent: () => void }) {
  const t = useT();
  const { lang } = useLang();
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');
  // The post-typhoon NISAR pass only reached the northern part of Taixi, so the complete pre pass is shown first.
  const [layers, setLayers] = useState({ trend: true, pre: true, asc: false, post: false, town: true, bnd: true, landuse: false });
  const landuse = useLanduse(layers.landuse);
  const [sheetRef, sheet] = useElementSize<HTMLDivElement>();
  const [zoom, setZoom] = useState(1);
  const vw = PROJ.W / zoom;
  const vh = PROJ.H / zoom;
  const vx = (PROJ.W - vw) / 2;
  const vy = (PROJ.H - vh) / 2;

  const current = parcelById(selectedId);
  const q = query.trim().toUpperCase();
  const visible = PARCELS.filter((p) => (filter === 'all' || trendOf(p) === filter) && (!q || p.id.includes(q)));
  const count = (k: Filter) => PARCELS.filter((p) => k === 'all' || trendOf(p) === k).length;

  // Map SVG uses "meet" scaling (contain), so viewBox → pixel is a uniform scale plus centering offset.
  const popupPos = useMemo(() => {
    const shape = SHAPES.find((c) => c.id === current?.id);
    if (!shape || !sheet.w) return { left: 0, top: 0 };
    const s = Math.min(sheet.w / vw, sheet.h / vh);
    const ox = (sheet.w - vw * s) / 2 - vx * s;
    const oy = (sheet.h - vh * s) / 2 - vy * s;
    let left = ox + shape.right * s + 16;
    // Keep clear of the layers card (top right, 200px wide).
    if (left > sheet.w - POPUP_W - 232) left = ox + shape.left * s - POPUP_W - 16;
    const top = Math.min(Math.max(80, oy + shape.top * s - 20), Math.max(80, sheet.h - 260));
    return { left: Math.max(16, left), top };
  }, [current?.id, sheet.w, sheet.h, vw, vh, vx, vy]);

  const sheetClass = ['sheet', !layers.trend && 'map-hide-dmg', !layers.bnd && 'map-hide-bnd'].filter(Boolean).join(' ');
  const [pre, post] = NISAR_TAIXI.scenes;
  const asc = NISAR_TAIXI.ascending;
  const gridLngs: number[] = [];
  for (let lng = Math.ceil(PROJ.west * 100) / 100; lng < PROJ.east; lng += 0.01) gridLngs.push(lng);
  const gridLats: number[] = [];
  for (let lat = Math.ceil(PROJ.south * 100) / 100; lat < PROJ.north; lat += 0.01) gridLats.push(lat);
  const kmPx = PROJ.pxPerKm;

  return (
    <>
      <div className={sheetClass} ref={sheetRef}>
        <svg className="map" viewBox={`${vx} ${vy} ${vw} ${vh}`} preserveAspectRatio="xMidYMid meet" style={{ overflow: 'visible' }} aria-label={t('候選田區地圖', 'Candidate field map')}>
          {([['pre', pre], ['asc', asc], ['post', post]] as const).map(
            ([key, scene]) =>
              layers[key] && (
                <image key={key} href={scene.image.RGB} {...sceneRect(scene.corners)} preserveAspectRatio="none" opacity={0.9} style={{ imageRendering: 'pixelated' }} />
              ),
          )}
          {layers.landuse && Array.isArray(landuse) && (
            <g className="landuse" aria-hidden="true">
              {landuse.map((f, i) => (
                <path key={i} d={f.d} fill={LANDUSE_COLOR[f.cls]} fillOpacity={0.22} stroke={LANDUSE_COLOR[f.cls]} strokeWidth={1} vectorEffect="non-scaling-stroke" />
              ))}
            </g>
          )}
          <g stroke="#BFD0F5" strokeOpacity=".25" strokeWidth="1">
            {gridLngs.map((lng) => {
              const [x] = PROJ.xy([lng, PROJ.north]);
              return <line key={lng} x1={x} y1={0} x2={x} y2={PROJ.H} />;
            })}
            {gridLats.map((lat) => {
              const [, y] = PROJ.xy([PROJ.west, lat]);
              return <line key={lat} x1={0} y1={y} x2={PROJ.W} y2={y} />;
            })}
          </g>
          {layers.town && (
            <g className="townships" aria-hidden="true">
              {TOWN_SHAPES.map((town) => (
                <path key={town.key} d={town.d} />
              ))}
            </g>
          )}
          <g fontFamily="IBM Plex Mono" fontSize="9" fill="#BFD0F5" fillOpacity=".75">
            {gridLngs.map((lng) => (
              <text key={lng} x={PROJ.xy([lng, PROJ.north])[0] + 3} y={PROJ.H - 6}>
                {lng.toFixed(2)}°E
              </text>
            ))}
          </g>
          <g transform={`translate(${PROJ.W - 70} ${PROJ.H - 110})`} stroke="#BFD0F5" fill="none" strokeWidth="1.2">
            <circle r="16" />
            <path d="M0 -22 L5 0 L0 -4 L-5 0Z" fill="#BFD0F5" />
            <text x="-4" y="-26" fontFamily="IBM Plex Mono" fontSize="10" fill="#BFD0F5" stroke="none">
              N
            </text>
          </g>
          <g transform={`translate(${PROJ.W - 240} ${PROJ.H - 60})`} fontFamily="IBM Plex Mono" fontSize="9" fill="#BFD0F5">
            <rect width={kmPx / 2} height="5" fill="#BFD0F5" />
            <rect x={kmPx / 2} width={kmPx / 2} height="5" fill="none" stroke="#BFD0F5" />
            <text y="18">0</text>
            <text x={kmPx / 2 - 8} y="18">0.5</text>
            <text x={kmPx - 8} y="18">1 km</text>
          </g>
          {SHAPES.map((shape) => {
            const p = PARCELS.find((x) => x.id === shape.id)!;
            const select = () => onSelect(p.id);
            return (
              <g key={p.id}>
                <path
                  fillRule="evenodd"
                  className={`parcel${p.id === current?.id ? ' sel' : ''}`}
                  d={shape.path}
                  fill={TREND_COLOR[trendOf(p)]}
                  fillOpacity={0.7}
                  onClick={select}
                  tabIndex={0}
                  aria-label={`${t('田區', 'Field')} ${p.id}, ${t(TREND_LABEL[trendOf(p)])} ${formatDb(p.preToPost)}`}
                  onKeyDown={(e) => e.key === 'Enter' && select()}
                />
                <text className="parcel-label" x={shape.right + 4} y={shape.top + 10}>
                  {p.id.replace('YL-CAND-', '')}
                </text>
              </g>
            );
          })}
        </svg>

        <div className="sheet-title">
          {CASE.id}
          <div className="sheet-title-row">
            <b>{t(CASE.town)}</b>
            <button className="btn change-event" onClick={onChangeEvent}>
              {t('更換事件', 'Change event')}
            </button>
          </div>
          {`${((PROJ.north + PROJ.south) / 2).toFixed(2)}°N ${((PROJ.west + PROJ.east) / 2).toFixed(2)}°E`}
        </div>

        <div className="bp-card layers" style={{ right: 16, top: 16, width: 200 }}>
          <div className="eyebrow" style={{ marginBottom: 4 }}>
            {t('LAYERS 圖層', 'LAYERS')}
          </div>
          {(
            [
              ['trend', t('VH 變化（田區著色）', 'VH change (field colour)')],
              ['pre', `NISAR ${t('颱風前', 'pre')} ${md(pre.date)}`],
              ['asc', `NISAR ${t('颱風後', 'post')} ${md(asc.date)}`],
              ['post', `NISAR ${t('颱風後', 'post')} ${md(post.date)}`],
              ['town', t('鄉鎮界線', 'Township boundaries')],
              ['bnd', t('田區邊界', 'Field boundaries')],
              ['landuse', t('農地類型（國土利用）', 'Farmland type (land use)')],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              <input type="checkbox" checked={layers[key]} onChange={(e) => setLayers((l) => ({ ...l, [key]: e.target.checked }))} />
              {label}
              {key === 'town' && <i className="dash-key" aria-hidden="true" />}
            </label>
          ))}
          {layers.landuse && (
            <div className="landuse-key">
              {landuse === 'error' ? (
                <p role="status">{t('農地圖層載入失敗。', 'The farmland layer failed to load.')}</p>
              ) : (
                <>
                  <div className="legend">
                    {(Object.keys(LANDUSE_COLOR) as Landuse[]).map((k) => (
                      <span key={k}>
                        <i className="hollow" style={{ borderColor: LANDUSE_COLOR[k], background: `${LANDUSE_COLOR[k]}38` }} />
                        {t(LANDUSE_LABEL[k])}
                      </span>
                    ))}
                  </div>
                  <p className="cap">
                    {t('國土利用現況調查 2024/11，只含農作使用。5 塊候選田都不在圖層內。', 'Land Use Survey, Nov 2024, farmland only. No candidate field is inside it.')}
                  </p>
                </>
              )}
            </div>
          )}
        </div>

        <div className="bp-card" style={{ left: 16, bottom: 16, maxWidth: 'calc(100% - 120px)' }}>
          <div className="eyebrow">{t('Sentinel-1 VH · 颱風前 10/11 → 後 11/04', 'Sentinel-1 VH · pre 10/11 → post 11/04')}</div>
          <div className="legend">
            {(['up', 'down'] as const).map((k) => (
              <span key={k}>
                <i style={{ background: TREND_COLOR[k] }} />
                {t(TREND_LABEL[k])}
              </span>
            ))}
          </div>
        </div>

        <div className="zoom">
          <button aria-label={t('放大', 'Zoom in')} disabled={zoom >= 2.5} onClick={() => setZoom((z) => Math.min(2.5, z + 0.5))}>
            +
          </button>
          <button aria-label={t('縮小', 'Zoom out')} disabled={zoom <= 1} onClick={() => setZoom((z) => Math.max(1, z - 0.5))}>
            −
          </button>
        </div>

        {current && (
          <div className="popup" style={popupPos} aria-live="polite">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <b className="mono" style={{ fontSize: 17 }}>
                {current.id}
              </b>
              <TrendTag trend={trendOf(current)} />
            </div>
            <div className="cap">
              {t(current.town)} · {current.areaHa.toFixed(4)} {t('公頃', 'ha')} ·{' '}
              {farmer ? `${t('您登記的作物：', 'Your crop: ')}${cropName(farmer, lang)}` : t('作物未驗證', 'Crop unverified')}
            </div>
            <div className="figs">
              <div>
                <b>{formatDb(current.preToPost)}</b>
                <span>{t('颱風前→後', 'Pre → post')}</span>
              </div>
              <div>
                <b>{formatDb(current.vsLastYear)}</b>
                <span>{t('與 2025 同期', 'vs 2025')}</span>
              </div>
            </div>
            <button className="btn btn-primary btn-block" onClick={() => go('compare')}>
              {t('查看前後比對 →', 'Compare before/after →')}
            </button>
          </div>
        )}
      </div>

      <aside className="panel">
        <section className="loss-summary" aria-labelledby="loss-title">
          <div className="eyebrow">
            {t(
              'SAR2Action 雷達估算 · 全雲林農地',
              'SAR2Action radar estimate · all Yunlin',
            )}
          </div>
          <h2 id="loss-title" className="h3">
            {t('這次颱風的受損面積', 'Area this typhoon hit')}
          </h2>
          <p className="loss-line">
            {t('颱風期間約 ', 'During the typhoon ~')}
            <b>{changedHa.toLocaleString()}{t(' 公頃', ' ha')}</b>
            {t('農地雷達明顯變化，其中約 ', ' of farmland changed clearly on radar; ~')}
            <b>
              {flatLow}–{flatHigh}
              {t(' 公頃', ' ha')}
            </b>
            {t('整片倒伏或淹水。', ' of it was flattened or flooded.')}
          </p>
          <p className="loss-official">
            {t(
              `官方（農業部 ${OFFICIAL_LOSS.date}）：全台農作物受害 ${OFFICIAL_LOSS.cropAreaHa.toLocaleString()} 公頃，雲林損失 ${bigNtd(OFFICIAL_LOSS.yunlinNtd, lang)}。`,
              `Official (MOA ${OFFICIAL_LOSS.date}): ${OFFICIAL_LOSS.cropAreaHa.toLocaleString()} ha of crops damaged in Taiwan; Yunlin lost NT$${bigNtd(OFFICIAL_LOSS.yunlinNtd, lang)}.`,
            )}{' '}
            <a href={OFFICIAL_LOSS.url} target="_blank" rel="noreferrer">
              {t('原始報告', 'Source')}
            </a>
          </p>
        </section>
        <div className="panel-head" style={{ paddingBottom: 0, border: 0 }}>
          <div className="eyebrow">{t('Candidate fields · 農田坵塊圖', 'Official farmland map')}</div>
          <h2 className="h2">{t('候選田區', 'Candidate fields')}</h2>
        </div>
        <label className="search">
          <Icon name="search" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('搜尋田區編號，例如 YL-CAND-03', 'Search field ID, e.g. YL-CAND-03')} aria-label={t('搜尋田區編號', 'Search field ID')} />
        </label>
        <div className="chips">
          {(
            [
              ['all', t('全部', 'All')],
              ['up', t(TREND_LABEL.up)],
              ['down', t(TREND_LABEL.down)],
            ] as const
          ).map(([k, label]) => (
            <button key={k} className="chip" aria-pressed={filter === k} onClick={() => setFilter(k)}>
              {label}
              <span className="mono">{count(k)}</span>
            </button>
          ))}
        </div>
        <div className="list" role="listbox" aria-label={t('候選田區', 'Candidate fields')}>
          {visible.length ? (
            visible.map((p) => <FieldRow key={p.id} parcel={p} selected={p.id === current?.id} onSelect={onSelect} />)
          ) : (
            <p className="cap" style={{ padding: 20 }}>
              {t('沒有符合的田區', 'No matching fields')}
            </p>
          )}
        </div>
        <div className="panel-foot">
          <button className="btn btn-cut btn-block" onClick={() => downloadCsv(visible, lang)}>
            <Icon name="download" />
            {t('匯出候選清單 CSV', 'Export candidates CSV')}
          </button>
        </div>
      </aside>
    </>
  );
}
