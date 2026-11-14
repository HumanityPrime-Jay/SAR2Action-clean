import React, { useRef, useState } from 'react';
import { type LngLat, NISAR_TAIXI, type Parcel, QA_TESTS, type VhPoint, WARNING, parcelById } from '../data/champi';
import { NISAR_SCENE } from '../data/nisar';
import { cropName } from '../data/farmer';
import { formatDb } from '../demo/fields';
import { type Lang, useLang, useT } from '../i18n';
import { Icon } from '../ui/shared';
import type { ScreenProps } from './types';

type Mode = 'side' | 'swipe';
type Pol = 'HH' | 'HV';
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
  const xy = projector(parcel.ring);
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
      <polygon points={parcel.ring.map((p) => xy(p).join(',')).join(' ')} fill="none" stroke="#7FA6FF" strokeWidth={2.5} strokeDasharray="7 5" vectorEffect="non-scaling-stroke" />
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

export function CompareScreen({ selectedId, go, farmer }: ScreenProps) {
  const t = useT();
  const { lang } = useLang();
  const [mode, setMode] = useState<Mode>('side');
  const [pol, setPol] = useState<Pol>('HH');
  const parcel = parcelById(selectedId);
  const [pre, post] = NISAR_TAIXI.scenes;

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
              {lang === 'zh' ? `雲林縣${parcel.town.zh}` : `${parcel.town.en}, Yunlin`} · {parcel.areaHa} {t('公頃', 'ha')} ·{' '}
              {farmer ? `${t('農民登記作物：', 'Farmer-reported crop: ')}${cropName(farmer, lang)}${t('（待驗證）', ' (unverified)')}` : t('作物未驗證', 'Crop unverified')}
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

        <p className="cap scene-src">
          {t(
            `真實 ${NISAR_SCENE.mission} 影像（Track ${NISAR_SCENE.track} Frame ${NISAR_SCENE.frame}），藍色虛線為農田坵塊圖的田區邊界。兩期各自調整亮度，且處理版本不同、尚未通過跨版本 QA，所以亮度不能直接相比，也不提供 NISAR 差異圖。`,
            `Real ${NISAR_SCENE.mission} imagery (Track ${NISAR_SCENE.track} Frame ${NISAR_SCENE.frame}); the dashed blue line is the official field boundary. Each scene has its own contrast stretch and a different processing version that has not passed cross-version QA, so brightness is not comparable and no NISAR difference image is shown.`,
          )}
        </p>

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
            <div className="cap">{t('需作物紀錄與現勘', 'Needs crop records and a site visit')}</div>
          </div>
        </div>
      </div>

      <aside className="panel">
        <div className="panel-head">
          <div className="eyebrow">Evidence QA</div>
          <h2 className="h3">{t('判讀檢核', 'Evidence checks')}</h2>
        </div>
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
        <div style={{ padding: '8px 20px 0' }}>
          <div className="eyebrow" style={{ marginBottom: 6 }}>
            {t('VH 回波時序 (dB)', 'VH backscatter (dB)')} · {parcel.id}
          </div>
          <VhChart parcel={parcel} />
        </div>
        <div style={{ flex: 1 }} />
        <div className="panel-foot">
          <button className="btn btn-primary btn-block" onClick={() => go('assist')}>
            {t('用此田區試算補助 →', 'Estimate relief for this field →')}
          </button>
          <button className="btn btn-line btn-block" onClick={() => window.print()}>
            {t('匯出證據報告 PDF', 'Export evidence report (PDF)')}
          </button>
        </div>
      </aside>
    </>
  );
}

/** Day of the season (Oct 1 = 0), so 2025 and 2026 share one axis. */
const seasonDay = (date: string) => {
  const [, m, d] = date.split('-').map(Number);
  return (m === 10 ? 0 : 31) + d - 1;
};

function VhChart({ parcel }: { parcel: Parcel }) {
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
