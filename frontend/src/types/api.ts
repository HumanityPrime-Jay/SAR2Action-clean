export type ScienceQualityStatus =
  | 'OBSERVED'
  | 'COMPARABLE'
  | 'LIMITED'
  | 'INSUFFICIENT_EVIDENCE';

export type PolarizationChannel = 'HH' | 'HV' | 'VV' | 'VH';

export type LayerType =
  | 't0_hh'
  | 't1_hh'
  | 't0_hv'
  | 't1_hv'
  | 'delta_hh'
  | 'delta_hv'
  | 'magnitude_hh'
  | 'magnitude_hv'
  | 'combined_change'
  | 'validity_mask';

export type RevealMode =
  | LayerType
  | 'swipe_hh'
  | 'swipe_hv';

export type AOISelectionMethod =
  | 'PREDEFINED_EXTERNAL_CONTEXT'
  | 'PREDEFINED_GEOGRAPHIC_AOI'
  | 'EXPLORATORY_POST_HOC_RADAR_CHANGE'
  | 'USER_CUSTOM_AOI';

export type AOISelectionTime = 'PRE_ANALYSIS' | 'POST_HOC_INSPECTION';

export type DemoMode = 'LIVE' | 'CACHED_REAL_DATA';

export interface PresetAOI {
  aoi_id: string;
  name: string;
  description: string;
  bbox_wgs84: [number, number, number, number];
  default_evidence_id?: string | null;
  selection_method?: AOISelectionMethod;
  selection_time?: AOISelectionTime;
  selection_basis?: string;
}

export interface CaseSummary {
  case_id: string;
  title: string;
  case_role: 'PRIMARY_FLAGSHIP' | 'ENGINEERING_VALIDATION' | 'BACKUP_FLAGSHIP';
  region_name: string;
  track_number: number;
  frame_number: number;
  orbit_pass_direction: 'ASCENDING' | 'DESCENDING';
  look_direction: 'LEFT' | 'RIGHT';
  polarizations: PolarizationChannel[];
  product_maturity: string;
  crid: string;
  is_full_frame: boolean;
  default_t0_scene_id: string;
  default_t1_scene_id: string;
  t0_acquisition_utc: string;
  t1_acquisition_utc: string;
  t0_orbit_pointing_fidelity?: string | null;
  t1_orbit_pointing_fidelity?: string | null;
  rfi_comparison_status?: string;
  default_aoi_bbox_wgs84: [number, number, number, number];
  illuminated_bbox_wgs84: [number, number, number, number];
  crs_epsg: number;
  pixel_spacing_m: [number, number];
  local_hdf5_ready: boolean;
  scientific_scope_note: string;
  preset_aois: PresetAOI[];
}

export interface ObservationRecord {
  scene_id: string;
  case_id: string;
  acquisition_start_utc: string;
  acquisition_end_utc: string;
  acquisition_date: string;
  track_or_frame: string;
  orbit_pass_direction: string;
  look_direction: string;
  polarizations: PolarizationChannel[];
  product_maturity: string;
  crid: string | null;
  processing_version: string | null;
  is_full_frame: boolean;
  orbit_pointing_fidelity_code?: string | null;
  orbit_pointing_fidelity_label?: string | null;
  coverage_fidelity_code?: string | null;
  coverage_fidelity_label?: string | null;
  sds_location_code?: string | null;
  approx_file_size_bytes: number | null;
  bbox_wgs84: [number, number, number, number] | null;
  local_hdf5_available: boolean;
  local_hdf5_path?: string | null;
}

export interface DistributionStatsDb {
  mean: number;
  median: number;
  std: number;
  min: number;
  max: number;
  p10?: number | null;
  p25?: number | null;
  p50?: number | null;
  p75?: number | null;
  p90?: number | null;
}

export interface LayerLegendStop {
  value: number;
  color: string;
  label: string;
}

export interface LayerLegendSpec {
  title: string;
  units: string;
  min_value: number;
  max_value: number;
  palette_type:
    | 'single_epoch_db'
    | 'signed_diverging_db'
    | 'magnitude_sequential_db'
    | 'validity_mask';
  stops: LayerLegendStop[];
  positive_change_meaning?: string | null;
  negative_change_meaning?: string | null;
  invalid_observation_meaning: string;
  prohibited_labels_notice: string;
}

