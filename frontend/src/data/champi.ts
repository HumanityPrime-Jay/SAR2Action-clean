/**
 * Typhoon CHAMPI (薔琵) case, Taixi Township, Yunlin: the team's verified science outputs.
 *
 * Everything here is read from `public/studio/`, which `scripts/sync_studio_assets.py`
 * publishes from `data/exports/`. Radar values are descriptive observations: the team's QA
 * does not attribute any change to the typhoon, and crop types are unverified.
 */
import comparison from '../../public/studio/field_comparison.json';
import fieldsGeojson from '../../public/studio/fields.geojson?raw';
import nisarMap from '../../public/studio/nisar_map_manifest.json';
import official from '../../public/studio/official_loss_record.json';
import investigation from '../../public/studio/recorded_investigation.json';
import type { Lang, Text } from '../i18n';

export type LngLat = [number, number];

export interface VhPoint {
  /** Taiwan local date, YYYY-MM-DD. */
  date: string;
  db: number;
}

export interface Parcel {
  id: string;
  town: Text;
  areaHa: number;
  /** Outer ring of the official farmland polygon (農田坵塊圖). */
  ring: LngLat[];
  vh2025: VhPoint[];
  vh2026: VhPoint[];
  /** Sentinel-1 VH median change, dB: pre-warning (10/11) → post-warning (11/04). */
  preToPost: number;
  /** Pre-warning (10/11) → inside the warning window (10/23). */
  preToWarning: number;
  /** 2026 minus 2025 at the post-warning matched date. */
  vsLastYear: number;
}

export type Trend = 'up' | 'down';
export const trendOf = (p: Parcel): Trend => (p.preToPost >= 0 ? 'up' : 'down');
export const TREND_LABEL: Record<Trend, Text> = { up: { zh: 'VH 上升', en: 'VH up' }, down: { zh: 'VH 下降', en: 'VH down' } };
export const TREND_COLOR: Record<Trend, string> = { up: '#4D8DFF', down: '#F28C3B' };

interface FeatureLike {
  properties: { field_id: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: unknown };
}

const rings = new Map<string, LngLat[]>(
  (JSON.parse(fieldsGeojson).features as FeatureLike[]).map((f) => {
    const c = f.geometry.coordinates as LngLat[][] | LngLat[][][];
    return [f.properties.field_id, (f.geometry.type === 'Polygon' ? (c as LngLat[][])[0] : (c as LngLat[][][])[0][0]) as LngLat[]];
  }),
);

const series = (obs: { acquisition_taiwan: string; vh_median_db: number }[]): VhPoint[] =>
  obs.map((o) => ({ date: o.acquisition_taiwan.slice(0, 10), db: o.vh_median_db }));

export const PARCELS: Parcel[] = comparison.fields.map((f) => {
  const pairs = f.matched_date_pairs;
  return {
    id: f.field_id,
    town: { zh: '台西鄉', en: 'Taixi' },
    areaHa: Math.round(f.field_area_m2 / 1000) / 10,
    ring: rings.get(f.field_id) ?? [],
    vh2025: series(f.observations['2025']),
    vh2026: series(f.observations['2026']),
    preToPost: f['2026_pre_to_post_warning'].median_difference_db,
    preToWarning: f['2026_pre_to_warning_window'].median_difference_db,
    vsLastYear: pairs[pairs.length - 1]['2026_minus_2025_db'],
  };
});

export const parcelById = (id: string) => PARCELS.find((p) => p.id === id) ?? PARCELS[0];

/** CWA land-warning window (not a field impact time). */
export const WARNING = {
  start: comparison.event_reference.start_taiwan.slice(0, 10),
  end: comparison.event_reference.end_taiwan.slice(0, 10),
};

export const CASE = {
  id: investigation.case_id,
  town: { zh: '雲林縣 台西鄉', en: 'Taixi, Yunlin' } as Text,
  provenance: investigation.provenance_status,
};

/** Team QA tests, with bilingual summaries of each recorded result. */
const TEST_TEXT: Record<string, { label: Text; result: Text }> = {
  genuine_post_event_observation: {
    label: { zh: '颱風後確實有 NISAR 觀測', en: 'A NISAR scene exists after the typhoon' },
    result: { zh: '10/28 的 NISAR 影像拍攝於 10/23–24 颱風之後。', en: 'The Oct 28 NISAR acquisition follows the Oct 23–24 event window.' },
  },
  cross_crid_radiometric_compatibility: {
    label: { zh: 'NISAR 前後兩期可直接比較強度', en: 'NISAR pre/post values are directly comparable' },
    result: {
      zh: '10/16（P05023 暫定版）與 10/28（P05036 驗證版）處理版本不同，尚未證實可直接相減。',
      en: 'Oct 16 (P05023, provisional) and Oct 28 (P05036, validated) use different processing; equivalence is not established.',
    },
  },
  official_loss_to_parcel_attribution: {
    label: { zh: '官方損失可對應到個別田區', en: 'Official losses map to individual fields' },
    result: { zh: '農業部只公布縣市層級損失，沒有田區層級資料。', en: 'The Ministry reports county-level losses only, with no parcel labels.' },
  },
  vh_event_bracketing: {
    label: { zh: 'Sentinel-1 VH 觀測涵蓋颱風前後', en: 'Sentinel-1 VH brackets the typhoon' },
    result: { zh: '同一顆衛星、同一軌道、同一處理方式，在颱風前後都有觀測。', en: 'Same platform, orbit and processing before and after the event.' },
  },
  vh_unique_event_signature_falsification: {
    label: { zh: 'VH 變化是颱風特有的訊號', en: 'The VH change is unique to the typhoon' },
    result: {
      zh: '2025 年同期也出現「先升後降」，無法證明是颱風特有；但也不能排除颱風影響。',
      en: 'A similar rise-then-fall occurs in 2025, so uniqueness fails; a typhoon effect is not ruled out.',
    },
  },
};

export interface QaTest {
  id: string;
  pass: boolean;
  label: Text;
  result: Text;
}

export const QA_TESTS: QaTest[] = investigation.hypothesis_tests.map((t) => ({
  id: t.test_id,
  pass: t.status === 'PASS',
  label: TEST_TEXT[t.test_id]?.label ?? { zh: t.test_id, en: t.test_id },
  result: TEST_TEXT[t.test_id]?.result ?? { zh: t.result, en: t.result },
}));

/** Two separate NISAR scenes over Taixi; each is stretched on its own, so not comparable in value. */
export const NISAR_TAIXI = {
  crossVersionVerified: nisarMap.cross_crid_radiometric_equivalence_verified,
  scenes: nisarMap.scenes.map((s) => ({
    period: s.period as 'PRE' | 'POST',
    date: s.acquisition_start_utc.slice(0, 10),
    crid: s.crid,
    maturity: s.product_maturity,
    corners: s.coordinates as LngLat[],
    image: {
      HH: `${import.meta.env.BASE_URL}studio/${s.layers.HH.image}`,
      HV: `${import.meta.env.BASE_URL}studio/${s.layers.HV.image}`,
    },
  })),
};

export const OFFICIAL_LOSS = {
  date: official.report_date_local,
  url: official.source_url,
  yunlinNtd: official.yunlin_county_ntd,
  taiwanNtd: official.taiwan_total_ntd,
};

/** Large NT$ amount: 1.58 億 / 157.7 million. */
export const bigNtd = (ntd: number, lang: Lang) => (lang === 'zh' ? `${(ntd / 1e8).toFixed(2)} 億` : `${(ntd / 1e6).toFixed(1)} million`);
