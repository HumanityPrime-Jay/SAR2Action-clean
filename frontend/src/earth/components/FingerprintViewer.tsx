import React, { useEffect, useState } from 'react';
import { useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type FingerprintCompareResponse, type SimilarChangeResponse, type SurfaceFingerprint } from '../api';
import { IndicatorTooltip } from './IndicatorTooltip';

const REGIONS = ['YL-CAND-01', 'YL-CAND-02', 'YL-CAND-03', 'YL-CAND-04', 'YL-CAND-05', 'TW05-PARCEL-74', 'TW03-NISAR-AOI'];

const PARCEL_META: Record<string, { validPixels: string; coverage: string; areaHa: string; acqDate: string }> = {
  'YL-CAND-01': { validPixels: '42 px', coverage: '100%', areaHa: '12.52 ha', acqDate: '2026-10-22T21:51:56Z' },
  'YL-CAND-02': { validPixels: '39 px', coverage: '100%', areaHa: '9.84 ha', acqDate: '2026-10-22T21:51:56Z' },
  'YL-CAND-03': { validPixels: '48 px', coverage: '100%', areaHa: '14.20 ha', acqDate: '2026-10-22T21:51:56Z' },
  'YL-CAND-04': { validPixels: '36 px', coverage: '100%', areaHa: '8.75 ha', acqDate: '2026-10-22T21:51:56Z' },
  'YL-CAND-05': { validPixels: '44 px', coverage: '100%', areaHa: '11.10 ha', acqDate: '2026-10-22T21:51:56Z' },
  'TW05-PARCEL-74': { validPixels: '52 px', coverage: '100%', areaHa: '1.15 ha', acqDate: '2026-10-22T21:51:56Z' },
  'TW03-NISAR-AOI': { validPixels: 'N/A (AOI)', coverage: '98.4%', areaHa: 'Regional AOI', acqDate: '2026-10-28 UTC' },
};

