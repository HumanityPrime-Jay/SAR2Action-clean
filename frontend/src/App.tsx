import React, { useEffect, useRef, useState } from 'react';
import { EVENTS } from './data/events';
import { PARCELS } from './data/champi';
import { AssistScreen } from './screens/AssistScreen';
import { CompareScreen } from './screens/CompareScreen';
import { HomeScreen } from './screens/HomeScreen';
import { MapScreen } from './screens/MapScreen';
import type { ScreenKey, ScreenProps } from './screens/types';
import { Earth, Icon, SvgDefs } from './ui/shared';

const SCREENS: { key: ScreenKey; label: string; drill?: boolean; Component: (p: ScreenProps) => React.ReactElement }[] = [
  { key: 'home', label: '首頁', Component: HomeScreen },
  { key: 'map', label: '受災地圖', Component: MapScreen },
  { key: 'compare', label: '田區比對', drill: true, Component: CompareScreen },
  { key: 'assist', label: '補助助手', drill: true, Component: AssistScreen },
];

function screenFromHash(): ScreenKey {
  const key = window.location.hash.replace('#', '');
  return SCREENS.some((s) => s.key === key) ? (key as ScreenKey) : 'home';
}

export function App() {
  const [screen, setScreen] = useState<ScreenKey>(screenFromHash);
  const [selectedId, setSelectedId] = useState(PARCELS[0].id);
  const [eventId, setEventId] = useState<string | null>(null);
  const event = EVENTS.find((e) => e.id === eventId);
  const sectionRefs = useRef<Partial<Record<ScreenKey, HTMLElement | null>>>({});
  const firstRender = useRef(true);

  // Move focus to the newly shown screen so keyboard and screen-reader users land in it.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    sectionRefs.current[screen]?.focus({ preventScroll: true });
  }, [screen]);

  useEffect(() => {
    const onHash = () => setScreen(screenFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const go = (key: ScreenKey) => {
    if (key === screen) return;
    window.location.hash = key === 'home' ? '' : key;
    setScreen(key);
  };

  return (
    <div className="stage">
      <SvgDefs />
      <header className="topbar">
        <a
          className="logo"
          href="#"
          aria-label="SAR2Action 首頁"
          onClick={(e) => {
            e.preventDefault();
            go('home');
          }}
        >
          <Earth size={32} />
          SAR2Action
        </a>
        <nav className="tabs" aria-label="主選單">
          {SCREENS.map((s) => (
            <button key={s.key} className="tab" aria-current={screen === s.key ? 'page' : undefined} onClick={() => go(s.key)}>
              <Icon name={s.key} />
              {s.label}
            </button>
          ))}
        </nav>
        <div className="spacer" />
        <div className="event">
          <span>EVENT</span>
          <b>{event ? `${event.name} · ${event.county}` : '尚未選擇'}</b>
        </div>
        <span className="stamp">PROTOTYPE · 研究原型</span>
      </header>

      <main className="screens">
        {SCREENS.map(({ key, label, drill, Component }) => (
          <section
            key={key}
            ref={(el) => (sectionRefs.current[key] = el)}
            className={`screen screen-${key}${drill ? ' drill' : ''}${screen === key ? ' active' : ''}`}
            aria-label={label}
            tabIndex={-1}
            // Hidden screens stay mounted for the page transition but must not be reachable.
            {...(screen !== key ? { inert: '' } : {})}
          >
            <Component selectedId={selectedId} onSelect={setSelectedId} go={go} eventId={eventId} onEvent={setEventId} />
          </section>
        ))}
      </main>

      <div className="demo-note">雷達資料為真實觀測 · 救助金額為示意試算</div>
    </div>
  );
}
