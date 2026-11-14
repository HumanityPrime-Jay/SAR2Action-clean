import React, { Suspense, lazy, useRef, useState } from 'react';
import type { GlobeHandle } from '../ui/Globe';
import { Icon } from '../ui/shared';
import type { ScreenKey, ScreenProps } from './types';

// MapLibre is large; load it only for the home globe.
const Globe = lazy(() => import('../ui/Globe'));

const ACTIONS: { to: ScreenKey; label: string; caption: string; icon: 'map' | 'compare' | 'assist' }[] = [
  { to: 'map', label: '受災地圖', caption: '找出受損田區', icon: 'map' },
  { to: 'compare', label: '田區比對', caption: '颱風前後雷達影像', icon: 'compare' },
  { to: 'assist', label: '補助助手', caption: '估算可申請補助', icon: 'assist' },
];

export function HomeScreen({ go }: ScreenProps) {
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
        <Globe ref={globeRef} borders={borders} />
      </Suspense>

      <div className="globe-intro">
        <span className="eyebrow">NISAR L-BAND · 薔琵颱風 · 雲林縣</span>
        <h1 className="h1">
          颱風過後，
          <br />
          哪幾塊稻田倒了？
        </h1>
        <p className="body">從太空比對颱風前後的雷達影像，找出受損田區、整理證據、估算補助。</p>
      </div>

      <div className="globe-tools">
        <label className="globe-toggle">
          <input type="checkbox" checked={borders} onChange={(e) => setBorders(e.target.checked)} />
          海岸線
        </label>
      </div>

      <p className="globe-hint mono">拖曳旋轉 · 滾輪縮放</p>

      <nav className="globe-actions" aria-label="開始使用">
        {ACTIONS.map((a, i) => (
          <button key={a.to} className={`globe-action box${i === 0 ? ' primary' : ''}`} onClick={() => open(a.to)} disabled={flying}>
            <span className="no mono">{String(i + 1).padStart(2, '0')}</span>
            <Icon name={a.icon} size={22} />
            <span className="txt">
              <b>{a.label}</b>
              <span>{a.caption}</span>
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
