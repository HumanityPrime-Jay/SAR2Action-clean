import React, { useEffect, useState } from 'react';
import { useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type LensMode, type RealityLensResponse } from '../api';
import { IndicatorTooltip } from './IndicatorTooltip';

const LENSES: { id: LensMode; labelZh: string; labelEn: string; tone: string }[] = [
  { id: 'OBSERVED', labelZh: 'A · 實測觀測', labelEn: 'A · OBSERVED', tone: '#22d3ee' },
  { id: 'HYPOTHESES', labelZh: 'B · 競爭假設', labelEn: 'B · HYPOTHESES', tone: '#fb923c' },
  { id: 'UNKNOWN', labelZh: 'C · 未知與限制', labelEn: 'C · UNKNOWN', tone: '#94a3b8' },
  { id: 'NEXT_EVIDENCE', labelZh: 'D · 下一步證據', labelEn: 'D · NEXT EVIDENCE', tone: '#34d399' },
];

export function RealityLensSelector() {
  const t = useT();
  const { eventId, selectedFieldId, setSelectedFieldId, selectedLens, setSelectedLens, setActiveTab } = useEarthContext();
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
          <h3 className="h3" style={{ margin: '5px 0 0', fontSize: 16, color: '#f8fafc' }}>
            {data?.title || t('科學實相透鏡', 'Reality Lens System')}
            <IndicatorTooltip indicatorKey="vh_change" />
          </h3>
        </div>
        <span className="eci-badge ok">no_fake_confidence=true</span>
      </div>

      <div className="eci-tabs" role="tablist" aria-label="Reality Lens Selector">
        {LENSES.map((l) => (
          <button
            key={l.id}
            type="button"
            role="tab"
            aria-selected={selectedLens === l.id}
            className="eci-tab"
            onClick={() => setSelectedLens(l.id)}
          >
            <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: 99, background: l.tone, marginRight: 5 }} />
            {t(l.labelZh, l.labelEn)}
          </button>
        ))}
      </div>

      {data && (
        <>
          <p style={{ fontSize: 12.5, color: '#cbd5e1', marginTop: 0, marginBottom: 8 }}>{data.subtitle}</p>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 10, padding: '6px 10px', borderRadius: 8, background: 'rgba(15,23,42,0.65)' }}>
            {(data.legend_items || []).map((item) => (
              <span key={item.label} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5 }}>
                <span style={{ width: 9, height: 9, borderRadius: 99, background: item.color, display: 'inline-block' }} />
                {item.label}
              </span>
            ))}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(data.features || []).map((feat) => {
              const isSelected = feat.feature_id === selectedFieldId;
              const isUnknown = selectedLens === 'UNKNOWN';
              return (
                <div
                  key={feat.feature_id}
                  className={`eci-card${isSelected ? ' active' : ''}${isUnknown ? ' unknown-pattern' : ''}`}
                  onClick={() => feat.scale === 'PARCEL' && setSelectedFieldId(feat.feature_id)}
                  style={{ cursor: feat.scale === 'PARCEL' ? 'pointer' : 'default', marginBottom: 0 }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                    <strong style={{ fontSize: 13 }}>{feat.label}</strong>
                    <span className={`eci-badge ${selectedLens === 'HYPOTHESES' || selectedLens === 'UNKNOWN' ? 'warn' : ''}`}>
                      {feat.scale} · {feat.status}
                    </span>
                  </div>
                  <p style={{ fontSize: 12, color: '#e2e8f0', margin: '5px 0' }}>{feat.explanation}</p>
                  <div style={{ fontSize: 11, color: '#67e8f9', fontFamily: 'var(--f-mono, monospace)' }}>
                    {Object.entries(feat.metrics || {})
                      .slice(0, 4)
                      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' / ') : String(v)}`)
                      .join(' · ')}
                  </div>
                </div>
              );
            })}
          </div>

          {selectedLens === 'NEXT_EVIDENCE' && (
            <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
              <button type="button" className="eci-btn" onClick={() => setActiveTab('gaps')}>
                {t('前往證據缺口導航', 'Open Evidence Gap Navigator →')}
              </button>
              <button type="button" className="eci-btn secondary" onClick={() => setActiveTab('hypotheses')}>
                {t('前往假設競技場', 'Open Hypothesis Arena →')}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
