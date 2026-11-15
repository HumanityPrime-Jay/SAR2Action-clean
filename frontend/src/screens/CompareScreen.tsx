import React, { useRef, useState } from 'react';
import {
  CAUSES,
  INVESTIGATED_FIELD,
  type LngLat,
  NISAR_TAIXI,
  type Parcel,
  QA_TESTS,
  type VhPoint,
  WARNING,
  geometryPath,
  parcelById,
  polygonRings,
} from '../data/champi';
import { EVENTS } from '../data/events';
import { cropName } from '../data/farmer';
import { formatDb } from '../demo/fields';
import { type Lang, type Text, useLang, useT } from '../i18n';
import { Icon } from '../ui/shared';
import { EvidenceGraph } from './EvidenceGraph';
import type { ScreenProps } from './types';

type Mode = 'side' | 'swipe';
type Pol = 'HH' | 'HV';
type Tab = 'findings' | 'checks' | 'causes';
type Scene = (typeof NISAR_TAIXI.scenes)[number];

/** Half-width of the area shown around the selected field, metres. */
const HALF_M = 1200;

/** Local metric projection centred on the parcel. */
function projector(ring: LngLat[]) {
  const cx = ring.reduce((s, p) => s + p[0], 0) / ring.length;
  const cy = ring.reduce((s, p) => s + p[1], 0) / ring.length;
  const cos = Math.cos((cy * Math.PI) / 180);
  return ([lng, lat]: LngLat): [number, number] => [(lng - cx) * cos * 111_320, (cy - lat) * 111_320];
}

/** Real NISAR scene around the parcel, with the official field boundary on top. */
function SceneView({ scene, pol, parcel, label }: { scene: Scene; pol: Pol; parcel: Parcel; label?: string }) {
  const xy = projector(polygonRings(parcel.geometry).flat(2));
  const c = scene.corners.map(xy);
  const xs = c.map((p) => p[0]);
  const ys = c.map((p) => p[1]);
  return (
    <svg viewBox={`${-HALF_M} ${-HALF_M} ${2 * HALF_M} ${2 * HALF_M}`} preserveAspectRatio="xMidYMid slice" role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <rect x={-HALF_M * 3} y={-HALF_M * 3} width={HALF_M * 6} height={HALF_M * 6} fill="#111" />
      <image
        href={scene.image[pol]}
        x={Math.min(...xs)}
        y={Math.min(...ys)}
        width={Math.max(...xs) - Math.min(...xs)}
        height={Math.max(...ys) - Math.min(...ys)}
        preserveAspectRatio="none"
        style={{ imageRendering: 'pixelated' }}
      />
      <path d={geometryPath(parcel.geometry, xy)} fill="none" stroke="#7FA6FF" strokeWidth={2.5} strokeDasharray="7 5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

const sceneLabel = (s: Scene, pol: Pol, parcel: Parcel, lang: Lang) =>
  lang === 'zh'
    ? `NISAR ${pol} 雷達影像，${s.date}（${s.period === 'PRE' ? '颱風前' : '颱風後'}），田區 ${parcel.id} 周邊 2.4 公里`
    : `NISAR ${pol} radar image, ${s.date} (${s.period === 'PRE' ? 'pre-typhoon' : 'post-typhoon'}), 2.4 km around field ${parcel.id}`;

const md = (d: string) => d.slice(5).replace('-', '/');

function SwipeViewer({ pol, parcel }: { pol: Pol; parcel: Parcel }) {
  const t = useT();
  const { lang } = useLang();
  if (!parcel) return <p role="status">Taixi field not found</p>;
  const [pre, post] = NISAR_TAIXI.scenes;
  const [pct, setPct] = useState(50);
  const ref = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const update = (clientX: number) => {
    const r = ref.current?.getBoundingClientRect();
    if (r) setPct(Math.min(98, Math.max(2, ((clientX - r.left) / r.width) * 100)));
  };
  return (
    <div
      className="swipe"
      ref={ref}
      style={{ display: 'block' }}
      onPointerDown={(e) => {
        dragging.current = true;
        e.currentTarget.setPointerCapture(e.pointerId);
        update(e.clientX);
      }}
      onPointerMove={(e) => dragging.current && update(e.clientX)}
      onPointerUp={() => (dragging.current = false)}
      role="slider"
      aria-label={t('颱風前後影像滑桿', 'Before/after image slider')}
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'ArrowLeft') setPct((p) => Math.max(2, p - 5));
        if (e.key === 'ArrowRight') setPct((p) => Math.min(98, p + 5));
      }}
    >
      <div className="layer">
        <SceneView scene={post} pol={pol} parcel={parcel} label={sceneLabel(post, pol, parcel, lang)} />
      </div>
      <div className="layer" style={{ clipPath: `inset(0 ${100 - pct}% 0 0)` }}>
        <SceneView scene={pre} pol={pol} parcel={parcel} />
      </div>
      <div className="handle" style={{ left: `${pct}%` }} />
      <span className="cap-tl swipe-cap">
        ← PRE {md(pre.date)} ｜ POST {md(post.date)} →
      </span>
    </div>
  );
}

