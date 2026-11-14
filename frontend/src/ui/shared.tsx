import React from 'react';
import { type Parcel, TREND_LABEL, type Trend, trendOf } from '../data/champi';
import { formatDb } from '../demo/fields';

/** Hidden SVG defs shared by every screen: SAR speckle, damage hatch, cut-paper earth. */
export function SvgDefs() {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
      <defs>
        <filter id="speckle" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="1.6" numOctaves={2} seed={7} result="n" />
          <feColorMatrix type="saturate" values="0" in="n" />
          <feComponentTransfer>
            <feFuncA type="table" tableValues="0 .55" />
          </feComponentTransfer>
        </filter>
        <pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="7" height="7" fill="rgba(229,87,79,.25)" />
          <line x1="0" y1="0" x2="0" y2="7" stroke="#E5574F" strokeWidth="2" />
        </pattern>
        <symbol id="earth" viewBox="0 0 120 120">
          <circle cx="58" cy="58" r="56" fill="#FFFFFF" opacity=".18" />
          <circle cx="58" cy="58" r="52" fill="#000000" stroke="#FFFFFF" strokeWidth="2" />
          <circle cx="58" cy="58" r="46" fill="#0B3D91" />
          <path d="M30 40 C40 26 62 22 74 30 C80 36 70 44 62 42 C56 48 64 56 56 62 C48 66 40 58 34 60 C26 58 24 48 30 40Z" fill="#1F7A6A" stroke="#BFD0F5" strokeWidth="1.2" />
          <path d="M70 62 C80 58 92 64 94 74 C92 84 82 90 74 86 C72 78 64 72 70 62Z" fill="#1F7A6A" stroke="#BFD0F5" strokeWidth="1.2" />
          <path d="M82 46 L86 50 L84 56 L80 52Z" fill="#F2C14E" stroke="#BFD0F5" strokeWidth="1" />
          <path d="M22 70 C30 72 34 80 30 86" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" opacity=".8" />
        </symbol>
      </defs>
    </svg>
  );
}

export function Earth({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" aria-hidden="true">
      <use href="#earth" />
    </svg>
  );
}

type IconName = 'home' | 'map' | 'compare' | 'assist' | 'search' | 'download' | 'back' | 'send';

const ICON_PATHS: Record<IconName, React.ReactNode> = {
  home: <path d="M3.5 10.8 12 3.8l8.6 7v9.2h-5.6v-6h-6v6H3.5z" />,
  map: (
    <>
      <path d="M9 4.2 3.2 6.1v13.8L9 18l6 2 5.8-1.9V4.3L15 6.1z" />
      <path d="M9 4.2V18M15 6.1v13.8" />
    </>
  ),
  compare: (
    <>
      <rect x="3.2" y="4.2" width="17.6" height="15.6" />
      <path d="M12 4.2v15.6" />
    </>
  ),
  assist: (
    <>
      <path d="M4 5h16v11H9l-5 4z" />
      <path d="M8 9.5h8M8 12.5h5" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m20 20-4.2-4.2" />
    </>
  ),
  download: <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />,
  back: <path d="m15 6-6 6 6 6" />,
  send: <path d="M4 12 20 4l-6 16-3-7z" />,
};

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICON_PATHS[name]}
    </svg>
  );
}

export function TrendTag({ trend }: { trend: Trend }) {
  return (
    <span className={`dmg ${trend}`}>
      <i />
      {TREND_LABEL[trend]}
    </span>
  );
}

export function FieldRow({ parcel, selected, onSelect }: { parcel: Parcel; selected: boolean; onSelect: (id: string) => void }) {
  return (
    <div
      className="row"
      role="option"
      tabIndex={0}
      aria-selected={selected}
      onClick={() => onSelect(parcel.id)}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onSelect(parcel.id))}
    >
      <div className="grow">
        <div className="id">{parcel.id}</div>
        <div className="meta">
          {parcel.town} · {parcel.areaHa.toFixed(1)} 公頃 · {formatDb(parcel.preToPost)}
        </div>
      </div>
      <TrendTag trend={trendOf(parcel)} />
    </div>
  );
}
