import React, { useEffect, useRef } from 'react';
import { CLOUD, DROP, GARLIC, PEANUT, RICE, outlined, propPaths } from './pixelProps';

/** Screen pixels per sprite cell. */
const SCALE = 5;
const GRAVITY = 1500; // px/s²
const BOUNCE = 0.25;
/** Gap between the floor and the bottom edge, so tilted sprites are not clipped. */
const FLOOR_GAP = 14;
const RAIN_EVERY = 0.45; // s
const DROPS = 12;

const SPRITES = { rice: outlined(RICE), garlic: outlined(GARLIC), peanut: outlined(PEANUT) };
type Kind = keyof typeof SPRITES;
const LINEUP: Kind[] = ['rice', 'garlic', 'peanut', 'rice', 'peanut', 'garlic', 'rice', 'peanut', 'rice', 'garlic', 'peanut', 'rice', 'garlic', 'peanut'];
/** Drop points as a share of the width; the crops fall in two heaps. */
const HEAPS = [0.28, 0.66];
const PATHS = Object.fromEntries(Object.entries(SPRITES).map(([k, g]) => [k, propPaths(g)])) as Record<Kind, ReturnType<typeof propPaths>>;
const CLOUD_GRID = outlined(CLOUD);
const DROP_GRID = outlined(DROP);

interface Body {
  kind: Kind;
  w: number;
  h: number;
  /** Collision radius: each sprite is treated as a circle. */
  r: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  /** Rotation in degrees, clockwise. */
  a: number;
  va: number;
  held: boolean;
  el: SVGGElement | null;
}

interface Drop {
  x: number;
  y: number;
  vy: number;
  live: boolean;
  el: SVGGElement | null;
}

const makeBodies = (): Body[] =>
  LINEUP.map((kind) => {
    const w = SPRITES[kind][0].length * SCALE;
    const h = SPRITES[kind].length * SCALE;
    return { kind, w, h, r: ((w + h) / 4) * 0.82, x: 0, y: 0, vx: 0, vy: 0, a: 0, va: 0, held: false, el: null };
  });

/** Fling speed limit, px/s, so a fast flick cannot tunnel through the walls. */
const MAX_FLING = 1800;
const clamp = (v: number) => Math.max(-MAX_FLING, Math.min(MAX_FLING, v));

const place = (el: SVGGElement | null, x: number, y: number, w: number, h: number, a = 0) =>
  el?.setAttribute('transform', `translate(${x} ${y}) rotate(${a}) translate(${-w / 2} ${-h / 2}) scale(${SCALE})`);

/**
 * Decorative pixel crops that tumble down, pile up and can be flung, with a drifting cloud whose
 * raindrops nudge them. Runs only while its screen is the active one; still under reduced motion.
 */