/** A point on the VH chart worth a note: which series, which date, and what it shows. */
interface Finding {
  year: 2025 | 2026;
  date: string;
  db: number;
  text: Text;
}

/** VH changes smaller than these, in dB, are read as "about the same". */
const EVENT_DB = 2;
const AFTER_DB = 1.5;

/** Up to three plain-language notes on the field's VH series; descriptive only, never a cause. */
function findings(parcel: Parcel): Finding[] {
  const [pre, mid, post] = parcel.vh2026;
  const [pre25, mid25] = parcel.vh2025;
  const d = parcel.preToWarning;
  const after = parcel.preToPost;
  const d25 = mid25.db - pre25.db;
  const big = Math.abs(d) >= EVENT_DB;
  const notes: Finding[] = [
    {
      year: 2026,
      date: mid.date,
      db: mid.db,
      text: !big
        ? { zh: `警報期間變化不大（${formatDb(d)}）。`, en: `Little change during the warning (${formatDb(d)}).` }
        : d > 0
          ? { zh: `警報期間回波升高 ${formatDb(d)}。地表變粗糙或變濕，回波都會變強。`, en: `Return rose ${formatDb(d)} during the warning. Rougher or wetter ground both raise it.` }
          : { zh: `警報期間回波降低 ${formatDb(d)}。積水會讓回波變弱。`, en: `Return fell ${formatDb(d)} during the warning. Standing water lowers it.` },
    },
    {
      year: 2026,
      date: post.date,
      db: post.db,
      text:
        Math.abs(after) < AFTER_DB
          ? { zh: `颱風後回到接近颱風前（${formatDb(after)}），變化沒有留下來。`, en: `Back near the pre-typhoon level (${formatDb(after)}); the change did not last.` }
          : after > 0
            ? { zh: `颱風後仍比颱風前高 ${formatDb(after)}。`, en: `Still ${formatDb(after)} above the pre-typhoon level.` }
            : { zh: `颱風後仍比颱風前低 ${formatDb(after)}。`, en: `Still ${formatDb(after)} below the pre-typhoon level.` },
    },
    {
      year: 2025,
      date: mid25.date,
      db: mid25.db,
      text:
        big && Math.sign(d25) === Math.sign(d) && Math.abs(d25) >= Math.abs(d) / 2
          ? { zh: `去年同期也${d25 > 0 ? '升高' : '降低'} ${formatDb(d25)}，可能是季節變化，不一定是颱風。`, en: `Same period last year also moved ${formatDb(d25)}: possibly seasonal, not necessarily the typhoon.` }
          : { zh: `去年同期變化 ${formatDb(d25)}。`, en: `Same period last year: ${formatDb(d25)}.` },
    },
  ];
  return notes;
}

