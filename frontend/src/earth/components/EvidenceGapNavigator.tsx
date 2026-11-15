import React, { useEffect, useState } from 'react';
import { useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type CatalogSearchResponse, type EvidenceGapResponse } from '../api';
import { IndicatorTooltip } from './IndicatorTooltip';

export function EvidenceGapNavigator() {
  const t = useT();
  const { eventId, selectedFieldId, pushActionFeedback } = useEarthContext();
  const [gapsData, setGapsData] = useState<EvidenceGapResponse | null>(null);
  const [productFamily, setProductFamily] = useState<'OPERA_RTC_S1' | 'NISAR_GCOV' | 'SENTINEL1_SLC'>('OPERA_RTC_S1');
  const [searching, setSearching] = useState(false);
  const [catalogResult, setCatalogResult] = useState<CatalogSearchResponse | null>(null);

  useEffect(() => {
    earthApi.getEvidenceGaps(eventId, selectedFieldId).then(setGapsData).catch(() => {});
  }, [eventId, selectedFieldId]);

  const runSearch = async () => {
    setSearching(true);
    pushActionFeedback([`Searching NASA CMR for ${productFamily}…`]);
    try {
      const res = await earthApi.searchCatalog({
        event_id: eventId,
        product_family: productFamily,
        live_network: true,
      });
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
          <h3 className="h3" style={{ margin: '5px 0 0', fontSize: 16, color: '#f8fafc' }}>
            {t('缺失證據導航與官方資料搜尋', 'Evidence Gap Navigator & Catalog Search')}
            <IndicatorTooltip indicatorKey="crid_compat" />
          </h3>
        </div>
        <span className="eci-badge warn">APPROVAL REQUIRED FOR DOWNLOAD</span>
      </div>

      {/* 4-Quadrant Epistemic Matrix */}
      <div className="eci-grid-2" style={{ marginBottom: 10 }}>
        <div className="eci-card" style={{ marginBottom: 0, padding: '8px 10px' }}>
          <div style={{ fontSize: 10.5, color: '#22d3ee', fontWeight: 700 }}>WHAT WE KNOW</div>
          <div style={{ fontSize: 11.5, color: '#e2e8f0', marginTop: 2 }}>
            {selectedFieldId} recorded +7.55336 dB VH shift (48 valid pixels, 100% coverage) during warning window.
          </div>
        </div>
        <div className="eci-card" style={{ marginBottom: 0, padding: '8px 10px' }}>
          <div style={{ fontSize: 10.5, color: '#fb923c', fontWeight: 700 }}>WHAT IS MISSING</div>
          <div style={{ fontSize: 11.5, color: '#e2e8f0', marginTop: 2 }}>
            On-site crop damage survey, verified 2026 crop label, and same-CRID NISAR L-band pair.
          </div>
        </div>
        <div className="eci-card" style={{ marginBottom: 0, padding: '8px 10px' }}>
          <div style={{ fontSize: 10.5, color: '#cbd5e1', fontWeight: 700 }}>WHY IT MATTERS</div>
          <div style={{ fontSize: 11.5, color: '#cbd5e1', marginTop: 2 }}>
            Separates physical typhoon crop loss from routine autumn harvest or aquaculture water shifts.
          </div>
        </div>
        <div className="eci-card" style={{ marginBottom: 0, padding: '8px 10px' }}>
          <div style={{ fontSize: 10.5, color: '#34d399', fontWeight: 700 }}>WHAT WE CAN DO NEXT</div>
          <div style={{ fontSize: 11.5, color: '#cbd5e1', marginTop: 2 }}>
            Stage 1: SEARCH / VALIDATE / PLAN / REQUEST_APPROVAL (no unapproved bulk SAR downloads).
          </div>
        </div>
      </div>

      {gapsData && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
          {(gapsData.gaps || []).map((g) => (
            <div key={g.gap_id} className="eci-card" style={{ marginBottom: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <strong style={{ fontSize: 12.5 }}>{g.title || g.gap_id}</strong>
                <span className={`eci-badge ${g.priority === 'HIGH' ? 'warn' : ''}`}>
                  {g.priority || 'HIGH'} · {g.recommended_action || 'SEARCH'}
                </span>
              </div>
              <p style={{ fontSize: 11.5, color: '#e2e8f0', margin: '4px 0' }}>
                <b>Why missing:</b> {g.why_missing || (g as unknown as Record<string, string>).description}
              </p>
              {g.research_value && (
                <p style={{ fontSize: 11, color: '#94a3b8', margin: 0 }}>
                  <b>Research value:</b> {g.research_value} · <b>Where:</b> {g.where_to_find}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Official NASA CMR Metadata-Only Search */}
      <div className="eci-card active" style={{ marginBottom: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600 }}>
            {t('查詢官方 NASA CMR 目錄 (僅中繼資料，不自動下載)', 'Search Official NASA CMR Catalog (Metadata Only)')}
          </span>
          <span className="eci-badge muted">download_permitted=false</span>
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
          <button type="button" className="eci-btn" disabled={searching} onClick={runSearch}>
            {searching ? t('搜尋中 (SEARCHING)…', 'SEARCHING…') : t('搜尋 NASA CMR', 'Search Catalog')}
          </button>
        </div>

        {catalogResult && (
          <div style={{ marginTop: 10, fontSize: 12 }}>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <span className={`eci-badge ${catalogResult.scenes?.length ? 'ok' : 'warn'}`}>
                {catalogResult.network_status}
              </span>
              <span className="eci-badge muted">APPROVAL REQUIRED</span>
              <span className="mono" style={{ fontSize: 11, color: '#94a3b8' }}>
                download_permitted={String(catalogResult.download_permitted)}
              </span>
            </div>
            <p style={{ margin: '6px 0', color: '#cbd5e1', fontSize: 11.5 }}>{catalogResult.compatibility_summary}</p>
            {(catalogResult.scenes || []).slice(0, 4).map((sc, idx) => (
              <div
                key={idx}
                style={{
                  fontSize: 11,
                  color: '#67e8f9',
                  padding: '4px 6px',
                  marginTop: 3,
                  borderRadius: 6,
                  background: 'rgba(15,23,42,0.75)',
                  fontFamily: 'var(--f-mono, monospace)',
                }}
              >
                {String(sc.scene_id || sc.granule_id)} · {String(sc.acquisition_start_utc || sc.datetime_utc || '')} · compatible={String(sc.compatible ?? true)}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
