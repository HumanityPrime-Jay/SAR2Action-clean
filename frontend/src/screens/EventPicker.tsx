import React, { useRef, useState } from 'react';
import { EVENTS, REGIONS, type RegionKey, eventLabel } from '../data/events';
import { CROPS, type CropKey, type FarmerInfo } from '../data/farmer';
import { PARCELS } from '../data/champi';
import { useLang, useT } from '../i18n';

interface Props {
  initialId: string | null;
  initialFarmer: FarmerInfo | null;
  /** `farmer` is null when the user does not say they are a farmer. */
  onPick: (id: string, farmer: FarmerInfo | null) => void;
}

/** Event choice for the damage map (region → event), plus, optionally, the farmer's own field info. */
export function EventPicker({ initialId, initialFarmer, onPick }: Props) {
  const t = useT();
  const { lang } = useLang();
  const initial = EVENTS.find((e) => e.id === initialId);
  const [region, setRegion] = useState<RegionKey | ''>(initial?.region ?? '');
  const [eventId, setEventId] = useState(initial?.id ?? '');
  const [isFarmer, setIsFarmer] = useState(!!initialFarmer);
  const [cadastral, setCadastral] = useState(initialFarmer?.cadastral ?? '');
  const [crop, setCrop] = useState<CropKey | ''>(initialFarmer?.crop ?? '');
  const [cropOther, setCropOther] = useState(initialFarmer?.cropOther ?? '');
  const [showErrors, setShowErrors] = useState(false);
  const cropRef = useRef<HTMLSelectElement>(null);
  const otherRef = useRef<HTMLInputElement>(null);
  const options = EVENTS.filter((e) => e.region === region);
  const chosen = EVENTS.find((e) => e.id === eventId);

  // The crop is only required once the user says they are a farmer.
  const cropMissing = isFarmer && !crop;
  const otherMissing = isFarmer && crop === 'other' && !cropOther.trim();

  const submit = () => {
    if (!chosen) return;
    if (cropMissing || otherMissing) {
      setShowErrors(true);
      (cropMissing ? cropRef : otherRef).current?.focus();
      return;
    }
    onPick(chosen.id, isFarmer ? { cadastral: cadastral.trim(), crop: crop as CropKey, cropOther: cropOther.trim() } : null);
  };

  return (
    <div className="picker">
      <div className="picker-head">
        <span className="eyebrow">{t('STEP 1 · 選擇災害事件', 'STEP 1 · CHOOSE AN EVENT')}</span>
        <h1 className="h1">{t('要查看哪一次災害？', 'Which disaster do you want to look at?')}</h1>
      </div>

      <div className="picker-steps">
        <label className="picker-field box">
          <span className="no mono">01</span>
          <span className="lbl">{t('地區', 'Region')}</span>
          <select
            value={region}
            onChange={(e) => {
              setRegion(e.target.value as RegionKey);
              setEventId('');
            }}
          >
            <option value="" disabled>
              {t('請選擇地區', 'Choose a region')}
            </option>
            {REGIONS.map((r) => (
              <option key={r.key} value={r.key}>
                {t(`${r.label.zh}（${r.counties.zh}）`, `${r.label.en} (${r.counties.en})`)}
              </option>
            ))}
          </select>
        </label>

        <span className="picker-arrow" aria-hidden="true">
          →
        </span>

        <label className={`picker-field box${region ? '' : ' off'}`}>
          <span className="no mono">02</span>
          <span className="lbl">{t('災害事件', 'Disaster event')}</span>
          <select value={eventId} disabled={!region || !options.length} onChange={(e) => setEventId(e.target.value)}>
            <option value="" disabled>
              {!region
                ? t('請先選擇地區', 'Choose a region first')
                : options.length
                  ? t('請選擇事件', 'Choose an event')
                  : t('此地區尚無事件', 'No events yet')}
            </option>
            {options.map((e) => (
              <option key={e.id} value={e.id}>
                {eventLabel(e, lang)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {chosen && (
        <>
          <div className="picker-summary">
            <div>
              <span className="eyebrow">
                {t(chosen.kind)} · {chosen.intlName}
              </span>
              <b>{lang === 'zh' ? `${chosen.county.zh} ${chosen.name.zh}` : `${chosen.name.en}, ${chosen.county.en}`}</b>
              <span className="cap">
                {chosen.period}
                {chosen.hasImagery && ` · ${t(chosen.town)} · ${PARCELS.length} ${t('塊田', 'fields')}`}
              </span>
            </div>
          </div>

          <fieldset className={`farmer-card${isFarmer ? ' open' : ''}`}>
            <legend className="sr-only">{t('我是農民', 'I am a farmer')}</legend>
            <label className="farmer-toggle">
              <input
                type="checkbox"
                checked={isFarmer}
                onChange={(e) => {
                  setIsFarmer(e.target.checked);
                  setShowErrors(false);
                }}
              />
              <span className="h3">{t('我是農民', 'I am a farmer')}</span>
              <span className="opt">{t('選填', 'Optional')}</span>
            </label>
            {isFarmer && (
              <div className="farmer-fields">
                <label className="farmer-field">
                  <span className="lbl">
                    {t('土地地籍', 'Land parcel no.')} <span className="opt">{t('選填', 'Optional')}</span>
                  </span>
                  <input
                    value={cadastral}
                    onChange={(e) => setCadastral(e.target.value)}
                    placeholder={t('例：台西鄉 海口段 0123 地號', 'e.g. Taixi, Haikou section, lot 0123')}
                    autoComplete="off"
                  />
                </label>
                <div className="farmer-field">
                  <label htmlFor="farmer-crop" className="lbl">
                    {t('這塊田種的作物', 'Crop on this field')} <span className="req">{t('必填', 'Required')}</span>
                  </label>
                  <select
                    id="farmer-crop"
                    ref={cropRef}
                    value={crop}
                    required
                    aria-invalid={showErrors && cropMissing}
                    aria-describedby={showErrors && cropMissing ? 'crop-error' : undefined}
                    onChange={(e) => setCrop(e.target.value as CropKey)}
                  >
                    <option value="" disabled>
                      {t('請選擇作物', 'Choose a crop')}
                    </option>
                    {CROPS.map((c) => (
                      <option key={c.key} value={c.key}>
                        {t(c.label)}
                      </option>
                    ))}
                  </select>
                  {crop === 'other' && (
                    <input
                      ref={otherRef}
                      value={cropOther}
                      onChange={(e) => setCropOther(e.target.value)}
                      placeholder={t('請填寫作物名稱', 'Name of the crop')}
                      aria-label={t('其他作物名稱', 'Other crop name')}
                      aria-invalid={showErrors && otherMissing}
                      aria-describedby={showErrors && otherMissing ? 'crop-error' : undefined}
                      required
                    />
                  )}
                  {showErrors && (cropMissing || otherMissing) && (
                    <span id="crop-error" className="error" role="alert">
                      {cropMissing
                        ? t('請選擇作物，才能進入受災地圖。', 'Choose a crop to open the damage map.')
                        : t('請填寫作物名稱。', 'Enter the crop name.')}
                    </span>
                  )}
                </div>
              </div>
            )}
          </fieldset>

          <div className="picker-actions">
            <button className="btn btn-primary" onClick={submit}>
              {t('進入受災地圖 →', 'Open damage map →')}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
