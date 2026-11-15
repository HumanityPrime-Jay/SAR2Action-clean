/** Typed API client & response cache for Earth Change Intelligence Platform. */

export type LensMode = 'OBSERVED' | 'HYPOTHESES' | 'UNKNOWN' | 'NEXT_EVIDENCE';
export type UserMode = 'FARMER' | 'AUTHORITY';

export interface ProvenanceMeta {
  data_status: string;
  evidence_ids: string[];
  scientific_limitations: string[];
  sources: string[];
  error_code?: string | null;
}

export interface GlobalEventRecord {
  event_id: string;
  event_name: string;
  event_name_zh: string;
  event_type: string;
  country: string;
  region: string;
  center_lon: number;
  center_lat: number;
  default_zoom: number;
  aoi_bbox: number[];
  aoi_geometry: Record<string, unknown>;
  observation_sources: string[];
  sensor: string;
  polarization: string[];
  acquisition_dates: string[];
  product_versions: string[];
  available_layers: string[];
  change_analysis_status: 'CATALOG_DISCOVERED' | 'OBSERVATION_AVAILABLE' | 'COMPARISON_COMPATIBLE' | 'CHANGE_ANALYZED';
  demo_mode: string;
  scientific_qa: Record<string, unknown>;
  evidence_ids: string[];
  data_provenance: string[];
  story_available: boolean;
  summary: string;
  summary_zh: string;
}

export interface AcquisitionPoint {
  acquisition_id: string;
  acquisition_time_utc: string;
  acquisition_time_local: string;
  date_label: string;
  sensor: string;
  polarization: string;
  product_version: string;
  source: string;
  qa_status: string;
  warning_phase: string;
  compatible_with_baseline: boolean;
  compatibility_note?: string | null;
  metric_name?: string | null;
  metric_value?: number | null;
  metric_unit?: string | null;
  overlay_url?: string | null;
  evidence_id?: string | null;
}

export interface ObservationGap {
  start_utc: string;
  end_utc: string;
  gap_days: number;
  status: 'NO_OBSERVATION';
  note: string;
}

export interface EarthMemoryTimelineResponse {
  event_id: string;
  field_id?: string | null;
  acquisitions: AcquisitionPoint[];
  observation_gaps: ObservationGap[];
  cross_sensor_warnings: string[];
  provenance: ProvenanceMeta;
}

export interface RealityLensFeature {
  feature_id: string;
  label: string;
  geometry?: Record<string, unknown> | null;
  scale: 'PARCEL' | 'REGION' | 'CATALOG';
  status: string;
  metrics: Record<string, unknown>;
  explanation: string;
  evidence_ids: string[];
}

export interface RealityLensResponse {
  event_id: string;
  lens: LensMode;
  title: string;
  subtitle: string;
  legend_items: Array<{ color: string; label: string }>;
  features: RealityLensFeature[];
  no_fake_confidence: boolean;
  spatial_qa_available: boolean;
  provenance: ProvenanceMeta;
}

export interface SurfaceFingerprint {
  region_id: string;
  event_id: string;
  label: string;
  sensor: string;
  polarizations: string[];
  product_version: string;
  observation_count: number;
  vh_temporal_signature: Array<{ date: string; vh_db: number; season: string }>;
  hh_hv_signature: Record<string, unknown> | string;
  temporal_difference_db?: number | null;
  seasonal_reference_db?: number | null;
  spatial_heterogeneity: number | string;
  valid_pixel_ratio: number | string;
  qa_status: string;
  missing_evidence: string[];
  feature_vector: Record<string, number | null>;
  evidence_ids: string[];
}

export interface FingerprintCompareResponse {
  source: SurfaceFingerprint;
  target: SurfaceFingerprint;
  comparable: boolean;
  incompatibility_reasons: string[];
  normalized_feature_distance?: number | null;
  temporal_pattern_similarity?: number | null;
  scientific_caution: string;
  provenance: ProvenanceMeta;
}

export interface SimilarChangeResponse {
  query_region_id: string;
  candidates: Array<{
    region_id: string;
    label: string;
    comparable: boolean;
    normalized_feature_distance?: number | null;
    temporal_pattern_similarity?: number | null;
    incompatibility_reason?: string | null;
    causal_warning: string;
  }>;
  provenance: ProvenanceMeta;
}

export interface HypothesisArenaCard {
  hypothesis_id: string;
  title: string;
  description: string;
  status: string;
  supporting_evidence: string[];
  alternative_explanations: string[];
  direct_contradictions: string[];
  missing_evidence: string[];
  test_outcomes: Array<Record<string, unknown>>;
  available_experiments: Array<{
    experiment_id: string;
    experiment_type: string;
    tool: string;
    feasibility: string;
    predicted_outcome: string;
    unavailability_reason?: string | null;
  }>;
}

export interface HypothesisArenaResponse {
  event_id: string;
  field_id: string;
  research_question: string;
  hypotheses: HypothesisArenaCard[];
  recommended_next_experiment?: Record<string, unknown> | null;
  provenance: ProvenanceMeta;
}

export interface RunHypothesisExperimentResponse {
  event_id: string;
  field_id: string;
  hypothesis_id: string;
  executed: boolean;
  status: string;
  experiment_type: string;
  summary: string;
  metrics: Record<string, unknown>;
  evidence_ids: string[];
  hypothesis_status_after: string;
  evaluation_outcome: string;
  reason_if_not_executable?: string | null;
  provenance: ProvenanceMeta;
}

