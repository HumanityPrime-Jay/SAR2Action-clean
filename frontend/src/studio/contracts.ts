export type StudioMode = 'RECORDED_DETERMINISTIC' | 'RECORDED_GEMINI' | 'LIVE_DETERMINISTIC' | 'LIVE_GEMINI';

export interface VhObservation {
  field_id: string;
  year: number;
  acquisition_datetime: string;
  vh_median_db: number | null;
  valid_pixel_count: number;
  interior_pixel_count?: number;
  valid_coverage_ratio: number;
  platform: string;
  relative_orbit: string | number;
  orbit_direction: string;
  source_scene_id: string;
  evidence_id: string;
  qa_flags: string[];
}

export interface StudioInvestigation {
  case_id: string;
  aoi_id: string;
  investigation_id: string;
  question: string;
  data_mode: string;
  observation_timeline: Array<Record<string, unknown>>;
  observation_statistics: Record<string, unknown>;
  vh_timeseries: { field_id: string; status: string; observations: VhObservation[] } | null;
  vh_comparison: Record<string, unknown> | null;
  field_comparison?: Record<string, unknown> | null;
  temporal_changes?: Record<string, unknown> | null;
  available_sensors: Array<Record<string, unknown>>;
  observed_changes: Array<Record<string, unknown>>;
  hypotheses: Array<Record<string, unknown>>;
  hypothesis_tests: Array<Record<string, unknown>>;
  evidence_ids: string[];
  scientific_limitations: string[];
  missing_evidence: string[];
  recommended_next_action: string;
  provenance_status: string;
  tool_trace: TraceEvent[];
  qa: Record<string, unknown>;
  official_loss_context: Record<string, unknown>;
  expert_report: Record<string, unknown>;
}

export interface TraceEvent {
  step?: number;
  timestamp_utc?: string;
  kind?: string;
  tool?: string;
  status?: string;
  source_references?: string[];
  evidence_ids?: string[];
  [key: string]: unknown;
}

export interface StudioAssets {
  fields: { type: string; features: Array<{ type: string; geometry: { type: string; coordinates: unknown }; properties: Record<string, unknown> }> };
  vh: { status: string; observations: VhObservation[]; mean_definition?: string };
  recorded: StudioInvestigation;
  recordedTrace: { investigation_id: string; mode: string; trace: TraceEvent[] };
  recordedDeterministic: StudioInvestigation;
  comparison: FieldComparison;
  recentGeminiTrace: { investigation_id: string; selected_tools: string[][]; tool_trace: TraceEvent[] };
  evidence: Map<string, Record<string, unknown>>;
  officialLoss: Record<string, unknown>;
  integrityWarnings: string[];
}

export interface FieldObservation {
  acquisition_utc: string;
  acquisition_taiwan: string;
  warning_relation: 'HISTORICAL_REFERENCE' | 'PRE_WARNING' | 'WARNING_WINDOW' | 'POST_WARNING';
  vh_median_db: number;
  valid_pixel_count: number;
  interior_pixel_count: number;
  valid_coverage_ratio: number;
  source_scene_id: string;
  evidence_id: string;
  qa_flags: string[];
}

export interface FieldDelta {
  label: string;
  median_difference_db: number;
  evidence_ids: string[];
  causal_attribution: 'UNKNOWN';
}

export interface FieldComparisonField {
  field_id: string;
  crop_label: string;
  observations: { '2025': FieldObservation[]; '2026': FieldObservation[] };
  matched_date_pairs: Array<{ '2025_utc': string; '2026_utc': string; '2026_minus_2025_db': number; evidence_ids: string[] }>;
  spatial_support: { min_valid_pixels: number; min_valid_coverage_ratio: number; assessment: string };
  '2026_pre_warning_change': FieldDelta | null;
  '2026_pre_warning_status': string;
  '2026_pre_to_warning_window': FieldDelta | null;
  '2026_pre_to_post_warning': FieldDelta | null;
  evidence_ids: string[];
}

export interface FieldComparison {
  status: 'OBSERVED_DESCRIPTIVE_ONLY';
  fields: FieldComparisonField[];
  event_reference: { start_taiwan: string; end_taiwan: string; middle_scene_utc: string; middle_scene_taiwan: string };
  cross_field_pattern: { pre_to_warning_increase_count: number; pre_to_post_increase_count: number; shared_response_is_causal_evidence: boolean };
  pixel_reverification: { status: string; reextracted_field_scene_count: number };
  scientific_limits: string[];
}

export interface GraphNode {
  id: string;
  type: 'OBSERVATION' | 'DATASET' | 'EVIDENCE' | 'HYPOTHESIS' | 'SCIENTIFIC_TEST' | 'CONCLUSION' | 'ACTION';
  label: string;
  payload: Record<string, unknown>;
}

export interface GraphEdge { from: string; to: string; relation: string }
