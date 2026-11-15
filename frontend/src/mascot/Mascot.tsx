import React, { createContext, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { type Text, useT } from '../i18n';
import type { ScreenKey } from '../screens/types';
import { MOOD_FRAMES, type Mood, SPRITE_H, SPRITE_W, composePose, spritePaths } from './sprites';

/** Moods the screens can ask for; the mascot falls back to idle on its own. */
export type MascotCue = 'think' | 'happy' | 'sorry';

const MascotContext = createContext<(cue: MascotCue) => void>(() => {});

/** Let a screen tell the mascot what is happening (agent thinking, answered, failed). */
export const useMascotCue = () => useContext(MascotContext);

const SCALE = 4;
const FRAME_MS = 320;
const STORAGE_KEY = 'sar2action.mascot';

/** How long a mood lasts before the pair goes back to idle; think waits for the next cue. */
const MOOD_MS: Partial<Record<Mood, number>> = { wave: 2200, happy: 2400, sorry: 6000 };

const TIPS: Record<ScreenKey, Text> = {
  home: {
    zh: '嗨！先選一場災害吧。',
    en: 'Hi! Pick a disaster to start.',
  },
  map: { zh: '選地區和災害。', en: 'Pick a region and a disaster.' },
  compare: { zh: '雷達有變化，不一定是受損。', en: "A radar change isn't always damage." },
  assist: { zh: '補助的事都可以問。', en: 'Ask us about relief.' },
};

const MAP_PICKED_TIP: Text = { zh: '點一塊田看看。', en: 'Click a field.' };

/**
 * Where the pair stands on wide screens: right-aligned on top of this element, so they never
 * cover its buttons. Screens not listed (and narrow screens) use the fixed corner from the CSS.
 */
const ANCHORS: Partial<Record<ScreenKey, string>> = {
  map: '.screen-map .panel-foot',
  assist: '.screen-assist .suggest',
};

/** Screens with no free corner (and every narrow screen): only the two heads peek from the bottom-left until clicked. */
const PEEK_SCREENS: ScreenKey[] = ['compare'];
const HEAD_ROWS = 10;
const WIDE = 1000;

const CUE_TEXT: Record<MascotCue, Text> = {
  think: { zh: '查一下', en: 'Checking' },
  happy: { zh: '找到了！', en: 'Found it!' },
  sorry: { zh: '抱歉，現在連不上。', en: "Sorry, can't connect." },
};

function prefersReducedMotion() {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function initialHidden() {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'hidden';
  } catch {
    return false;
  }
}

function Sprite({ mood, blink, rows = SPRITE_H, className = 'mascot-sprite' }: { mood: Mood; blink: boolean; rows?: number; className?: string }) {
  const frames = MOOD_FRAMES[mood];
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    setFrame(0);
    if (frames.length < 2 || prefersReducedMotion()) return;
    const id = window.setInterval(() => setFrame((f) => (f + 1) % frames.length), FRAME_MS);
    return () => clearInterval(id);
  }, [frames]);
  const paths = useMemo(() => spritePaths(composePose(frames[frame % frames.length], blink)), [frames, frame, blink]);
  return (
    <svg className={className} viewBox={`0 0 ${SPRITE_W} ${rows}`} width={SPRITE_W * SCALE} height={rows * SCALE} aria-hidden="true">
      {paths.map((p) => (
        <path key={p.fill} fill={p.fill} d={p.d} />
      ))}
    </svg>
  );
}