export interface EvidenceGapResponse {
  event_id: string;
  field_id: string;
  gaps: Array<{
    gap_id: string;
    title: string;
    priority: 'HIGH' | 'MEDIUM' | 'LOW';
    why_missing: string;
    research_value: string;
    where_to_find: string;
    recommended_action: string;
  }>;
  stage_one_policy: string;
  provenance: ProvenanceMeta;
}

export interface CatalogSearchResponse {
  event_id: string;
  product_family: string;
  search_executed: boolean;
  network_status: string;
  scenes: Array<Record<string, unknown>>;
  compatibility_summary: string;
  download_permitted: boolean;
  provenance: ProvenanceMeta;
}

export interface AIMapAction {
  action: string;
  params: Record<string, unknown>;
}

export interface GuidedDiscoveryResponse {
  query: string;
  user_mode: UserMode;
  execution_mode: string;
  answer: string;
  actions: AIMapAction[];
  validated_actions_count: number;
  rejected_actions: string[];
  facts_used: string[];
  provenance: ProvenanceMeta;
}

export interface StoryChapter {
  chapter_number: number;
  chapter_code: string;
  title: string;
  narrative: string;
  camera: Record<string, unknown>;
  lens: LensMode;
  timeline_date?: string | null;
  active_layers: string[];
  metrics: Array<Record<string, unknown>>;
  evidence_ids: string[];
  limitations: string[];
}

export interface EarthStory {
  story_id: string;
  event_id: string;
  field_id: string;
  title: string;
  created_at_utc: string;
  user_mode: UserMode;
  chapters: StoryChapter[];
  provenance: ProvenanceMeta;
}

const getCache = new Map<string, unknown>();

async function apiJson<T>(url: string, init?: RequestInit, useCache = false): Promise<T> {
  if (useCache && getCache.has(url)) {
    return getCache.get(url) as T;
  }
  const resp = await fetch(url, init);
  if (!resp.ok) {
    const detail = await resp.text().catch(() => resp.statusText);
    throw new Error(`HTTP ${resp.status}: ${detail}`);
  }
  const data = (await resp.json()) as T;
  if (useCache) getCache.set(url, data);
  return data;
}

export const earthApi = {
  listEvents: (eventType?: string, q?: string, signal?: AbortSignal) => {
    const params = new URLSearchParams();
    if (eventType) params.set('event_type', eventType);
    if (q) params.set('q', q);
    const qs = params.toString();
    return apiJson<{ events: GlobalEventRecord[]; supported_event_types: string[]; total: number; provenance: ProvenanceMeta }>(
      `/api/earth/events${qs ? `?${qs}` : ''}`,
      { signal },
      !qs,
    );
  },
  getTimeline: (eventId: string, fieldId?: string, signal?: AbortSignal) =>
    apiJson<EarthMemoryTimelineResponse>(
      `/api/earth/events/${encodeURIComponent(eventId)}/timeline${fieldId ? `?field_id=${encodeURIComponent(fieldId)}` : ''}`,
      { signal },
      true,
    ),
  getLens: (eventId: string, lens: LensMode, fieldId?: string, signal?: AbortSignal) =>
    apiJson<RealityLensResponse>(
      `/api/earth/events/${encodeURIComponent(eventId)}/lens/${lens}${fieldId ? `?field_id=${encodeURIComponent(fieldId)}` : ''}`,
      { signal },
      true,
    ),
  getFingerprint: (regionId: string, signal?: AbortSignal) =>
    apiJson<SurfaceFingerprint>(`/api/earth/fingerprint/${encodeURIComponent(regionId)}`, { signal }, true),
  compareFingerprints: (sourceRegionId: string, targetRegionId: string, eventId = 'CHAMPI-YUNLIN-TAIXI') =>
    apiJson<FingerprintCompareResponse>('/api/earth/fingerprint/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_region_id: sourceRegionId, target_region_id: targetRegionId, event_id: eventId }),
    }),
  findSimilar: (regionId: string) =>
    apiJson<SimilarChangeResponse>(`/api/earth/fingerprint/${encodeURIComponent(regionId)}/similar`, undefined, true),
  getArena: (eventId: string, fieldId: string) =>
    apiJson<HypothesisArenaResponse>(`/api/earth/hypotheses/${encodeURIComponent(eventId)}?field_id=${encodeURIComponent(fieldId)}`),
  runExperiment: (payload: { event_id: string; field_id: string; hypothesis_id: string; experiment_type?: string; propose_only?: boolean }) =>
    apiJson<RunHypothesisExperimentResponse>('/api/earth/hypotheses/experiment', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  getEvidenceGaps: (eventId: string, fieldId: string) =>
    apiJson<EvidenceGapResponse>(`/api/earth/evidence-gaps/${encodeURIComponent(eventId)}?field_id=${encodeURIComponent(fieldId)}`),
  searchCatalog: (payload: { event_id: string; product_family: string; live_network: boolean }) =>
    apiJson<CatalogSearchResponse>('/api/earth/evidence-gaps/catalog-search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  guidedDiscovery: (payload: { query: string; context: Record<string, unknown>; prefer_gemini?: boolean }) =>
    apiJson<GuidedDiscoveryResponse>('/api/earth/guided-discovery', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  generateStory: (payload: { event_id: string; field_id: string; user_mode: UserMode; lang: 'zh' | 'en' }) =>
    apiJson<EarthStory>('/api/earth/stories/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  importStory: (story: EarthStory) =>
    apiJson<EarthStory>('/api/earth/stories/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ story }),
    }),
};
