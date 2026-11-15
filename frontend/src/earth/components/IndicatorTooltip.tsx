import React, { useState } from 'react';
import { useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';

export interface IndicatorSpec {
  id: string;
  termZh: string;
  termEn: string;
  farmerZh: string;
  farmerEn: string;
  authorityZh: string;
  authorityEn: string;
  formula?: string;
  source?: string;
  limitationZh: string;
  limitationEn: string;
}

export const SCIENTIFIC_INDICATORS: Record<string, IndicatorSpec> = {
  vh_change: {
    id: 'vh_change',
    termZh: 'VH 交叉極化回波變化 (dB)',
    termEn: 'VH Cross-Pol Backscatter Change (dB)',
    farmerZh: '代表颱風前後農田表面的粗糙度或積水程度發生變化（例如 +7.55336 dB），但雷達訊號改變不等於作物一定受損。',
    farmerEn: 'Measures how much field surface roughness or standing water changed before vs. after the storm (+7.55336 dB), but a radar shift alone does not prove crop loss.',
    authorityZh: '哨兵一號 C 波段垂直發射、水平接收 (VH) 後向散射係數差分，對植被結構與地表雙重反射敏感。',
    authorityEn: 'Sentinel-1 C-band vertical-transmit horizontal-receive (VH) sigma-nought differential, sensitive to canopy geometry and surface double-bounce.',
    formula: 'Δσ⁰_VH (dB) = σ⁰_VH(post) − σ⁰_VH(pre)',
    source: 'OPERA_L2_RTC-S1_V1 (Sentinel-1A IW)',
    limitationZh: '受田間管理、灌溉水位與收割時程混淆，無法單獨確認颱風因果。',
    limitationEn: 'Confounded by irrigation water level and harvest timing; cannot establish typhoon causality alone.',
  },
  hh_hv: {
    id: 'hh_hv',
    termZh: 'HH / HV L-Band 觀測狀態',
    termEn: 'HH / HV L-Band Observation Status',
    farmerZh: 'NASA 新一代 NISAR 衛星的長波雷達資料，目前因前後期處理版本不同，系統自動阻止直接相減，避免算錯。',
    farmerEn: 'NASA NISAR L-band radar data; because pre- and post-storm processor versions differ, the system blocks direct subtraction to prevent false alarms.',
    authorityZh: 'NISAR L2 GCOV 雙極化共變異數矩陣 (HH/HV)。2026-10-16 為 P05023 (PROVISIONAL)，2026-10-28 為 P05036 (VALIDATED)。',
    authorityEn: 'NISAR L2 GCOV dual-pol covariance (HH/HV). 2026-10-16 is CRID P05023 (PROVISIONAL) vs. 2026-10-28 P05036 (VALIDATED).',
    formula: 'Cross-CRID Δ(P05023, P05036) → BLOCKED (UNVERIFIED)',
    source: 'NISAR_L2_GCOV_BETA_V1',
    limitationZh: '跨 CRID 輻射校正一致性尚未驗證，禁止產生未驗證差分圖。',
    limitationEn: 'Cross-CRID radiometric equivalence is unverified; uncalibrated differencing is strictly blocked.',
  },
  valid_pixels: {
    id: 'valid_pixels',
    termZh: '有效雷達像素與覆蓋率',
    termEn: 'Valid Pixels & Coverage Ratio',
    farmerZh: '這塊農田內共有 48 個有效的衛星雷達觀測格點（覆蓋率 100%），代表訊號完整，但仍需現場勘查才能確認災損。',
    farmerEn: '48 valid radar pixels (100% spatial coverage) were sampled inside this parcel—meaning the signal is complete, though on-site inspection is still required to confirm crop damage.',
    authorityZh: '地塊多邊形內通過輻射地形校正 (RTC) 遮罩與陰影/疊掩篩選之有效像素數與空間覆蓋比例。',
    authorityEn: 'Count and spatial ratio of RTC-valid pixels inside the parcel polygon after layover/shadow and nodata masking.',
    formula: 'Coverage = N_valid / N_total × 100% (48 / 48 = 100%)',
    source: 'OPERA_L2_RTC-S1_V1 Zonal QA',
    limitationZh: '48 個有效像素與 100% 覆蓋率僅代表空間取樣完整，不代表已確認農損或排除季節性干擾。',
    limitationEn: '48 valid pixels and 100% coverage verify spatial sampling completeness only—NOT confirmed crop damage.',
  },
  seasonal_ref: {
    id: 'seasonal_ref',
    termZh: '季節性基準比較 (2025 Baseline)',
    termEn: 'Seasonal Baseline Reference (2025)',
    farmerZh: '拿去年同一時期的農田雷達紀錄來比對，看看是不是每年秋收或翻耕都會出現類似變化。',
    farmerEn: 'Compares against last year’s radar record in the same season to check whether normal autumn harvesting or tilling causes a similar shift.',
    authorityZh: '2025 同農曆節氣／同月份之歷史 Sentinel-1 VH 基準差分，用於檢定季節性農務干擾假設 (H2)。',
    authorityEn: '2025 matched-phenology Sentinel-1 VH reference differential used to test the routine agricultural management hypothesis (H2).',
    formula: 'Δσ⁰_ref (2025) = +5.11 dB vs. Δσ⁰_event (2026) = +7.55336 dB',
    source: 'OPERA_L2_RTC-S1_V1 Multi-Year Archive',
    limitationZh: '2025 同季亦存在顯著正變化，顯示常規農務可能貢獻部分訊號。',
    limitationEn: 'Significant positive shift in 2025 seasonal reference indicates routine farming may contribute to the signal.',
  },
  crid_compat: {
    id: 'crid_compat',
    termZh: '跨感測器／跨版本相容性 (CRID Gate)',
    termEn: 'Cross-CRID & Sensor Compatibility Gate',
    farmerZh: '系統的「防呆保護機制」：不同衛星或不同處理版本的資料不會混在一起算，確保不會誤報災情。',
    farmerEn: 'Built-in safety gate that prevents mixing incompatible satellite sensors or processor versions.',
    authorityZh: 'Composite Release Identifier (CRID) 與波段幾何相容性檢核。僅允許同波段、同軌道方向與已驗證 CRID 進行定量距離計算。',
    authorityEn: 'Composite Release Identifier (CRID) and sensor geometry gate. Quantitative feature distance is restricted to matched band, orbit, and verified CRID.',
    formula: 'Comparable(A, B) ⟺ Sensor(A)=Sensor(B) ∧Pol(A)=Pol(B) ∧ CRID_Verified(A,B)',
    source: 'SAR2Action Epistemic Guardrail Engine',
    limitationZh: '不相容組合強制標記為 INCOMPATIBLE_BLOCKED。',
    limitationEn: 'Incompatible pairs are strictly gated as INCOMPATIBLE_BLOCKED.',
  },
};

export function IndicatorTooltip({ indicatorKey }: { indicatorKey: keyof typeof SCIENTIFIC_INDICATORS }) {
  const t = useT();
  const { userMode } = useEarthContext();
  const [open, setOpen] = useState(false);
  const spec = SCIENTIFIC_INDICATORS[indicatorKey];
  if (!spec) return null;

  return (
    <span className="eci-info-wrap">
      <button
        type="button"
        className="eci-info-btn"
        aria-label={`Info: ${t(spec.termZh, spec.termEn)}`}
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
      >
        ⓘ
      </button>
      {open && (
        <div className="eci-info-popover" role="tooltip" onClick={(e) => e.stopPropagation()}>
          <div className="eci-info-head">
            <strong>{t(spec.termZh, spec.termEn)}</strong>
            <span className="eci-badge">{userMode}</span>
          </div>
          <p className="eci-info-body">
            {userMode === 'FARMER' ? t(spec.farmerZh, spec.farmerEn) : t(spec.authorityZh, spec.authorityEn)}
          </p>
          {userMode === 'AUTHORITY' && spec.formula && (
            <div className="eci-info-formula">{spec.formula}</div>
          )}
          <div className="eci-info-meta">
            <span>{t('來源', 'Source')}: {spec.source}</span>
            <span className="warn-text">⚠ {t(spec.limitationZh, spec.limitationEn)}</span>
          </div>
        </div>
      )}
    </span>
  );
}
