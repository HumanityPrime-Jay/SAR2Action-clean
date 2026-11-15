import React, { useEffect, useState } from 'react';
import { useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type LensMode, type RealityLensResponse } from '../api';

const LENSES: { id: LensMode; labelZh: string; labelEn: string }[] = [
  { id: 'OBSERVED', labelZh: 'A · 實測觀測', labelEn: 'A · OBSERVED' },
  { id: 'HYPOTHESES', labelZh: 'B · 競爭假設', labelEn: 'B · HYPOTHESES' },
  { id: 'UNKNOWN', labelZh: 'C · 未知與限制', labelEn: 'C · UNKNOWN' },
  { id: 'NEXT_EVIDENCE', labelZh: 'D · 下一步證據', labelEn: 'D · NEXT EVIDENCE' },
];

export function RealityLensSelector() {
  const t = useT();
  const { eventId, selectedFieldId, setSelectedFieldId, selectedLens, setSelectedLens } = useEarthContext();
  const [data, setData] = useState<RealityLensResponse | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    earthApi
      .getLens(eventId, selectedLens, selectedFieldId, ctrl.signal)
      .then(setData)
      .catch(() => {});
    return () => ctrl.abort();
  }, [eventId, selectedLens, selectedFieldId]);

  return (
    <div className="eci-glass">
      <div className="eci-header">
        <div>
          <span className="eci-badge">REALITY LENS · NO FAKE CONFIDENCE</span>
          <h3 className="h3" style={{ margin: '6px 0 0', color: '#f8fafc' }}>
            {data?.title || t('科學實相透鏡', 'Reality Lens System')}
          </h3>
        </div>
      </div>

      <div className="eci-tabs" role="tablist" aria-label="Reality Lens Selector">
        {LENSES.map((l) => (
          <button
            key={l.id}
            role="tab"
            aria-selected={selectedLens === l.id}
            className="eci-tab"
            onClick={() => setSelectedLens(l.id)}
          >
            {t(l.labelZh, l.labelEn)}
          </button>
        ))}
      </div>

      {data && (
        <>
          <p style={{ fontSize: 13, color: '#cbd5e1', marginTop: 0 }}>{data.subtitle}</p>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
            {(data.legend_items || []).map((item) => (
              <span key={item.label} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                <span style={{ width: 10, height: 10, borderRadius: 99, background: item.color, display: 'inline-block' }} />
                {item.label}
              </span>
            ))}
          </div>

          {(data.features || []).map((feat) => (
            <div
              key={feat.feature_id}
              className={`eci-card${feat.feature_id === selectedFieldId ? ' active' : ''}`}
              onClick={() => feat.scale === 'PARCEL' && setSelectedFieldId(feat.feature_id)}
              style={{ cursor: feat.scale === 'PARCEL' ? 'pointer' : 'default' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <strong>{feat.label}</strong>
                <span className="eci-badge muted">
                  {feat.scale} · {feat.status}
                </span>
              </div>
              <p style={{ fontSize: 12.5, color: '#cbd5e1', margin: '6px 0' }}>{feat.explanation}</p>
              <div style={{ fontSize: 11.5, color: '#94a3b8', fontFamily: 'var(--f-mono, monospace)' }}>
                {Object.entries(feat.metrics)
                  .slice(0, 4)
                  .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' / ') : String(v)}`)
                  .join(' · ')}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
