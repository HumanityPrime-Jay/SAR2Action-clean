/**
 * Relief agent in authority mode (`POST /api/agent/chat`, mode AUTHORITY): scientific evidence and the
 * relief regulations (M0090019) checked rule by rule. One reply serves both the authority and the farmer
 * view; the farmer view only rewords it, and never the law text.
 */
import { AgentUnavailableError } from './farmerAgent';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export type RuleState = 'TRUE' | 'FALSE' | 'UNKNOWN' | 'NOT_APPLICABLE';

export interface LegalCitation {
  law_name: string;
  /** e.g. "第12-1條" */
  article: string;
  version: string;
  official_url: string;
  /** Verbatim article text; shown as it is in both views. */
  exact_source_text: string;
  source_id: string;
}

export interface RuleEvaluation {
  rule_id: string;
  rule_name: string;
  state: RuleState;
  citation_id: string;
  reason: string;
  missing_fields: string[];
}

export interface AuthorityReply {
  mode: 'AUTHORITY';
  field_id: string;
  summary: string;
  scientific_evidence: {
    crop_damage_confirmed: boolean;
    vh_change: { status: string; median_change_db: number | null; pre_median_db: number | null; warning_median_db: number | null; post_median_db: number | null };
    sar_quality: { qa_passed: boolean; valid_pixels: number; valid_coverage_ratio: number };
    spatial_reference_matching: { matched_fields: { field_id: string }[]; excluded_fields: { field_id: string }[] };
  };
  legal_authority: {
    status: string;
    citations: LegalCitation[];
    applicable_law_version: { version: string | null };
    rule_evaluations: { overall_status: string; rule_evaluations: RuleEvaluation[]; missing_information: string[] };
  };
  required_follow_up: { farmer: string[]; authority: string[]; field_survey: string[] };
  limitations: string[];
}

export interface AuthorityChatRequest {
  message: string;
  field_id: string;
  crop?: string;
  lang?: 'zh' | 'en';
}

export async function authorityChat(req: AuthorityChatRequest, signal?: AbortSignal): Promise<AuthorityReply> {
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}/api/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'AUTHORITY', ...req }),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err;
    throw new AgentUnavailableError('network');
  }
  if (!resp.ok) throw new AgentUnavailableError(`HTTP ${resp.status}`);
  const body = (await resp.json()) as AuthorityReply;
  if (body?.mode !== 'AUTHORITY' || !body.legal_authority || !body.scientific_evidence) throw new AgentUnavailableError('unexpected reply');
  return body;
}
