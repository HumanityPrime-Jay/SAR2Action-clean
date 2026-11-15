import React, { Suspense, lazy, useRef, useState } from 'react';
import { type Text, useLang, useT } from '../i18n';
import { TYPHOON_DAY } from '../data/champi';
import type { GlobeHandle, GlobeLayers } from '../ui/Globe';
import { Icon } from '../ui/shared';
import type { ScreenKey, ScreenProps } from './types';

// MapLibre is large; load it only for the home globe.
const Globe = lazy(() => import('../ui/Globe'));

const ACTIONS: { to: ScreenKey; label: Text; icon: 'map' | 'compare' | 'assist' }[] = [
  { to: 'map', label: { zh: '受災田區地圖', en: 'Damaged field map' }, icon: 'map' },
  { to: 'compare', label: { zh: '田區雷達影像比對', en: 'Field radar comparison' }, icon: 'compare' },
  { to: 'assist', label: { zh: '補助助手', en: 'Relief assistant' }, icon: 'assist' },
];

const DATA_TOGGLES: { key: keyof GlobeLayers; label: Text; source: string }[] = [
  { key: 'clouds', label: { zh: '颱風雲圖', en: 'Typhoon clouds' }, source: 'VIIRS' },
  { key: 'rain', label: { zh: '降雨強度', en: 'Rain rate' }, source: 'IMERG' },
  { key: 'borders', label: { zh: '海岸線', en: 'Coastlines' }, source: '' },
];

export function HomeScreen({ go }: ScreenProps) {
  const t = useT();
  const { lang } = useLang();
  const globeRef = useRef<GlobeHandle>(null);
  const [layers, setLayers] = useState<GlobeLayers>({ borders: true, clouds: true, rain: true, shield: false });
  const toggle = (key: keyof GlobeLayers) => (e: React.ChangeEvent<HTMLInputElement>) => setLayers((l) => ({ ...l, [key]: e.target.checked }));
  const [flying, setFlying] = useState(false);

  // Fly to Taiwan first, then open the chosen screen.
  const open = async (to: ScreenKey) => {
    if (flying) return;
    setFlying(true);
    try {
      await globeRef.current?.flyToTaiwan();
    } finally {
      setFlying(false);
      go(to);
    }
  };

  return (
    <div className="home-globe">
      <Suspense fallback={<div className="globe" />}>
        <Globe ref={globeRef} layers={layers} lang={lang} />
      </Suspense>

      <div className="globe-intro">
        <span className="eyebrow">{t('NISAR L-BAND · 薔琵颱風 · 雲林縣', 'NISAR L-BAND · TYPHOON CHAMPI · YUNLIN')}</span>
        <h1 className="h1">
          {t('颱風過後，', 'After the typhoon,')}
          <br />
          {t('哪幾塊田受到影響？', 'which fields were hit?')}
        </h1>
      </div>

      <div className="globe-tools" role="group" aria-label={t('地球圖層', 'Globe layers')}>
        <div className="eyebrow">{t(`圖層 · ${TYPHOON_DAY.replaceAll('-', '/')} 警報期間`, `LAYERS · ${TYPHOON_DAY} warning window`)}</div>
        {DATA_TOGGLES.map(({ key, label, source }) => (
          <label key={key} className="globe-toggle">
            <input type="checkbox" checked={layers[key]} onChange={toggle(key)} />
            {t(label)}
            {source && <span className="cap mono">{source}</span>}
          </label>
        ))}
        {layers.rain && (
          <div className="rain-key" aria-label={t('降雨強度：綠色小、紅色大', 'Rain rate: green light, red heavy')}>
            <i />
            <span className="cap">{t('小', 'Light')}</span>
            <span className="cap">{t('大', 'Heavy')}</span>
          </div>
        )}
        <div className="eyebrow globe-tools-sep">{t('效果', 'EFFECTS')}</div>
        <label className="globe-toggle">
          <input type="checkbox" checked={layers.shield} onChange={toggle('shield')} />
          {t('掃描光環', 'Scan ring')}
        </label>
      </div>

      <nav className="globe-actions" aria-label={t('開始使用', 'Get started')}>
        {ACTIONS.map((a, i) => (
          <button key={a.to} className={`globe-action box${i === 0 ? ' primary' : ''}`} onClick={() => open(a.to)} disabled={flying}>
            <span className="no mono">{String(i + 1).padStart(2, '0')}</span>
            <Icon name={a.icon} size={22} />
            <span className="txt">
              <b>{t(a.label)}</b>
            </span>
            <span className="arrow" aria-hidden="true">
              →
            </span>
          </button>
        ))}
      </nav>
    </div>
  );
}
