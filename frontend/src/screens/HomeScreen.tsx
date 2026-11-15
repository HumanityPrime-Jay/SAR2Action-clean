import React, { Suspense, lazy, useRef, useState } from 'react';
import { type Text, useLang, useT } from '../i18n';
import type { GlobeHandle } from '../ui/Globe';
import { Icon } from '../ui/shared';
import type { ScreenKey, ScreenProps } from './types';

// MapLibre is large; load it only for the home globe.
const Globe = lazy(() => import('../ui/Globe'));

const ACTIONS: { to: ScreenKey; label: Text; icon: 'map' | 'compare' | 'assist' }[] = [
  { to: 'map', label: { zh: '受災田區地圖', en: 'Damaged field map' }, icon: 'map' },
  { to: 'compare', label: { zh: '田區雷達影像比對', en: 'Field radar comparison' }, icon: 'compare' },
  { to: 'assist', label: { zh: '補助助手', en: 'Relief assistant' }, icon: 'assist' },
];

export function HomeScreen({ go }: ScreenProps) {
  const t = useT();
  const { lang } = useLang();
  const globeRef = useRef<GlobeHandle>(null);
  const [borders, setBorders] = useState(true);
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
        <Globe ref={globeRef} borders={borders} lang={lang} />
      </Suspense>

      <div className="globe-intro">
        <span className="eyebrow">{t('NISAR L-BAND · 薔琵颱風 · 雲林縣', 'NISAR L-BAND · TYPHOON CHAMPI · YUNLIN')}</span>
        <h1 className="h1">
          {t('颱風過後，', 'After the typhoon,')}
          <br />
          {t('哪幾塊田受到影響？', 'which fields were hit?')}
        </h1>
      </div>

      <div className="globe-tools">
        <label className="globe-toggle">
          <input type="checkbox" checked={borders} onChange={(e) => setBorders(e.target.checked)} />
          {t('海岸線', 'Coastlines')}
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
