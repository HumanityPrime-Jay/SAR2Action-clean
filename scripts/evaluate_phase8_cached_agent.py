"""Real Gemini + cached evidence evaluation; credential comes only from process env."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.api import RadarFingerprintRequest
from backend.app.services.agent_orchestrator import InvestigateRequest
from backend.app.services.science_evidence_provider import ScienceEvidenceProvider
from scripts.validate_science_cache import audit


ROOT = Path(__file__).resolve().parents[1]
BBOX = [105.08, -2.92, 105.24, -2.76]
EVIDENCE_ID = 'E-FLAGSHIP-OKI-004'


def main() -> None:
    if os.getenv('SAR2ACTION_LLM_PROVIDER') != 'gemini' or not os.getenv('GEMINI_API_KEY'):
        raise SystemExit('GEMINI_PROCESS_CREDENTIAL_REQUIRED')
    handoff = audit(ROOT / 'data' / 'cache')
    if handoff['status'] != 'SCHEMA_AND_INTERNAL_PROVENANCE_VALID':
        raise SystemExit('SCIENCE_CACHE_VALIDATION_FAILED')
    provider = ScienceEvidenceProvider('cache')
    request = RadarFingerprintRequest(case_id='case-flagship-oki-f2', aoi_id='AOI-OKI-04', aoi_bbox_wgs84=BBOX)
    fp = provider.get_fingerprint(request)
    evidence = provider.get_evidence(EVIDENCE_ID)
    analysis = provider.get_analysis(request, EVIDENCE_ID)
    raw_fp = json.loads((ROOT / 'data/cache/fingerprint_store.json').read_text(encoding='utf-8'))['fingerprints'][EVIDENCE_ID]
    client = TestClient(app)
    http_fp_response = client.post('/api/radar-fingerprint', json=request.model_dump(mode='json'))
    http_ev_response = client.get('/api/evidence/' + EVIDENCE_ID)
    started = time.perf_counter()
    agent_response = client.post('/api/agent/investigate', json=InvestigateRequest(
        case_id='case-flagship-oki-f2', aoi_id='AOI-OKI-04', aoi_bbox_wgs84=BBOX,
        query='分析 AOI-OKI-04 的雷達變化，告訴我 HH/HV 有什麼改變，顯示實際證據，並解釋這些變化是否足以確認泥炭火災。請產生五幕證據故事。',
        data_mode='cache', agent_mode='real', session_id='phase8-evaluation').model_dump(mode='json'))
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    result = agent_response.json()
    http_fp = http_fp_response.json()
    http_ev = http_ev_response.json()
    hh = evidence.summary_statistics['per_polarization']['HH']['median_delta_db']
    hv = evidence.summary_statistics['per_polarization']['HV']['median_delta_db']
    trace = [{key: event[key] for key in ('tool', 'status', 'selected_intent', 'validated_arguments',
                                          'result_status', 'evidence_ids', 'ui_actions', 'duration_ms') if key in event}
             for event in result.get('trace', []) if event.get('tool') != 'user_request']
    completed = {event['tool'] for event in trace if event['status'] == 'complete'}
    checks = {
        'three_stores_internal_integrity': handoff['status'] == 'SCHEMA_AND_INTERNAL_PROVENANCE_VALID',
        'all_six_evidence_ids': all(handoff['expected_evidence_ids'].values()),
        'http_routes_success': http_fp_response.status_code == 200 and http_ev_response.status_code == 200 and agent_response.status_code == 200,
        'http_cache_labeled': http_fp.get('cache_hit') is True and http_fp.get('demo_mode') == 'CACHED_REAL_DATA',
        'evidence_id_match': result.get('evidence_ids') == [EVIDENCE_ID] and all(
            item == EVIDENCE_ID for item in (fp.evidence_id, analysis.evidence_id,
                                             http_fp.get('evidence_id'), http_ev.get('evidence_id'))),
        'hh_match': result.get('fingerprint_details', {}).get('hh_delta_median_db') == fp.hh_detail.delta_median_db == raw_fp['hh_detail']['delta_median_db'] == http_fp.get('hh_detail', {}).get('delta_median_db') == hh,
        'hv_match': result.get('fingerprint_details', {}).get('hv_delta_median_db') == fp.hv_detail.delta_median_db == raw_fp['hv_detail']['delta_median_db'] == http_fp.get('hv_detail', {}).get('delta_median_db') == hv,
        'valid_pixels_match': result.get('fingerprint_details', {}).get('valid_pixel_count') == evidence.valid_pixel_count == analysis.valid_pixel_count == http_fp.get('valid_pixel_count') == 3148830,
        'aoi_and_pair_match': result.get('fingerprint_details', {}).get('roi_id') == fp.roi_id == 'AOI-OKI-04' and result.get('fingerprint_details', {}).get('scene_ids') == evidence.scene_ids == http_ev.get('scene_ids') and result.get('map_actions', [{}])[0].get('payload', {}).get('bbox') == BBOX,
        'model_selected_science_tool': 'analyze_aoi' in completed or 'get_radar_fingerprint' in completed,
        'evidence_inspected': 'inspect_evidence' in completed,
        'story_five_frames': len(result.get('story', {}).get('frames', [])) == 5 and all(frame.get('evidence_ids') == [EVIDENCE_ID] for frame in result.get('story', {}).get('frames', [])),
        'causation_guard': any('cannot confirm wildfire' in text for text in result.get('scientific_assessment', {}).get('unknown', [])),
        'no_unauthorized_tool_success': result.get('unauthorized_tool_calls', 0) == 0,
        'provenance_pending_label': 'PROVENANCE PENDING' in result.get('data_notice', ''),
    }
    payload = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'provider': 'gemini',
               'model_id': result.get('model_name'), 'mode': 'NISAR CACHED EVIDENCE',
               'external_nasa_provenance_verified': False, 'latency_ms': latency_ms,
               'http_statuses': {'fingerprint': http_fp_response.status_code, 'evidence': http_ev_response.status_code,
                                 'agent': agent_response.status_code},
               'evidence_id': EVIDENCE_ID, 'aoi_id': 'AOI-OKI-04', 'hh_median_delta_db': hh,
               'hv_median_delta_db': hv, 'valid_pixel_count_recorded': evidence.valid_pixel_count,
               'checks': checks, 'trace': trace, 'token_usage': None, 'estimated_cost': None}
    (ROOT / 'docs/phase8_gemini_real_evidence_eval.json').write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    print('PHASE8_REAL_GEMINI', payload['status'], 'checks', sum(checks.values()), '/', len(checks),
          'latency_ms', latency_ms)


if __name__ == '__main__':
    main()
