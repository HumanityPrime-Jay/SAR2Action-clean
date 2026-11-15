/**
 * Client for TW-05 agricultural satellite evidence, Gemini agent and statutory relief APIs.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export interface AgentStatusInfo {
  agent: { status: string; reason?: string };
  gemini: {
    status: string;
    provider: string;
    model: string;
    api_key_configured: boolean;
    live_function_calling_verified: boolean;
    reason?: string;
  };
  tw05_agent_available: boolean;
  tw05_tools: string[];
}

export interface Tw05ObservedFact {
  fact_id: string;
  sensor_or_source: string;
  metric_name: string;
  metric_value?: number | null;
  verified_value_str: string;
  unit: string;
  statement: string;
  epistemic_status: 'OBSERVED';
  evidence_ids: string[];
}

export interface Tw05InferenceItem {
  inference_id: string;
  statement: string;
  status: 'SUPPORTED_FOR_FOLLOWUP_ONLY' | 'UNRESOLVED' | 'BLOCKED';
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  proposed_by_gemini: boolean;
  reason: string;
}

export interface Tw05EvidenceCitation {
  evidence_id: string;
  source_module: string;
  sensor_or_authority: string;
  acquisition_window: string;
  summary: string;
  provenance_status: string;
  verified_metrics: Record<string, unknown>;
  limitations: string[];
}

export interface Tw05ToolTraceStep {
  step: number;
  timestamp_utc: string;
  kind: 'request' | 'planner' | 'tool_call' | 'tool_result' | 'validation' | 'final';
  tool: string;
  status: 'complete' | 'executed' | 'rejected' | 'failed' | 'blocked' | 'skipped';
  validated_arguments?: Record<string, unknown> | null;
  source_references: string[];
  evidence_ids: string[];
  reason?: string | null;
  duration_ms?: number | null;
  detail: Record<string, unknown>;
}

export interface Tw05InvestigationResponse {
  investigation_id: string;
  status: 'completed' | 'blocked';
  execution_mode:
    | 'GEMINI_FUNCTION_CALLING_LIVE'
    | 'GEMINI_FUNCTION_CALLING_MOCK'
    | 'DETERMINISTIC_TOOL_PIPELINE'
    | 'BLOCKED_NO_MODEL_CONFIGURED'
    | 'BLOCKED_MODEL_EXECUTION_FAILED'
    | 'BLOCKED_NO_VALID_TOOL_SELECTED'
    | 'BLOCKED_VALIDATION_FAILED';
  agent_mode: string;
  model_provider: string;
  model_name?: string | null;
  case_id: string;
  aoi_id: string;
  locked_parcel_feature_id?: number | null;
  question: string;
  observed_facts: Tw05ObservedFact[];
  inferences: Tw05InferenceItem[];
  unknowns: string[];
  evidence_ids: string[];
  evidence_records: Tw05EvidenceCitation[];
  tool_trace: Tw05ToolTraceStep[];
  scientific_limitations: string[];
  error?: {
    error_code: string;
    message: string;
    rejected_tool_count: number;
    unauthorized_tool_calls: number;
  } | null;
  epistemic_guardrails: {
    crop_type_label: string;
    actual_damage_rate: string;
    confirmed_typhoon_damage: boolean;
    official_relief_eligibility: string;
    optical_insufficient_parcel_flag: boolean;
  };
  parcel_summary?: Record<string, unknown> | null;
}

export interface TwAgroReliefScheduleItem {
  item_id: string;
  display_name: string;
  statutory_category: string;
  rate_twd_per_ha?: number | null;
  unit: string;
  announced_in_yunlin_11510: boolean;
  statutory_conditions?: string | null;
}

export interface TwAgroReliefCatalog {
  schedule_version_id: string;
  regulation_title: string;
  min_application_area_ha: number;
  statutory_loss_threshold_fraction: number;
  items: TwAgroReliefScheduleItem[];
  /** Yunlin relief announcements for this disaster, with their application windows. */
  announcements?: { doc_id: string; application_end_iso: string; expired_as_of_reference_date: boolean }[];
}

export interface TwAgroReliefEstimateRequest {
  parcel_feature_id?: number | null;
  crop_item_id: string;
  assumed_approved_area_ha?: number | null;
  assumed_loss_threshold:
    | 'unverified'
    | 'below_20_percent'
    | 'meets_20_percent'
    | 'article_12_simplified_exception';
  allow_cross_aoi_boundary_area?: boolean;
}

export interface TwAgroReliefEstimateResponse {
  calculation_allowed: boolean;
  result_status:
    | 'CONDITIONAL_REFERENCE_ESTIMATE'
    | 'BLOCKED_UNKNOWN_CROP'
    | 'BLOCKED_UNANNOUNCED_OR_EXCLUDED_ITEM'
    | 'BLOCKED_UNVERIFIED_OR_BELOW_20_THRESHOLD'
    | 'BLOCKED_BELOW_MIN_AREA_001_HA'
    | 'BLOCKED_INVALID_AREA';
  result_label: string;
  blocked_reason?: string | null;
  conditional_reference_amount_twd?: number | null;
  formula_display?: string | null;
  confirmed_facts: Record<string, unknown>;
  user_assumptions: Record<string, unknown>;
  unconfirmed_eligibility: string[];
  non_approval_disclaimer: string;
}

export async function fetchAgentStatus(): Promise<AgentStatusInfo> {
  const resp = await fetch(`${API_BASE}/api/agent/status`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

export async function investigateTw05(
  payload: {
    parcel_feature_id: number;
    question: string;
    agent_mode?: 'gemini' | 'deterministic' | 'real';
    session_id?: string;
  },
  signal?: AbortSignal,
): Promise<Tw05InvestigationResponse> {
  const resp = await fetch(`${API_BASE}/api/agent/tw05/investigate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      case_id: 'TW-05-YUNLIN-AGRO',
      aoi_id: 'TW-01-YUNLIN-5KM',
      parcel_feature_id: payload.parcel_feature_id,
      question: payload.question,
      agent_mode: payload.agent_mode || 'gemini',
      session_id: payload.session_id || `tw05-${payload.parcel_feature_id}`,
    }),
    signal,
  });
  if (!resp.ok) {
    let errBody: any = null;
    try {
      errBody = await resp.json();
    } catch {
      // ignore
    }
    const msg = errBody?.detail?.message || errBody?.detail || `HTTP ${resp.status}`;
    throw new Error(msg);
  }
  return resp.json();
}

export async function fetchReliefCatalog(): Promise<TwAgroReliefCatalog> {
  const resp = await fetch(`${API_BASE}/api/tw-agro/relief-catalog`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

export async function estimateRelief(
  payload: TwAgroReliefEstimateRequest,
  signal?: AbortSignal,
): Promise<TwAgroReliefEstimateResponse> {
  const resp = await fetch(`${API_BASE}/api/tw-agro/relief-estimate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  if (!resp.ok) {
    let errBody: any = null;
    try {
      errBody = await resp.json();
    } catch {
      // ignore
    }
    const msg = errBody?.detail?.message || errBody?.detail || `HTTP ${resp.status}`;
    throw new Error(msg);
  }
  return resp.json();
}

export async function fetchParcelOptical(
  parcelFeatureId: number,
  signal?: AbortSignal,
): Promise<any> {
  const resp = await fetch(`${API_BASE}/api/tw-agro/parcels/${parcelFeatureId}/optical`, { signal });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}
