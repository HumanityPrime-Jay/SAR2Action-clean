/**
 * Typhoon CHAMPI (薔琵) case, Taixi Township, Yunlin: the team's verified science outputs.
 *
 * Everything here is read from `public/studio/`, which `scripts/sync_studio_assets.py`
 * publishes from `data/exports/`. Radar values are descriptive observations: the team's QA
 * does not attribute any change to the typhoon, and crop types are unverified.
 */
import comparison from '../../public/studio/field_comparison.json';
import fieldsGeojson from '../../public/studio/fields.geojson?raw';
import townshipsGeojson from '../../public/studio/townships.geojson?raw';
import nisarMap from '../../public/studio/nisar_map_manifest.json';
import nisarAscending from '../../public/studio/nisar_ascending_manifest.json';
import official from '../../public/studio/official_loss_record.json';
import yunlinArea from '../../public/studio/yunlin_area_estimate.json';
import investigation from '../../public/studio/recorded_investigation.json';
import type { Lang, Text } from '../i18n';

export type LngLat = [number, number];
export type FieldGeometry =
  | { type: 'Polygon'; coordinates: LngLat[][] }
  | { type: 'MultiPolygon'; coordinates: LngLat[][][] };

export const polygonRings = (geometry: FieldGeometry) =>
  geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;

export function geometryPath(geometry: FieldGeometry, project: (point: LngLat) => LngLat) {
  return polygonRings(geometry).flatMap((polygon) =>
    polygon.map((ring) => `M${ring.map((point) => project(point).join(',')).join('L')}Z`),
  ).join(' ');
}

export interface VhPoint {
  /** Taiwan local date, YYYY-MM-DD. */
  date: string;
  db: number;
}

export interface Parcel {
  id: string;
  town: Text;
  areaHa: number;
  sourceAreaM2: number;
  areaSource: 'SOURCE_FARMLAND';
  /** Full polygon/multipolygon geometry (including interior rings) from official farmland boundaries. */
  geometry: FieldGeometry;
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
  geometry: FieldGeometry;
}

const geometries = new Map(
  (JSON.parse(fieldsGeojson).features as FeatureLike[]).map((f) => [f.properties.field_id, f.geometry]),
);

const series = (obs: { acquisition_taiwan: string; vh_median_db: number }[]): VhPoint[] =>
  obs.map((o) => ({ date: o.acquisition_taiwan.slice(0, 10), db: o.vh_median_db }));

export const PARCELS: Parcel[] = comparison.fields.map((f) => {
  const pairs = f.matched_date_pairs;
  const geometry = geometries.get(f.field_id);
  if (!geometry) throw new Error(`Missing geometry for ${f.field_id}`);
  return {
    id: f.field_id,
    town: { zh: '台西鄉', en: 'Taixi' },
    areaHa: f.field_area_m2 / 10_000,
    sourceAreaM2: f.field_area_m2,
    areaSource: 'SOURCE_FARMLAND',
    geometry,
    vh2025: series(f.observations['2025']),
    vh2026: series(f.observations['2026']),
    preToPost: f['2026_pre_to_post_warning'].median_difference_db,
    preToWarning: f['2026_pre_to_warning_window'].median_difference_db,
    vsLastYear: pairs[pairs.length - 1]['2026_minus_2025_db'],
  };
});

export const parcelById = (id: string) => PARCELS.find((p) => p.id === id);

/** CWA land-warning window (not a field impact time). */
export const WARNING = {
  start: comparison.event_reference.start_taiwan.slice(0, 10),
  end: comparison.event_reference.end_taiwan.slice(0, 10),
};

/** A day inside the warning window, for the home globe's daily NASA GIBS layers. */
export const TYPHOON_DAY = '2026-10-23';

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

/** The field the recorded investigation was run on; other fields share its scene-level tests. */
export const INVESTIGATED_FIELD = investigation.vh_timeseries.field_id;

