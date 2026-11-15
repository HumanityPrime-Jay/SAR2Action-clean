import React, { useEffect, useState } from 'react';
import { useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type FingerprintCompareResponse, type SimilarChangeResponse, type SurfaceFingerprint } from '../api';

const REGIONS = ['YL-CAND-01', 'YL-CAND-02', 'YL-CAND-03', 'YL-CAND-04', 'YL-CAND-05', 'TW05-PARCEL-74', 'TW03-NISAR-AOI'];

export function FingerprintViewer() {
  const t = useT();
  const { selectedFieldId } = useEarthContext();
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

  return (
    <div className="eci-glass">
      <div className="eci-header">
        <div>
          <span className="eci-badge">SURFACE CHANGE FINGERPRINT</span>
          <h3 className="h3" style={{ margin: '6px 0 0', color: '#f8fafc' }}>
            {t('雷達變化指紋與相似性檢核', 'Radar Change Signature & Similarity')}
          </h3>
        </div>
      </div>

      {fp && (
        <div className="eci-card active">
          <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
            <strong>{fp.label}</strong>
            <span className="eci-badge">{fp.sensor} · {fp.product_version}</span>
          </div>
          <div className="eci-grid-2" style={{ marginTop: 8 }}>
            <div>
              <div style={{ fontSize: 11.5, color: '#94a3b8' }}>Temporal VH Diff</div>
              <div className="eci-metric">{fp.temporal_difference_db !== null && fp.temporal_difference_db !== undefined ? `${fp.temporal_difference_db > 0 ? '+' : ''}${fp.temporal_difference_db} dB` : 'NOT_AVAILABLE'}</div>
            </div>
            <div>
              <div style={{ fontSize: 11.5, color: '#94a3b8' }}>2025 Seasonal Ref</div>
              <div className="eci-metric warn">{fp.seasonal_reference_db !== null && fp.seasonal_reference_db !== undefined ? `${fp.seasonal_reference_db > 0 ? '+' : ''}${fp.seasonal_reference_db} dB` : 'NOT_AVAILABLE'}</div>
            </div>
            <div>
              <div style={{ fontSize: 11.5, color: '#94a3b8' }}>HH / HV Bands</div>
              <div style={{ fontSize: 13 }}>{typeof fp.hh_hv_signature === 'string' ? fp.hh_hv_signature : 'CROSS_CRID_UNVERIFIED'}</div>
            </div>
            <div>
              <div style={{ fontSize: 11.5, color: '#94a3b8' }}>Observations / QA</div>
              <div style={{ fontSize: 13 }}>{fp.observation_count} passes · {fp.qa_status}</div>
            </div>
          </div>
        </div>
      )}

      {/* Compare Two Regions */}
      <div className="eci-card">
        <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 8 }}>{t('比較兩個區域指紋', 'Compare Two Regions')}</div>
        <div className="eci-grid-2">
          <select className="eci-input" aria-label="Source region" value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
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
        <button className="eci-btn" style={{ marginTop: 8 }} onClick={runCompare}>
          {t('執行指紋比對', 'Compare Fingerprints')}
        </button>

        {cmp && (
          <div style={{ marginTop: 10, fontSize: 12.5 }}>
            <span className={`eci-badge ${cmp.comparable ? '' : 'warn'}`}>
              {cmp.comparable ? 'COMPATIBLE' : 'INCOMPATIBLE_BLOCKED'}
            </span>
            {cmp.comparable ? (
              <div style={{ marginTop: 6 }}>
                Feature Distance: <b>{cmp.normalized_feature_distance}</b> · Temporal Similarity: <b>{cmp.temporal_pattern_similarity}</b>
              </div>
            ) : (
              <div style={{ marginTop: 6, color: '#fdba74' }}>{cmp.incompatibility_reasons.join(' ')}</div>
            )}
            <div style={{ marginTop: 4, color: '#94a3b8' }}>{cmp.scientific_caution}</div>
          </div>
        )}
      </div>

      {/* Similar Earth Changes */}
      {similar && (
        <div className="eci-card">
          <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 6 }}>{t('尋找相似地表變化 (確定性特徵距離)', 'Find Similar Earth Changes')}</div>
          {similar.candidates.slice(0, 4).map((c) => (
            <div key={c.region_id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', borderBottom: '1px solid rgba(148,163,184,0.12)' }}>
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