/** The farmer and the association officer in the corner: they react to the site and give a tip per screen. */
export function MascotProvider({
  screen,
  eventId,
  go,
  children,
}: {
  screen: ScreenKey;
  eventId: string | null;
  go: (s: ScreenKey) => void;
  children: React.ReactNode;
}) {
  const t = useT();
  const tip = screen === 'map' && eventId ? MAP_PICKED_TIP : TIPS[screen];
  const [mood, setMood] = useState<Mood>('wave');
  const [bubble, setBubble] = useState<Text | null>(tip);
  const [place, setPlace] = useState<React.CSSProperties | undefined>();
  const [hidden, setHidden] = useState(initialHidden);
  const [blink, setBlink] = useState(false);
  const [wide, setWide] = useState(() => window.innerWidth > WIDE);
  const peekScreen = !wide || PEEK_SCREENS.includes(screen);
  const moodTimer = useRef<number>();
  const bubbleTimer = useRef<number>();

  const show = (m: Mood, text: Text | null, bubbleMs = 7000) => {
    setMood(m);
    clearTimeout(moodTimer.current);
    const ms = MOOD_MS[m];
    if (ms) moodTimer.current = window.setTimeout(() => setMood('idle'), ms);
    setBubble(text);
    clearTimeout(bubbleTimer.current);
    if (text && bubbleMs) bubbleTimer.current = window.setTimeout(() => setBubble(null), bubbleMs);
  };

  // A new screen (or a newly picked event): wave and give that screen's tip; peeking screens stay quiet.
  useEffect(() => {
    show('wave', peekScreen ? null : tip);
  }, [tip, peekScreen]);

  // Stand on the screen's anchor; re-measure on resize, after the page slide, and once an event's map appears.
  useLayoutEffect(() => {
    const measure = () => {
      setWide(window.innerWidth > WIDE);
      const anchor = ANCHORS[screen] && document.querySelector<HTMLElement>(ANCHORS[screen]!);
      if (!anchor || window.innerWidth <= WIDE) return setPlace(undefined);
      const r = anchor.getBoundingClientRect();
      setPlace({ right: window.innerWidth - r.right + 12, bottom: window.innerHeight - r.top + 8 });
    };
    measure();
    const settle = window.setTimeout(measure, 350);
    window.addEventListener('resize', measure);
    return () => {
      clearTimeout(settle);
      window.removeEventListener('resize', measure);
    };
  }, [screen, eventId]);

  useEffect(
    () => () => {
      clearTimeout(moodTimer.current);
      clearTimeout(bubbleTimer.current);
    },
    [],
  );

  // Blink now and then.
  useEffect(() => {
    if (prefersReducedMotion()) return;
    let off: number;
    const id = window.setInterval(() => {
      setBlink(true);
      off = window.setTimeout(() => setBlink(false), 140);
    }, 3600);
    return () => {
      clearInterval(id);
      clearTimeout(off);
    };
  }, []);

  const cue = useMemo(
    // `show` only touches state setters and refs, so the cue never needs to change.
    () => (c: MascotCue) => show(c, CUE_TEXT[c], c === 'think' ? 0 : c === 'sorry' ? 9000 : 6000),
    [],
  );

  const setHiddenSaved = (h: boolean) => {
    setHidden(h);
    try {
      localStorage.setItem(STORAGE_KEY, h ? 'hidden' : 'shown');
    } catch {
      // Not remembering is fine.
    }
  };

  return (
    <MascotContext.Provider value={cue}>
      {children}
      {hidden ? (
        <button className="mascot-restore" onClick={() => setHiddenSaved(false)}>
          {t('顯示小幫手', 'Show helpers')}
        </button>
      ) : peekScreen && !bubble ? (
        <button className="mascot-peek" aria-label={t('小幫手：點一下看提示', 'Helpers: click for a tip')} onClick={() => show('wave', tip)}>
          <Sprite mood={mood} blink={blink} rows={HEAD_ROWS} className="mascot-heads" />
        </button>
      ) : (
        <div className={`mascot mascot-${mood} mascot-on-${screen}${place ? ' anchored' : ''}${peekScreen ? ' at-left' : ''}`} style={place}>
          {bubble && (
            <div className="mascot-bubble">
              <p>{t(bubble)}</p>
              {screen !== 'assist' && (
                <button className="link" onClick={() => go('assist')}>
                  {t('問補助助手 →', 'Ask the relief assistant →')}
                </button>
              )}
            </div>
          )}
          <div className="mascot-figure">
            <button
              className="mascot-body"
              aria-label={t('小幫手：農民和農會人員，點一下看提示', 'Helpers: a farmer and an association officer. Click for a tip')}
              aria-expanded={!!bubble}
              onClick={() => (bubble ? setBubble(null) : show('wave', tip))}
            >
              <Sprite mood={mood} blink={blink} />
            </button>
            <button className="mascot-hide" aria-label={t('隱藏小幫手', 'Hide helpers')} onClick={() => setHiddenSaved(true)}>
              ×
            </button>
          </div>
        </div>
      )}
    </MascotContext.Provider>
  );
}
