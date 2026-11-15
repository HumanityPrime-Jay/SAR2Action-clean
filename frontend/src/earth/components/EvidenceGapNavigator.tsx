import React, { useEffect, useState } from 'react';
import { useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type CatalogSearchResponse, type EvidenceGapResponse } from '../api';

export function EvidenceGapNavigator() {
  const t = useT();
  const { eventId, selectedFieldId } = useEarthContext();
  const [gaps, setGaps] = useState<EvidenceGapResponse | null>(null);
  const [productFamily, setProductFamily] = useState<'OPERA_RTC_S1' | 'NISAR_GCOV' | 'SENTINEL1_SLC'>('OPERA_RTC_S1');
  const [searching, setSearching] = useState(false);
  const [catalogResult, setCatalogResult] = useState<CatalogSearchResponse | null>(null);

  useEffect(() => {
    earthApi.getEvidenceGaps(eventId, selectedFieldId).then(setGaps).catch(() => {});
  }, [eventId, selectedFieldId]);

  const runSearch = async () => {
    setSearching(true);
    try {
      const res = await earthApi.searchCatalog({ event_id: eventId, product_family: productFamily, live_network: true });
      setCatalogResult(res);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="eci-glass">
      <div className="eci-header">
        <div>
          <span className="eci-badge">EVIDENCE GAP NAVIGATOR · STAGE 1</span>
          <h3 className="h3" style={{ margin: '6px 0 0', color: '#f8fafc' }}>
            {t('缺失證據導航與 NASA 官方目錄搜尋', 'Evidence Gap Navigator & Catalog Search')}
          </h3>
        </div>
      </div>

      {gaps && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11.5, color: '#94a3b8', marginBottom: 8 }}>{gaps.stage_one_policy}</div>
          {gaps.gaps.map((g) => (
            <div key={g.gap_id} className="eci-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <strong>{g.title}</strong>
                <span className={`eci-badge ${g.priority === 'HIGH' ? 'warn' : ''}`}>
                  {g.priority} · {g.recommended_action}
                </span>
              </div>
              <p style={{ fontSize: 12, color: '#cbd5e1', margin: '6px 0 2px' }}>
                <b>Why missing:</b> {g.why_missing}
              </p>
              <p style={{ fontSize: 12, color: '#94a3b8', margin: '2px 0' }}>
                <b>Research value:</b> {g.research_value} · <b>Where:</b> {g.where_to_find}
              </p>
            </div>
          ))}
        </div>
      )}

      <div className="eci-card active">
        <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 8 }}>
          {t('查詢官方 NASA CMR 目錄 (僅中繼資料，不自動下載)', 'Search Official NASA CMR Catalog (Metadata Only)')}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <select
            className="eci-input"
            style={{ flex: 1 }}
            aria-label="Product family"
            value={productFamily}
            onChange={(e) => setProductFamily(e.target.value as 'OPERA_RTC_S1' | 'NISAR_GCOV' | 'SENTINEL1_SLC')}
          >
            <option value="OPERA_RTC_S1">OPERA_L2_RTC-S1_V1</option>
            <option value="NISAR_GCOV">NISAR_L2_GCOV_BETA_V1</option>
            <option value="SENTINEL1_SLC">SENTINEL-1A_SLC</option>
          </select>
          <button className="eci-btn" disabled={searching} onClick={runSearch}>
            {searching ? t('搜尋中…', 'Searching CMR…') : t('搜尋 NASA CMR', 'Search Catalog')}
          </button>
        </div>

        {catalogResult && (
          <div style={{ marginTop: 10, fontSize: 12.5 }}>
            <span className="eci-badge">{catalogResult.network_status}</span>
            <p style={{ margin: '6px 0', color: '#cbd5e1' }}>{catalogResult.compatibility_summary}</p>
            {catalogResult.scenes.slice(0, 4).map((sc, idx) => (
              <div key={idx} style={{ fontSize: 11.5, color: '#67e8f9', padding: '3px 0', fontFamily: 'var(--f-mono, monospace)' }}>
                {String(sc.scene_id)} · {String(sc.acquisition_start_utc)} · compatible={String(sc.compatible)}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
