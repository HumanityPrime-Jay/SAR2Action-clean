import React, { useState } from 'react';
import { EVENTS, REGIONS, type RegionKey, eventLabel } from '../data/events';
import { PARCELS } from '../data/champi';
import { NISAR_SCENE } from '../data/nisar';

/** Two-step event choice for the damage map: region first, then an event in that region. */
export function EventPicker({ initialId, onPick }: { initialId: string | null; onPick: (id: string) => void }) {
  const initial = EVENTS.find((e) => e.id === initialId);
  const [region, setRegion] = useState<RegionKey | ''>(initial?.region ?? '');
  const [eventId, setEventId] = useState(initial?.id ?? '');
  const options = EVENTS.filter((e) => e.region === region);
  const chosen = EVENTS.find((e) => e.id === eventId);

  return (
    <div className="picker">
      <div className="picker-head">
        <span className="eyebrow">STEP 1 · 選擇災害事件</span>
        <h1 className="h1">要查看哪一次災害？</h1>
        <p className="body">先選地區，再選該地區的災害事件，就會開啟該事件的受災地圖。</p>
      </div>

      <div className="picker-steps">
        <label className="picker-field box">
          <span className="no mono">01</span>
          <span className="lbl">地區</span>
          <select
            value={region}
            onChange={(e) => {
              setRegion(e.target.value as RegionKey);
              setEventId('');
            }}
          >
            <option value="" disabled>
              請選擇地區
            </option>
            {REGIONS.map((r) => (
              <option key={r.key} value={r.key}>
                {r.label}（{r.counties}）
              </option>
            ))}
          </select>
        </label>

        <span className="picker-arrow" aria-hidden="true">
          →
        </span>

        <label className={`picker-field box${region ? '' : ' off'}`}>
          <span className="no mono">02</span>
          <span className="lbl">災害事件</span>
          <select value={eventId} disabled={!region || !options.length} onChange={(e) => setEventId(e.target.value)}>
            <option value="" disabled>
              {!region ? '請先選擇地區' : options.length ? '請選擇事件' : '此地區尚無事件'}
            </option>
            {options.map((e) => (
              <option key={e.id} value={e.id}>
                {eventLabel(e)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {region && !options.length && <p className="cap picker-empty">這個地區目前還沒有處理好的災害事件。</p>}

      {chosen && (
        <div className="picker-summary">
          <div>
            <span className="eyebrow">
              {chosen.kind} · {chosen.intlName}
            </span>
            <b>
              {chosen.county} {chosen.name}
            </b>
            <span className="cap">暴風圈影響台灣陸地：{chosen.period}</span>
            {chosen.hasImagery && (
              <span className="cap">
                NISAR 影像：{NISAR_SCENE.preDate}（颱風前）／{NISAR_SCENE.postDate}（颱風後） · Track {NISAR_SCENE.track}
              </span>
            )}
            {chosen.hasImagery && (
              <span className="cap">
                調查範圍：{chosen.town} · {PARCELS.length} 塊候選田區（農田坵塊圖）
              </span>
            )}
          </div>
          <button className="btn btn-primary" onClick={() => onPick(chosen.id)}>
            進入受災地圖 →
          </button>
        </div>
      )}
    </div>
  );
}