export function PixelPlayground() {
  const rootRef = useRef<HTMLDivElement>(null);
  const cloudRef = useRef<SVGGElement>(null);
  const bodies = useRef<Body[]>(makeBodies()).current;
  const drops = useRef<Drop[]>(Array.from({ length: DROPS }, () => ({ x: 0, y: 0, vy: 0, live: false, el: null }))).current;

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    let W = root.clientWidth;
    let H = root.clientHeight;
    const ro = new ResizeObserver(() => {
      W = root.clientWidth;
      H = root.clientHeight;
    });
    ro.observe(root);

    // Start in two columns above the top, so the first visit shows them falling into heaps.
    bodies.forEach((b, i) => {
      b.x = HEAPS[i % HEAPS.length] * W + (Math.random() - 0.5) * 60;
      b.y = -80 - i * 45;
      b.a = Math.random() * 360;
      b.va = (Math.random() - 0.5) * 400;
    });

    const cloudW = CLOUD_GRID[0].length * SCALE;
    const cloudH = CLOUD_GRID.length * SCALE;
    const dropW = DROP_GRID[0].length * SCALE;
    const dropH = DROP_GRID.length * SCALE;

    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      // A still pile: on the floor, tilted, no rain.
      bodies.forEach((b, i) => place(b.el, ((i + 0.5) / bodies.length) * W, H - FLOOR_GAP - b.r, b.w, b.h, ((i * 37) % 60) - 30));
      place(cloudRef.current, W * 0.3, 40, cloudW, cloudH);
      return () => ro.disconnect();
    }

    const screen = root.closest('.screen');
    const active = () => (!screen || screen.classList.contains('active')) && !document.hidden && root.offsetParent !== null;

    let nextRain = 1;
    const step = (dt: number, t: number) => {
      for (const b of bodies) {
        if (b.held) continue;
        b.vy += GRAVITY * dt;
        b.x += b.vx * dt;
        b.y += b.vy * dt;
        b.a += b.va * dt;
        b.va *= 0.995;
        const floor = H - FLOOR_GAP;
        if (b.y + b.r > floor) {
          b.y = floor - b.r;
          b.vy = b.vy > 60 ? -b.vy * BOUNCE : 0;
          // Rolling friction: spin follows the slide, and both die down.
          b.va += ((b.vx / b.r) * (180 / Math.PI) - b.va) * 0.3;
          b.vx *= 0.86;
          b.va *= 0.86;
        }
        // The playground clips its contents, so a crop thrown up bounces off its top edge.
        if (b.y - b.r < 0 && b.vy < 0) {
          b.y = b.r;
          b.vy = -b.vy * 0.4;
        }
        if (b.x - b.r < 0 || b.x + b.r > W) {
          b.x = Math.min(Math.max(b.x, b.r), W - b.r);
          b.vx = -b.vx * 0.4;
        }
      }
      for (let i = 0; i < bodies.length; i++)
        for (let j = i + 1; j < bodies.length; j++) {
          const p = bodies[i];
          const q = bodies[j];
          const dx = q.x - p.x;
          const dy = q.y - p.y;
          const d = Math.hypot(dx, dy) || 0.01;
          const overlap = p.r + q.r - d;
          if (overlap <= 0) continue;
          const nx = dx / d;
          const ny = dy / d;
          // A held body does not move; the other takes the whole correction.
          const sp = p.held ? 0 : q.held ? 1 : 0.5;
          const sq = 1 - sp;
          p.x -= nx * overlap * sp;
          p.y -= ny * overlap * sp;
          q.x += nx * overlap * sq;
          q.y += ny * overlap * sq;
          const rv = (q.vx - p.vx) * nx + (q.vy - p.vy) * ny;
          if (rv < 0) {
            const jn = -(1 + BOUNCE) * rv;
            p.vx -= jn * nx * sp;
            p.vy -= jn * ny * sp;
            q.vx += jn * nx * sq;
            q.vy += jn * ny * sq;
          }
          // Sliding past each other sets both spinning, the way a pile settles at angles;
          // friction then takes most of the slide away, so crops come to rest on each other.
          const tx = -ny;
          const ty = nx;
          const rt = (q.vx - p.vx) * tx + (q.vy - p.vy) * ty;
          p.va += rt * 0.4 * sp;
          q.va -= rt * 0.4 * sq;
          const jt = rt * 0.35;
          p.vx += jt * tx * sp;
          p.vy += jt * ty * sp;
          q.vx -= jt * tx * sq;
          q.vy -= jt * ty * sq;
          p.va *= 0.97;
          q.va *= 0.97;
        }

      const cx = W * 0.12 + W * 0.7 * (0.5 + 0.5 * Math.sin(t * 0.15));
      place(cloudRef.current, cx, 34, cloudW, cloudH);
      if (t >= nextRain) {
        nextRain = t + RAIN_EVERY;
        const d = drops.find((x) => !x.live);
        if (d) Object.assign(d, { x: cx + (Math.random() - 0.5) * cloudW * 0.7, y: 34 + cloudH / 2, vy: 120, live: true });
      }
      for (const d of drops) {
        if (!d.live) continue;
        d.vy += GRAVITY * 0.5 * dt;
        d.y += d.vy * dt;
        const hit = bodies.find((b) => Math.hypot(b.x - d.x, b.y - d.y) < b.r);
        if (hit && !hit.held) {
          hit.vy += 40;
          hit.vx += (hit.x - d.x) * 1.5;
          hit.va += (hit.x - d.x) * 3;
        }
        if (hit || d.y > H) d.live = false;
        d.el?.setAttribute('opacity', d.live ? '1' : '0');
        if (d.live) place(d.el, d.x, d.y, dropW, dropH);
      }
      for (const b of bodies) place(b.el, b.x, b.y, b.w, b.h, b.a);
    };

    let raf = 0;
    let last = performance.now();
    let t = 0;
    const tick = (now: number) => {
      const dt = Math.min(0.033, (now - last) / 1000);
      last = now;
      if (active()) {
        t += dt;
        step(dt / 2, t);
        step(dt / 2, t);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [bodies, drops]);

  // Drag and fling: the held body follows the pointer and leaves with its last velocity.
  const grab = (b: Body) => (e: React.PointerEvent<SVGGElement>) => {
    const root = rootRef.current;
    if (!root) return;
    const target = e.currentTarget;
    target.setPointerCapture(e.pointerId);
    b.held = true;
    let prev = { x: e.clientX, y: e.clientY, t: performance.now() };
    const move = (ev: PointerEvent) => {
      const box = root.getBoundingClientRect();
      const now = performance.now();
      const dt = Math.max(0.008, (now - prev.t) / 1000);
      b.vx = clamp((ev.clientX - prev.x) / dt);
      b.vy = clamp((ev.clientY - prev.y) / dt);
      b.x = ev.clientX - box.left;
      b.y = ev.clientY - box.top;
      prev = { x: ev.clientX, y: ev.clientY, t: now };
    };
    const up = () => {
      b.held = false;
      b.va = b.vx * 0.5;
      target.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    target.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  return (
    <div ref={rootRef} className="playground" aria-hidden="true">
      <svg width="100%" height="100%">
        <g ref={cloudRef} transform="translate(-999 -999)">
          {propPaths(CLOUD_GRID).map((p) => (
            <path key={p.fill} d={p.d} fill={p.fill} />
          ))}
        </g>
        {drops.map((d, i) => (
          <g
            key={`d${i}`}
            ref={(el) => {
              d.el = el;
            }}
            opacity="0"
          >
            {propPaths(DROP_GRID).map((p) => (
              <path key={p.fill} d={p.d} fill={p.fill} />
            ))}
          </g>
        ))}
        {bodies.map((b, i) => (
          <g
            key={`b${i}`}
            className="prop"
            ref={(el) => {
              b.el = el;
            }}
            transform="translate(-999 -999)"
            onPointerDown={grab(b)}
          >
            {PATHS[b.kind].map((p) => (
              <path key={p.fill} d={p.d} fill={p.fill} />
            ))}
          </g>
        ))}
      </svg>
    </div>
  );
}