/** Causes the investigation keeps open, with bilingual summaries of what was checked. */
const CAUSE_TEXT: Record<string, { label: Text; check: Text }> = {
  storm_disturbance: {
    label: { zh: '颱風擾動作物或地表', en: 'Typhoon disturbed crops or ground' },
    check: {
      zh: '2025 年同期也有相同起伏，無法證明是颱風造成，也無法排除。',
      en: 'The same rise and fall shows in 2025, so the typhoon is neither shown nor ruled out.',
    },
  },
  observation_processing: {
    label: { zh: '衛星處理版本不同', en: 'Different satellite processing' },
    check: { zh: 'NISAR 前後兩期版本不同，仍可能影響比較。', en: 'The two NISAR scenes use different versions, which may still skew the comparison.' },
  },
  harvesting: {
    label: { zh: '收割', en: 'Harvest' },
    check: { zh: '需要作物或收割紀錄。', en: 'Needs crop or harvest records.' },
  },
  field_preparation: {
    label: { zh: '整地', en: 'Field preparation' },
    check: { zh: '需要作物紀錄或現勘。', en: 'Needs crop records or a field visit.' },
  },
  moisture: {
    label: { zh: '土壤濕度變化', en: 'Soil moisture' },
    check: { zh: '需要現勘或其他觀測。', en: 'Needs a field visit or other observations.' },
  },
};

/** Recorded tests that bear on each cause (the same pairing as the Investigation Studio). */
const CAUSE_TESTS: Record<string, (testId: string) => boolean> = {
  storm_disturbance: (id) => id.startsWith('vh_'),
  observation_processing: (id) => id === 'cross_crid_radiometric_compatibility',
};

export interface Cause {
  id: string;
  /** Every cause is still open; `tested` says whether any recorded test touched it. */
  tested: boolean;
  label: Text;
  check: Text;
  testIds: string[];
}

export const CAUSES: Cause[] = investigation.hypotheses
  .map((h) => {
    const testIds = QA_TESTS.map((q) => q.id).filter(CAUSE_TESTS[h.hypothesis_id] ?? (() => false));
    return {
      id: h.hypothesis_id,
      tested: h.test_status !== 'NOT_TESTED',
      label: CAUSE_TEXT[h.hypothesis_id]?.label ?? { zh: h.statement, en: h.statement },
      check: CAUSE_TEXT[h.hypothesis_id]?.check ?? { zh: h.falsification_check, en: h.falsification_check },
      testIds,
    };
  })
  .sort((a, b) => Number(b.tested) - Number(a.tested));

/** Data sources the recorded tests cite. */
export interface EvidenceSource {
  id: string;
  label: Text;
}

const SOURCE_TEXT: Record<string, Text> = {
  'E-CHAMPI-MOA-20261106': { zh: '農業部災損公告 11/06', en: 'Ministry loss report, Nov 6' },
  'E-CHAMPI-NLSC-TAIXI': { zh: '國土測繪中心田區界線', en: 'NLSC field boundaries' },
  'E-CHAMPI-ASF-CROSS-CRID': { zh: 'ASF 處理版本紀錄', en: 'ASF processing versions' },
};

const observationLabel = new Map(
  investigation.observation_timeline.map((o) => {
    const date = o.acquisition_start_utc.slice(0, 10);
    const name = o.mission.startsWith('Sentinel-1/OPERA') ? 'Sentinel-1 VH' : o.mission;
    return [o.evidence_id, { zh: `${name} ${date}`, en: `${name} ${date}` } as Text];
  }),
);

/** Which sources each recorded test cites. */
export const TEST_SOURCES: Record<string, string[]> = Object.fromEntries(
  investigation.hypothesis_tests.map((t) => [t.test_id, t.evidence_ids ?? []]),
);

export const EVIDENCE_SOURCES: EvidenceSource[] = [...new Set(Object.values(TEST_SOURCES).flat())].map((id) => ({
  id,
  label: SOURCE_TEXT[id] ?? observationLabel.get(id) ?? { zh: id, en: id },
})).sort((a, b) => a.label.en.localeCompare(b.label.en));

