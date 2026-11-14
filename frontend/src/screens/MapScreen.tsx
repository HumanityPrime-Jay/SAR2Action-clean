import React, { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { CASE, type LngLat, NISAR_TAIXI, PARCELS, type Parcel, TREND_COLOR, TREND_LABEL, type Trend, trendOf } from '../data/champi';
import { formatDb } from '../demo/fields';
import { FieldRow, Icon, TrendTag } from '../ui/shared';
import { EventPicker } from './EventPicker';
import type { ScreenProps } from './types';

const POPUP_W = 250;

const md = (d: string) => d.slice(5).replace('-', '/');

type Filter = Trend | 'all';

/**
 * Local equirectangular projection around the five candidate fields, in SVG units.
 * Width is fixed; height follows the true aspect ratio of the padded extent.
 */
const PROJ = (() => {
  const pts = PARCELS.flatMap((p) => p.ring);
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

const SHAPES = PARCELS.map((p) => {
  const pts = p.ring.map(PROJ.xy);
  return { id: p.id, pts, right: Math.max(...pts.map((q) => q[0])), left: Math.min(...pts.map((q) => q[0])), top: Math.min(...pts.map((q) => q[1])) };
});

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

function downloadCsv(rows: Parcel[]) {
  const header = '田區編號,鄉鎮,面積(公頃),VH變化 颱風前→後(dB),VH變化 颱風前→警報期間(dB),與2025同期差(dB)';
  const body = rows.map((p) => [p.id, p.town, p.areaHa, p.preToPost, p.preToWarning, p.vsLastYear].join(','));
  const blob = new Blob(['﻿' + [header, ...body].join('\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'sar2action-champi-taixi-candidates.csv';
  a.click();
  URL.revokeObjectURL(url);
}

export function MapScreen({ eventId, onEvent, ...props }: ScreenProps) {
  const [changing, setChanging] = useState(false);
  if (!eventId || changing) {
    return (
      <EventPicker
        initialId={eventId}
        onPick={(id) => {
          onEvent(id);
          setChanging(false);
        }}
      />
    );
  }
  return <DamageMap {...props} onChangeEvent={() => setChanging(true)} />;
}

// Mounted only once an event is chosen, so its size observer sees the real sheet.
function DamageMap({ selectedId, onSelect, go, onChangeEvent }: Pick<ScreenProps, 'selectedId' | 'onSelect' | 'go'> & { onChangeEvent: () => void }) {
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');
  const [layers, setLayers] = useState({ trend: true, post: true, pre: false, bnd: true });
  const [sheetRef, sheet] = useElementSize<HTMLDivElement>();
  const [zoom, setZoom] = useState(1);
  const vw = PROJ.W / zoom;
  const vh = PROJ.H / zoom;
  const vx = (PROJ.W - vw) / 2;
  const vy = (PROJ.H - vh) / 2;

  const current = PARCELS.find((p) => p.id === selectedId) ?? PARCELS[0];
  const q = query.trim().toUpperCase();
  const visible = PARCELS.filter((p) => (filter === 'all' || trendOf(p) === filter) && (!q || p.id.includes(q)));
  const count = (k: Filter) => PARCELS.filter((p) => k === 'all' || trendOf(p) === k).length;

  // Map SVG uses "meet" scaling (contain), so viewBox → pixel is a uniform scale plus centering offset.
  const popupPos = useMemo(() => {
    const shape = SHAPES.find((c) => c.id === current.id);
    if (!shape || !sheet.w) return { left: 0, top: 0 };
    const s = Math.min(sheet.w / vw, sheet.h / vh);
    const ox = (sheet.w - vw * s) / 2 - vx * s;
    const oy = (sheet.h - vh * s) / 2 - vy * s;
    let left = ox + shape.right * s + 16;
    // Keep clear of the layers card (top right, 200px wide).
    if (left > sheet.w - POPUP_W - 232) left = ox + shape.left * s - POPUP_W - 16;
    const top = Math.min(Math.max(80, oy + shape.top * s - 20), Math.max(80, sheet.h - 260));
    return { left: Math.max(16, left), top };
  }, [current.id, sheet.w, sheet.h, vw, vh, vx, vy]);

  const sheetClass = ['sheet', !layers.trend && 'map-hide-dmg', !layers.bnd && 'map-hide-bnd'].filter(Boolean).join(' ');
  const [pre, post] = NISAR_TAIXI.scenes;
  const gridLngs: number[] = [];
  for (let lng = Math.ceil(PROJ.west * 100) / 100; lng < PROJ.east; lng += 0.01) gridLngs.push(lng);
  const gridLats: number[] = [];
  for (let lat = Math.ceil(PROJ.south * 100) / 100; lat < PROJ.north; lat += 0.01) gridLats.push(lat);
  const kmPx = PROJ.pxPerKm;

  return (
    <>
      <div className={sheetClass} ref={sheetRef}>
        <svg className="map" viewBox={`${vx} ${vy} ${vw} ${vh}`} preserveAspectRatio="xMidYMid meet" style={{ overflow: 'visible' }} aria-label="候選田區地圖">
          {([['pre', pre], ['post', post]] as const).map(
            ([key, scene]) =>
              layers[key] && (
                <image key={key} href={scene.image.HH} {...sceneRect(scene.corners)} preserveAspectRatio="none" opacity={0.85} style={{ imageRendering: 'pixelated' }} />
              ),
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
                <polygon
                  className={`parcel${p.id === current.id ? ' sel' : ''}`}
                  points={shape.pts.map((pt) => pt.join(',')).join(' ')}
                  fill={TREND_COLOR[trendOf(p)]}
                  fillOpacity={0.7}
                  onClick={select}
                  tabIndex={0}
                  aria-label={`田區 ${p.id}，${TREND_LABEL[trendOf(p)]} ${formatDb(p.preToPost)}`}
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
            <b>{CASE.town}</b>
            <button className="btn change-event" onClick={onChangeEvent}>
              更換事件
            </button>
          </div>
          {`${((PROJ.north + PROJ.south) / 2).toFixed(2)}°N ${((PROJ.west + PROJ.east) / 2).toFixed(2)}°E`}
        </div>

        <div className="bp-card layers" style={{ right: 16, top: 16, width: 200 }}>
          <div className="eyebrow" style={{ marginBottom: 4 }}>
            LAYERS 圖層
          </div>
          {(
            [
              ['trend', 'VH 變化（田區著色）'],
              ['post', `NISAR 颱風後 ${md(post.date)}`],
              ['pre', `NISAR 颱風前 ${md(pre.date)}`],
              ['bnd', '田區邊界'],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              <input type="checkbox" checked={layers[key]} onChange={(e) => setLayers((l) => ({ ...l, [key]: e.target.checked }))} />
              {label}
            </label>
          ))}
        </div>

        <div className="bp-card" style={{ left: 16, bottom: 16, maxWidth: 'calc(100% - 120px)' }}>
          <div className="eyebrow">Sentinel-1 VH · 颱風前 10/11 → 後 11/04</div>
          <div className="legend">
            {(['up', 'down'] as const).map((t) => (
              <span key={t}>
                <i style={{ background: TREND_COLOR[t] }} />
                {TREND_LABEL[t]}
              </span>
            ))}
          </div>
          <div className="cap" style={{ marginTop: 4 }}>
            描述性觀測，不代表受損判定
          </div>
        </div>

        <div className="zoom">
          <button aria-label="放大" disabled={zoom >= 2.5} onClick={() => setZoom((z) => Math.min(2.5, z + 0.5))}>
            +
          </button>
          <button aria-label="縮小" disabled={zoom <= 1} onClick={() => setZoom((z) => Math.max(1, z - 0.5))}>
            −
          </button>
        </div>

        <div className="popup" style={popupPos} aria-live="polite">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <b className="mono" style={{ fontSize: 17 }}>
              {current.id}
            </b>
            <TrendTag trend={trendOf(current)} />
          </div>
          <div className="cap">
            {current.town} · {current.areaHa} 公頃 · 作物未驗證
          </div>
          <div className="figs">
            <div>
              <b>{formatDb(current.preToPost)}</b>
              <span>颱風前→後</span>
            </div>
            <div>
              <b>{formatDb(current.vsLastYear)}</b>
              <span>與 2025 同期</span>
            </div>
          </div>
          <button className="btn btn-primary btn-block" onClick={() => go('compare')}>
            查看前後比對 →
          </button>
        </div>
      </div>

      <aside className="panel">
        <div className="panel-head" style={{ paddingBottom: 0, border: 0 }}>
          <div className="eyebrow">Candidate fields · 農田坵塊圖</div>
          <h2 className="h2">候選田區</h2>
        </div>
        <label className="search">
          <Icon name="search" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜尋田區編號，例如 YL-CAND-03" aria-label="搜尋田區編號" />
        </label>
        <div className="chips">
          {(
            [
              ['all', '全部'],
              ['up', 'VH 上升'],
              ['down', 'VH 下降'],
            ] as const
          ).map(([k, label]) => (
            <button key={k} className="chip" aria-pressed={filter === k} onClick={() => setFilter(k)}>
              {label}
              <span className="mono">{count(k)}</span>
            </button>
          ))}
        </div>
        <div className="list" role="listbox" aria-label="候選田區">
          {visible.length ? (
            visible.map((p) => <FieldRow key={p.id} parcel={p} selected={p.id === current.id} onSelect={onSelect} />)
          ) : (
            <p className="cap" style={{ padding: 20 }}>
              沒有符合的田區
            </p>
          )}
        </div>
        <div className="panel-foot">
          <button className="btn btn-cut btn-block" onClick={() => downloadCsv(visible)}>
            <Icon name="download" />
            匯出候選清單 CSV
          </button>
        </div>
      </aside>
    </>
  );
}
