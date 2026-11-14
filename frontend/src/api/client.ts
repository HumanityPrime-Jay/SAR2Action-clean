import {
  ApiScienceError,
  CaseSummary,
  EvidenceRecord,
  LayerMetadataResponse,
  ObservationRecord,
  PolarizationChannel,
  RadarFingerprintResponse,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export class ScienceApiError extends Error {
  public readonly statusCode: number;
  public readonly scienceError: ApiScienceError;

  constructor(statusCode: number, scienceError: ApiScienceError) {
    super(scienceError.message);
    this.statusCode = statusCode;
    this.scienceError = scienceError;
  }
}

async function handleResponse<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let errPayload: ApiScienceError = {
      error_code: `HTTP_${resp.status}`,
      message: `API error (${resp.status})`,
      science_status: 'INSUFFICIENT_EVIDENCE',
    };
    try {
      const body = await resp.json();
      if (body?.detail && typeof body.detail === 'object') {
        errPayload = {
          error_code: body.detail.error_code || `HTTP_${resp.status}`,
          message: body.detail.message || JSON.stringify(body.detail),
          science_status: body.detail.science_status || 'INSUFFICIENT_EVIDENCE',
          details: body.detail.details || {},
        };
      }
    } catch {
      // ignore JSON parse failure
    }
    throw new ScienceApiError(resp.status, errPayload);
  }
  return resp.json() as Promise<T>;
}

export async function fetchCases(): Promise<CaseSummary[]> {
  const resp = await fetch(`${API_BASE}/api/cases`);
  const data = await handleResponse<{ cases: CaseSummary[] }>(resp);
  return data.cases;
}

export async function fetchCaseObservations(caseId: string): Promise<{
  case_id: string;
  default_t0_scene_id: string;
  default_t1_scene_id: string;
  observations: ObservationRecord[];
}> {
  const resp = await fetch(`${API_BASE}/api/cases/${encodeURIComponent(caseId)}/observations`);
  return handleResponse(resp);
}

export async function requestRadarFingerprint(params: {
  case_id: string;
  scene_t0_id?: string;
  scene_t1_id?: string;
  aoi_id?: string;
  aoi_bbox_wgs84: [number, number, number, number];
  requested_polarizations?: PolarizationChannel[];
}): Promise<RadarFingerprintResponse> {
  const resp = await fetch(`${API_BASE}/api/radar-fingerprint`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  return handleResponse<RadarFingerprintResponse>(resp);
}

export async function fetchEvidenceRecord(evidenceId: string): Promise<EvidenceRecord> {
  const resp = await fetch(`${API_BASE}/api/evidence/${encodeURIComponent(evidenceId)}`);
  return handleResponse<EvidenceRecord>(resp);
}

export async function fetchLayerMetadata(layerId: string): Promise<LayerMetadataResponse> {
  const resp = await fetch(`${API_BASE}/api/layers/${encodeURIComponent(layerId)}`);
  return handleResponse<LayerMetadataResponse>(resp);
}