export function CompareScreen({ selectedId, go, farmer, eventId }: ScreenProps) {
  const t = useT();
  const { lang } = useLang();
  const [mode, setMode] = useState<Mode>('side');
  const [pol, setPol] = useState<Pol>('HH');
  const [tab, setTab] = useState<Tab>('findings');
  const [graphOpen, setGraphOpen] = useState(false);
  const [activeNote, setActiveNote] = useState<number | null>(null);
  const event = EVENTS.find((e) => e.id === eventId);
  // The comparison follows the damage map: pick a disaster (and a field) there first.
  if (!event?.hasImagery) {
    return (
      <div className="cmp-empty">
        <h1 className="h2">{event ? t('這場災害還沒有雷達影像', 'No radar imagery for this disaster yet') : t('先在受災地圖選一場災害', 'Pick a disaster on the damage map first')}</h1>
        <button className="btn btn-primary" onClick={() => go('map')}>
          {t('到受災地圖 →', 'Go to the damage map →')}
        </button>
      </div>
    );
  }
  const parcel = parcelById(selectedId);
  if (!parcel) return <p role="status">Taixi field not found</p>;
  const [pre, post] = NISAR_TAIXI.scenes;
  const notes = findings(parcel);

  return (
    <>
      <div className="cmp-main">
        <div className="cmp-head">
          <button className="back" onClick={() => go('map')}>
            <Icon name="back" size={16} />
            {t('地圖', 'Map')}
          </button>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <h1 className="h2">
                {t('田區', 'Field')} <span className="mono">{parcel.id}</span>
              </h1>
              <span className="seal neutral">{t('OBSERVED · 原因未知', 'OBSERVED · cause unknown')}</span>
            </div>
            <div className="cap">
              {lang === 'zh' ? `雲林縣${parcel.town.zh}` : `${parcel.town.en}, Yunlin`} · {parcel.areaHa.toFixed(4)} {t('公頃', 'ha')} ·{' '}
              {farmer ? cropName(farmer, lang) : t('作物未知', 'Crop unknown')}
            </div>
          </div>
          <div className="seg" role="group" aria-label={t('極化', 'Polarization')}>
            {(['HH', 'HV'] as const).map((p) => (
              <button key={p} aria-pressed={pol === p} onClick={() => setPol(p)}>
                {p}
              </button>
            ))}
          </div>
          <div className="seg" role="group" aria-label={t('比對模式', 'Compare mode')}>
            {(
              [
                ['side', t('並排', 'Side by side')],
                ['swipe', t('滑桿', 'Slider')],
              ] as const
            ).map(([m, label]) => (
              <button key={m} aria-pressed={mode === m} onClick={() => setMode(m)}>
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="viewer">
          {mode === 'swipe' ? (
            <SwipeViewer pol={pol} parcel={parcel} />
          ) : (
            [pre, post].map((s) => (
              <div key={s.period} className={`frame ${s.period.toLowerCase()}`}>
                <span className="cap-tl">
                  {s.period} · NISAR L-BAND · {s.date}
                </span>
                <SceneView scene={s} pol={pol} parcel={parcel} label={sceneLabel(s, pol, parcel, lang)} />
                <span className="ticks" />
                <span className="cap-br">
                  {pol} · {s.crid} {s.maturity === 'PROVISIONAL' ? t('暫定版', 'provisional') : t('驗證版', 'validated')}
                </span>
              </div>
            ))
          )}
        </div>

        <div className="metrics">
          <div className="metric">
            <div className="eyebrow">{t('VH 颱風前→後', 'VH pre → post')}</div>
            <div className="v">{formatDb(parcel.preToPost)}</div>
            <div className="cap">Sentinel-1 · 10/11 → 11/04</div>
          </div>
          <div className="metric">
            <div className="eyebrow">{t('VH 颱風前→警報中', 'VH pre → warning')}</div>
            <div className="v">{formatDb(parcel.preToWarning)}</div>
            <div className="cap">10/11 → 10/23</div>
          </div>
          <div className="metric">
            <div className="eyebrow">{t('與 2025 同期差', 'vs same period 2025')}</div>
            <div className="v">{formatDb(parcel.vsLastYear)}</div>
            <div className="cap">{t('11/04 對 2025-11-02', '11/04 vs 2025-11-02')}</div>
          </div>
          <div className="metric">
            <div className="eyebrow">{t('判定', 'Verdict')}</div>
            <div className="v">{t('原因未知', 'Unknown')}</div>
            <button className="link cap" onClick={() => setTab('causes')}>
              {t(`${CAUSES.length} 個可能原因 →`, `${CAUSES.length} possible causes →`)}
            </button>
          </div>
        </div>
      </div>

      <aside className="panel">
        <div className="panel-head panel-tabs">
          <div className="seg" role="tablist" aria-label={t('判讀', 'Interpretation')}>
            {(
              [
                ['findings', t('看出什麼', 'What it shows')],
                ['checks', t('判讀檢核', 'Evidence checks')],
                ['causes', t('可能原因', 'Possible causes')],
              ] as [Tab, string][]
            ).map(([k, label]) => (
              <button key={k} id={`tab-${k}`} role="tab" aria-selected={tab === k} aria-controls={`tabpanel-${k}`} onClick={() => setTab(k)}>
                {label}
              </button>
            ))}
          </div>
          {parcel.id !== INVESTIGATED_FIELD && (
            <div className="eyebrow">
              {t('調查田區', 'Investigated field')} · {INVESTIGATED_FIELD}
            </div>
          )}
        </div>
        <div className="panel-body" id={`tabpanel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`}>
          {tab === 'findings' ? (
            <div className="findings">
              <div className="eyebrow">
                {t('VH 回波時序 (dB)', 'VH backscatter (dB)')} · {parcel.id}
              </div>
              <VhChart parcel={parcel} notes={notes} active={activeNote} />
              <ol className="finding-list">
                {notes.map((n, i) => (
                  <li key={i} className={activeNote === i ? 'on' : undefined} onMouseEnter={() => setActiveNote(i)} onMouseLeave={() => setActiveNote(null)}>
                    <span className="finding-no" aria-hidden="true">
                      {i + 1}
                    </span>
                    <span>
                      <span className="cap mono">
                        {n.year} · {md(n.date)}
                      </span>
                      {t(n.text)}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          ) : tab === 'checks' ? (
            <ul className="qa-list">
              {QA_TESTS.map((q) => (
                <li key={q.id}>
                  <span className={`qa-mark ${q.pass ? 'pass' : 'fail'}`}>{q.pass ? t('通過', 'Pass') : t('未通過', 'Fail')}</span>
                  <span>
                    <b>{t(q.label)}</b>
                    <span className="cap">{t(q.result)}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <ul className="qa-list">
              {CAUSES.map((c) => (
                <li key={c.id}>
                  <span className="qa-mark open">{c.tested ? t('不確定', 'Unclear') : t('未檢驗', 'Untested')}</span>
                  <span>
                    <b>{t(c.label)}</b>
                    <span className="cap">{t(c.check)}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <button className="link graph-open" onClick={() => setGraphOpen(true)}>
            {t('證據關係圖', 'Evidence graph')}
          </button>
        </div>
        <div className="panel-foot">
          <button className="btn btn-primary btn-block" onClick={() => go('assist')}>
            {t('用此田區試算補助 →', 'Estimate relief for this field →')}
          </button>
          <button className="btn btn-line btn-block" onClick={() => window.print()}>
            {t('匯出證據報告 PDF', 'Export evidence report (PDF)')}
          </button>
        </div>
      </aside>
      {graphOpen && <EvidenceGraph onClose={() => setGraphOpen(false)} />}
    </>
  );
}

/** Day of the season (Oct 1 = 0), so 2025 and 2026 share one axis. */
const seasonDay = (date: string) => {
  const [, m, d] = date.split('-').map(Number);
  return (m === 10 ? 0 : 31) + d - 1;
};

function VhChart({ parcel, notes, active }: { parcel: Parcel; notes: Finding[]; active: number | null }) {
  const t = useT();
  const all = [...parcel.vh2025, ...parcel.vh2026].map((p) => p.db);
  const lo = Math.floor(Math.min(...all) - 1);
  const hi = Math.ceil(Math.max(...all) + 1);
  const x0 = 6;
  const x1 = 36;
  const X = (day: number) => 34 + ((day - x0) / (x1 - x0)) * 256;
  const Y = (db: number) => 14 + ((hi - db) / (hi - lo)) * 86;
  const line = (pts: VhPoint[]) => pts.map((p) => `${X(seasonDay(p.date))},${Y(p.db)}`).join(' ');
  const ticks = [hi, Math.round((hi + lo) / 2), lo];
  const wStart = X(seasonDay(WARNING.start));
  const wEnd = X(seasonDay(WARNING.end));
  const desc = parcel.vh2026.map((p) => `${md(p.date)} ${p.db.toFixed(1)}`).join('、');
  return (
    <svg viewBox="0 0 300 130" width="100%" role="img" aria-label={t(`VH 回波時序：2026 年 ${desc} dB；灰線為 2025 年同期`, `VH backscatter 2026: ${desc} dB; grey line is the same period in 2025`)}>
      <rect x={wStart} y={10} width={Math.max(4, wEnd - wStart)} height={92} fill="rgba(215,50,42,.12)" />
      <text x={wStart + 2} y={9} fontFamily="Noto Sans TC" fontSize="9" fill="#D7322A">
        {t('颱風警報', 'Typhoon warning')}
      </text>
      <g stroke="rgba(0,0,0,.12)" strokeWidth="1">
        {ticks.map((t) => (
          <line key={t} x1="30" y1={Y(t)} x2="295" y2={Y(t)} />
        ))}
      </g>
      <g fontFamily="IBM Plex Mono" fontSize="9" fill="#5F6672">
        {ticks.map((t) => (
          <text key={t} x="0" y={Y(t) + 3}>
            {String(t).replace('-', '−')}
          </text>
        ))}
        {['10-08', '10-15', '10-22', '10-29', '11-05'].map((d) => (
          <text key={d} x={X(seasonDay(`2026-${d}`)) - 12} y="118">
            {d.replace('-', '/')}
          </text>
        ))}
      </g>
      <polyline points={line(parcel.vh2025)} fill="none" stroke="#9AA0AA" strokeWidth="1.5" strokeDasharray="4 3" />
      <polyline points={line(parcel.vh2026)} fill="none" stroke="#0A0A0A" strokeWidth="2" />
      {parcel.vh2026.map((p) => (
        <rect key={p.date} x={X(seasonDay(p.date)) - 4} y={Y(p.db) - 4} width="8" height="8" fill="#FFFFFF" stroke="#0A0A0A" strokeWidth="1.5" />
      ))}
      {notes.map((n, i) => {
        const cx = X(seasonDay(n.date));
        const cy = Y(n.db);
        // The number sits off the dot, joined by a short leader: 2026 notes up and right, 2025
        // notes down and left, so notes on nearby dates do not collide; flipped where the chart ends.
        const right = n.year === 2026 ? cx < 250 : cx < 60;
        const up = n.year === 2026 ? cy > 40 : cy > 84;
        const lx = cx + (right ? 16 : -16);
        const ly = cy + (up ? -16 : 16);
        return (
          <g key={i} className={`finding-dot${active === i ? ' on' : ''}`}>
            <circle cx={cx} cy={cy} r={active === i ? 11 : 9} />
            <line x1={cx} y1={cy} x2={lx} y2={ly} />
            <circle className="badge" cx={lx} cy={ly} r="6" />
            <text x={lx} y={ly + 3} textAnchor="middle">
              {i + 1}
            </text>
          </g>
        );
      })}
      <g fontFamily="IBM Plex Mono" fontSize="9">
        <text x="236" y="128" fill="#0A0A0A">
          ━ 2026
        </text>
        <text x="196" y="128" fill="#9AA0AA">
          ┅ 2025
        </text>
      </g>
    </svg>
  );
}
