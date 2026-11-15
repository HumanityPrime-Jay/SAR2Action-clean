import React, { useEffect, useRef, useState } from 'react';
import { EVENTS, eventShort } from './data/events';
import type { FarmerInfo } from './data/farmer';
import { LangProvider, type Text, useLang, useT } from './i18n';
import { PARCELS } from './data/champi';
import { AssistScreen } from './screens/AssistScreen';
import { CompareScreen } from './screens/CompareScreen';
import { HomeScreen } from './screens/HomeScreen';
import { MapScreen } from './screens/MapScreen';
import type { ScreenKey, ScreenProps } from './screens/types';
import { MascotProvider } from './mascot/Mascot';
import { deleteMyField, fetchMyFields, saveMyField } from './api/me';
import { Account, AuthProvider, useMe } from './ui/Account';
import { Earth, Icon, SvgDefs } from './ui/shared';

const SCREENS: { key: ScreenKey; label: Text; drill?: boolean; Component: (p: ScreenProps) => React.ReactElement }[] = [
  { key: 'home', label: { zh: '首頁', en: 'Home' }, Component: HomeScreen },
  { key: 'map', label: { zh: '受災地圖', en: 'Damage map' }, Component: MapScreen },
  { key: 'compare', label: { zh: '田區比對', en: 'Field compare' }, drill: true, Component: CompareScreen },
  { key: 'assist', label: { zh: '補助助手', en: 'Relief assistant' }, drill: true, Component: AssistScreen },
];

function screenFromHash(): ScreenKey {
  const key = window.location.hash.replace('#', '');
  return SCREENS.some((s) => s.key === key) ? (key as ScreenKey) : 'home';
}

export function App() {
  return (
    <LangProvider>
      <AuthProvider>
        <Shell />
      </AuthProvider>
    </LangProvider>
  );
}

function Shell() {
  const t = useT();
  const { lang, setLang } = useLang();
  const [farmer, setFarmer] = useState<FarmerInfo | null>(null);
  const [screen, setScreen] = useState<ScreenKey>(screenFromHash);
  const [selectedId, setSelectedId] = useState(PARCELS[0].id);
  const [eventId, setEventId] = useState<string | null>(null);
  const event = EVENTS.find((e) => e.id === eventId);
  const me = useMe();
  // Farmer cards a signed-in user saved, by event.
  const [saved, setSaved] = useState<Record<string, FarmerInfo>>({});

  useEffect(() => {
    setSaved({});
    if (!me) return;
    let live = true;
    fetchMyFields()
      .then((f) => live && setSaved(f))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [me]);

  // Signing in after a disaster is picked brings back the crop saved for it.
  useEffect(() => {
    if (eventId && !farmer && saved[eventId]) setFarmer(saved[eventId]);
  }, [saved]);

  const pickFarmer = (info: FarmerInfo | null, id: string) => {
    setFarmer(info);
    if (!me) return;
    setSaved(({ [id]: _, ...rest }) => (info ? { ...rest, [id]: info } : rest));
    (info ? saveMyField(id, info) : deleteMyField(id)).catch(() => {});
  };
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
          aria-label={t('SAR2Action 首頁', 'SAR2Action home')}
          onClick={(e) => {
            e.preventDefault();
            go('home');
          }}
        >
          <Earth size={32} />
          SAR2Action
        </a>
        <nav className="tabs" aria-label={t('主選單', 'Main menu')}>
          {SCREENS.map((s) => (
            <button key={s.key} className="tab" aria-current={screen === s.key ? 'page' : undefined} onClick={() => go(s.key)}>
              <Icon name={s.key} />
              {t(s.label)}
            </button>
          ))}
        </nav>
        <div className="spacer" />
        <div className="event">
          <span>EVENT</span>
          <b>{event ? eventShort(event, lang) : t('尚未選擇', 'Not selected')}</b>
        </div>
        <div className="lang" role="group" aria-label={t('語言', 'Language')}>
          {(['zh', 'en'] as const).map((l) => (
            <button key={l} lang={l === 'zh' ? 'zh-Hant' : 'en'} aria-pressed={lang === l} onClick={() => setLang(l)}>
              {l === 'zh' ? '中' : 'EN'}
            </button>
          ))}
        </div>
        <span className="stamp">{t('PROTOTYPE · 研究原型', 'PROTOTYPE')}</span>
        <Account />
      </header>

      <MascotProvider screen={screen} eventId={eventId} go={go}>
        <main className="screens">
          {SCREENS.map(({ key, label, drill, Component }) => (
            <section
              key={key}
              ref={(el) => (sectionRefs.current[key] = el)}
              className={`screen screen-${key}${drill ? ' drill' : ''}${screen === key ? ' active' : ''}`}
              aria-label={t(label)}
              tabIndex={-1}
              // Hidden screens stay mounted for the page transition but must not be reachable.
              {...(screen !== key ? { inert: '' } : {})}
            >
              <Component selectedId={selectedId} onSelect={setSelectedId} go={go} eventId={eventId} onEvent={setEventId} farmer={farmer} onFarmer={pickFarmer} savedFarmers={saved} />
            </section>
          ))}
        </main>
      </MascotProvider>
    </div>
  );
}