/** Township boundaries (NLSC) around the case: Taixi and its neighbours. */
export const TOWNSHIPS: { name: Text; geometry: FieldGeometry }[] = (
  JSON.parse(townshipsGeojson) as { features: { properties: { name_zh: string; name_en: string }; geometry: FieldGeometry }[] }
).features.map((f) => ({ name: { zh: f.properties.name_zh, en: f.properties.name_en }, geometry: f.geometry }));

type NisarScene = {
  period: string;
  acquisition_start_utc: string;
  crid: string;
  product_maturity: string;
  coordinates: number[][];
  layers: { HH?: { image: string }; HV?: { image: string }; RGB: { image: string } };
};
const studio = (file: string) => `${import.meta.env.BASE_URL}studio/${file}`;
const nisarScene = (s: NisarScene) => ({
  period: s.period as 'PRE' | 'POST' | 'PRE_ASC' | 'POST_ASC',
  date: s.acquisition_start_utc.slice(0, 10),
  crid: s.crid,
  maturity: s.product_maturity,
  corners: s.coordinates as LngLat[],
  image: { HH: studio(s.layers.HH?.image ?? ''), HV: studio(s.layers.HV?.image ?? ''), RGB: studio(s.layers.RGB.image) },
});

/**
 * NISAR passes over Taixi, each stretched on its own. `scenes` are the 10/16 and 10/28 descending passes
 * on one track; `ascending` is the 10/26 pass on another track, which covers the south the 10/28 pass
 * missed. `comparePair` is that track's 10/14 -> 10/26 pair: both cover all of Taixi, so the field
 * comparison uses it.
 */
const ascending = nisarScene(nisarAscending.scene as NisarScene);
export const NISAR_TAIXI = {
  crossVersionVerified: nisarMap.cross_crid_radiometric_equivalence_verified,
  scenes: (nisarMap.scenes as NisarScene[]).map(nisarScene),
  ascending,
  comparePair: [nisarScene(nisarAscending.pre_scene as NisarScene), ascending],
};

export const OFFICIAL_LOSS = {
  date: official.report_date_local,
  url: official.source_url,
  yunlinNtd: official.yunlin_county_ntd,
  taiwanNtd: official.taiwan_total_ntd,
  /** National crop figures; the report gives no county areas. */
  cropAreaHa: official.taiwan_crop_damaged_area_ha,
  damagePct: official.taiwan_crop_damage_level_pct,
  noHarvestHa: official.taiwan_crop_no_harvest_equiv_ha,
  yunlinSharePct: official.yunlin_share_pct,
  yunlinRank: official.yunlin_rank,
};

/**
 * Our county-wide radar estimate (scripts/estimate_yunlin_damage_area.py): Yunlin farmland whose
 * Sentinel-1 backscatter changed by >= 2 dB during the warning, minus what an ordinary 12 days changes.
 * Mostly brightening, so more likely wet fields than lost crops; not confirmed damage.
 */
export const YUNLIN_AREA = {
  typhoon: yunlinArea.typhoon as [string, string],
  control: yunlinArea.control as [string, string],
  thresholdDb: yunlinArea.threshold_db,
  farmlandHa: yunlinArea.farmland_ha,
  excessHa: yunlinArea.excess_ha,
  excessShare: yunlinArea.excess_share,
  excessHaAt3Db: yunlinArea.excess_ha_at_3db,
  /** NISAR (scripts/estimate_yunlin_nisar_change.py): parcels whose HH darkened beyond an ordinary 12 days, 3 dB to 2 dB. */
  flattenedHa: [yunlinArea.flattened_or_flooded.low_ha, yunlinArea.flattened_or_flooded.high_ha] as [number, number],
};

/** Large NT$ amount: 1.58 億 / 157.7 million. */
export const bigNtd = (ntd: number, lang: Lang) => (lang === 'zh' ? `${(ntd / 1e8).toFixed(2)} 億` : `${(ntd / 1e6).toFixed(1)} million`);