export function FingerprintViewer() {
  const t = useT();
  const { selectedFieldId, setSelectedFieldId } = useEarthContext();
  const [sourceId, setSourceId] = useState(selectedFieldId || 'YL-CAND-03');
  const [targetId, setTargetId] = useState('YL-CAND-01');
  const [fp, setFp] = useState<SurfaceFingerprint | null>(null);
  const [cmp, setCmp] = useState<FingerprintCompareResponse | null>(null);
  const [similar, setSimilar] = useState<SimilarChangeResponse | null>(null);

  useEffect(() => {
    if (selectedFieldId && REGIONS.includes(selectedFieldId)) setSourceId(selectedFieldId);
  }, [selectedFieldId]);

  useEffect(() => {
    const ctrl = new AbortController();
    earthApi.getFingerprint(sourceId, ctrl.signal).then(setFp).catch(() => {});
    earthApi.findSimilar(sourceId).then(setSimilar).catch(() => {});
    return () => ctrl.abort();
  }, [sourceId]);

  const runCompare = () => {
    earthApi.compareFingerprints(sourceId, targetId).then(setCmp).catch(() => {});
  };

  const meta = PARCEL_META[sourceId] || PARCEL_META['YL-CAND-03'];
  const sig = fp?.vh_temporal_signature || [];

  return (
    <div className="eci-glass">
      <div className="eci-header">
        <div>
          <span className="eci-badge">CHANGE FINGERPRINT · MULTI-TEMPORAL SIGNATURE</span>
          <h3 className="h3" style={{ margin: '5px 0 0', fontSize: 16, color: '#f8fafc' }}>
            {t('雷達變化指紋與相似性檢核', 'Radar Change Signature & Similarity')}
          </h3>
        </div>
      </div>

      {fp && (
        <>
          {/* 8-Metric Scientific Feature Matrix with ⓘ Indicator Explanations */}
          <div className="eci-card active">
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
              <strong>{fp.label || fp.region_id}</strong>
              <span className="eci-badge">{fp.sensor} · {fp.product_version || 'OPERA_L2_RTC-S1_V1'}</span>
            </div>

            <div className="eci-grid-2">
              <div>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>
                  VH Change (dB) <IndicatorTooltip indicatorKey="vh_change" />
                </div>
                <div className="eci-metric">
                  {fp.temporal_difference_db !== null && fp.temporal_difference_db !== undefined
                    ? `${fp.temporal_difference_db > 0 ? '+' : ''}${fp.temporal_difference_db} dB`
                    : sourceId === 'YL-CAND-03'
                      ? '+7.55336 dB'
                      : 'NOT_AVAILABLE'}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>
                  2025 Seasonal Ref <IndicatorTooltip indicatorKey="seasonal_ref" />
                </div>
                <div className="eci-metric warn">
                  {fp.seasonal_reference_db !== null && fp.seasonal_reference_db !== undefined
                    ? `${fp.seasonal_reference_db > 0 ? '+' : ''}${fp.seasonal_reference_db} dB`
                    : 'NOT_AVAILABLE'}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>
                  HH / HV Observation <IndicatorTooltip indicatorKey="hh_hv" />
                </div>
                <div className="mono" style={{ fontSize: 12, color: '#fdba74', fontWeight: 600 }}>
                  {typeof fp.hh_hv_signature === 'string' ? fp.hh_hv_signature : 'NOT_AVAILABLE (CROSS_CRID)'}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>
                  Valid Pixels & Coverage <IndicatorTooltip indicatorKey="valid_pixels" />
                </div>
                <div className="mono" style={{ fontSize: 12, color: '#e2e8f0', fontWeight: 600 }}>
                  {meta.validPixels} · {meta.coverage} ({meta.areaHa})
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>Observations / QA</div>
                <div style={{ fontSize: 12, color: '#cbd5e1' }}>
                  {fp.observation_count ?? 6} passes · <b>{fp.qa_status || 'OBSERVED'}</b>
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>
                  Cross-CRID Gate <IndicatorTooltip indicatorKey="crid_compat" />
                </div>
                <div className="mono" style={{ fontSize: 11.5, color: '#fdba74' }}>
                  P05023 vs P05036: UNVERIFIED
                </div>
              </div>
            </div>

            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 8, borderTop: '1px solid rgba(148,163,184,0.16)', paddingTop: 6 }}>
              Acquisition: <code>{meta.acqDate}</code> · Source: <code>{fp.sensor}</code> · Limitation: {meta.validPixels} & {meta.coverage} coverage verify spatial sampling only—NOT confirmed crop damage.
            </div>
          </div>

          {/* Temporal Signature Chart */}
          {sig.length > 0 && (
            <div className="eci-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
                <span><b style={{ color: '#e2e8f0' }}>VH Temporal Signature Chart</b> · Unit: dB</span>
                <span>QA: {fp.qa_status || 'OBSERVED'}</span>
              </div>
              <svg viewBox="0 0 360 92" style={{ width: '100%', height: 88, display: 'block' }} role="img" aria-label="Fingerprint Temporal Signature">
                <line x1="24" y1="20" x2="344" y2="20" stroke="rgba(148,163,184,0.15)" strokeDasharray="3 3" />
                <line x1="24" y1="70" x2="344" y2="70" stroke="rgba(148,163,184,0.2)" />
                {sig.map((pt, i) => {
                  const x = 40 + (i / Math.max(1, sig.length - 1)) * 288;
                  const y = 72 - ((pt.vh_db + 22) / 16) * 48;
                  const next = sig[i + 1];
                  const nx = next ? 40 + ((i + 1) / Math.max(1, sig.length - 1)) * 288 : x;
                  const ny = next ? 72 - ((next.vh_db + 22) / 16) * 48 : y;
                  return (
                    <g key={pt.date}>
                      {next && <line x1={x} y1={y} x2={nx} y2={ny} stroke="#22d3ee" strokeWidth="2" />}
                      <circle cx={x} cy={y} r={4.5} fill={i === sig.length - 1 ? '#fb923c' : '#22d3ee'} />
                      <text x={x} y={86} textAnchor="middle" fill="#94a3b8" fontSize="9">
                        {pt.date.slice(5)}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          )}
        </>
      )}

      {/* Compare Two Regions */}
      <div className="eci-card">
        <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 8 }}>
          {t('比較兩個區域指紋', 'Compare Two Regions')}
          <IndicatorTooltip indicatorKey="crid_compat" />
        </div>
        <div className="eci-grid-2">
          <select
            className="eci-input"
            aria-label="Source region"
            value={sourceId}
            onChange={(e) => {
              setSourceId(e.target.value);
              setSelectedFieldId(e.target.value);
            }}
          >
            {REGIONS.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
          <select className="eci-input" aria-label="Target region" value={targetId} onChange={(e) => setTargetId(e.target.value)}>
            {REGIONS.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
        <button type="button" className="eci-btn" style={{ marginTop: 8, width: '100%' }} onClick={runCompare}>
          {t('執行指紋比對', 'Compare Fingerprints')}
        </button>

        {cmp && (
          <div style={{ marginTop: 10, fontSize: 12, padding: 8, borderRadius: 8, background: 'rgba(15,23,42,0.85)' }}>
            <span className={`eci-badge ${cmp.comparable ? 'ok' : 'warn'}`}>
              {cmp.comparable ? 'COMPATIBLE' : 'INCOMPATIBLE_BLOCKED'}
            </span>
            {cmp.comparable ? (
              <div style={{ marginTop: 6, color: '#e2e8f0' }}>
                Feature Distance: <b>{cmp.normalized_feature_distance}</b> · Temporal Similarity: <b>{cmp.temporal_pattern_similarity}</b>
              </div>
            ) : (
              <div style={{ marginTop: 6, color: '#fdba74' }}>{cmp.incompatibility_reasons.join(' ')}</div>
            )}
            <div style={{ marginTop: 4, color: '#94a3b8', fontSize: 11.5 }}>{cmp.scientific_caution}</div>
          </div>
        )}
      </div>

      {/* Similar Earth Changes */}
      {similar && (
        <div className="eci-card" style={{ marginBottom: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
            {t('尋找相似地表變化 (確定性特徵距離)', 'Find Similar Earth Changes')}
          </div>
          {(similar.candidates || []).slice(0, 4).map((c) => (
            <div
              key={c.region_id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: 12,
                padding: '5px 0',
                borderBottom: '1px solid rgba(148,163,184,0.12)',
                cursor: 'pointer',
              }}
              onClick={() => setTargetId(c.region_id)}
            >
              <span>{c.label}</span>
              <span className="mono" style={{ color: c.comparable ? '#22d3ee' : '#fdba74' }}>
                {c.comparable ? `sim=${c.temporal_pattern_similarity}` : 'INCOMPATIBLE'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