export interface LayerMetadataResponse {
  layer_id: string;
  case_id: string;
  evidence_id: string;
  roi_id: string;
  layer_type: LayerType;
  title: string;
  polarization?: PolarizationChannel | null;
  units: string;
  source_scenes: string[];
  t0_acquisition_utc: string;
  t1_acquisition_utc?: string | null;
  bbox_wgs84: [number, number, number, number];
  crs_epsg: number;
  width: number;
  height: number;
  image_url: string;
  color_interpretation: string;
  legend: LayerLegendSpec;
  disclaimer?: string | null;
  limitations: string[];
}

export interface DeterministicClaim {
  claim_id: string;
  statement: string;
  evidence_id: string;
  case_id: string;
  roi_id: string;
  scene_ids: string[];
  aoi_bbox_wgs84: [number, number, number, number];
  polarization?: PolarizationChannel | null;
  metric_name: string;
  metric_value: number;
  unit: string;
  valid_pixel_count: number;
  valid_area_km2: number;
  algorithm_version: string;
  calculation_formula: string;
  target_layer_type: string;
}

export interface PolarizationFingerprintDetail {
  polarization: PolarizationChannel;
  available: boolean;
  status_label: 'Available' | 'Unavailable';
  t0_median_db?: number | null;
  t0_mean_db?: number | null;
  t1_median_db?: number | null;
  t1_mean_db?: number | null;
  delta_median_db?: number | null;
  delta_mean_db?: number | null;
  delta_distribution_db?: DistributionStatsDb | null;
  magnitude_median_db?: number | null;
  magnitude_mean_db?: number | null;
  magnitude_distribution_db?: DistributionStatsDb | null;
  positive_change_fraction?: number | null;
  negative_change_fraction?: number | null;
}

export interface EpistemicSummaryPanel {
  what_we_observed: string[];
  what_may_explain_it: string[];
  what_we_do_not_know: string[];
}

export interface EvidenceRecord {
  evidence_id: string;
  evidence_type: string;
  scene_ids: string[];
  roi_id: string;
  selection_method?: AOISelectionMethod;
  selection_time?: AOISelectionTime;
  selection_basis?: string;
  geometry: Record<string, unknown> | null;
  polarizations: PolarizationChannel[];
  t0_db: Record<string, DistributionStatsDb>;
  t1_db: Record<string, DistributionStatsDb>;
  delta_db: Record<string, DistributionStatsDb>;
  magnitude_db: Record<string, DistributionStatsDb>;
  combined_change_db?: {
    metric_name: string;
    unit?: string;
    formula?: string;
    disclaimer: string;
    stats: DistributionStatsDb;
  } | null;
  summary_statistics: Record<string, unknown>;
  valid_pixel_count: number;
  coverage_ratio: number;
  missing_data_ratio: number;
  quality_status: ScienceQualityStatus;
  algorithm_version: string;
  processing_metadata: Record<string, unknown>;
  limitations: string[];
}

export interface RadarFingerprintResponse {
  case_id: string;
  roi_id: string;
  evidence_id: string;
  selection_method?: AOISelectionMethod;
  selection_time?: AOISelectionTime;
  selection_basis?: string;
  demo_mode?: DemoMode;
  cache_hit?: boolean;
  quality_status: ScienceQualityStatus;
  t0_acquisition_utc: string;
  t1_acquisition_utc: string;
  aoi_bbox_wgs84: [number, number, number, number];
  available_polarizations: PolarizationChannel[];
  unavailable_polarizations: PolarizationChannel[];
  hh_detail: PolarizationFingerprintDetail;
  hv_detail: PolarizationFingerprintDetail;
  combined_radar_change_detail?: {
    metric_name: string;
    unit?: string;
    formula?: string;
    disclaimer: string;
    stats: DistributionStatsDb;
  } | null;
  valid_pixel_count: number;
  valid_area_m2: number;
  valid_area_ha: number;
  valid_area_km2: number;
  coverage_ratio: number;
  missing_invalid_fraction: number;
  epistemic_panel: EpistemicSummaryPanel;
  claims: DeterministicClaim[];
  layers: Record<string, LayerMetadataResponse>;
  evidence_record: EvidenceRecord;
}

export interface ApiScienceError {
  error_code: string;
  message: string;
  science_status: ScienceQualityStatus;
  details?: Record<string, unknown>;
}
