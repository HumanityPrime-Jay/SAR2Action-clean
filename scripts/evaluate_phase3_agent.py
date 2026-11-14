"""HTTP smoke and fixed-question synthetic Agent evaluation against a running API."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path


BASE = 'http://127.0.0.1:8000'
CASE = 'case-flagship-oki-f2'
AOI = [105.28, -3.28, 105.48, -3.08]
SESSION = 'phase3-http-evaluation'
OUT = Path(__file__).resolve().parents[1] / 'docs' / 'phase3_agent_evaluation.json'


def call(method: str, path: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(BASE + path, data=body, method=method,
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def investigate(question: str) -> tuple[dict, float]:
    start = time.perf_counter()
    result = call('POST', '/api/agent/investigate', {
        'case_id': CASE, 'aoi_bbox_wgs84': AOI, 'session_id': SESSION,
        'query': question, 'intent': 'auto', 'data_mode': 'fixture'})
    elapsed = time.perf_counter() - start
    check(result['status'] == 'completed' and result['mode'] == 'fixture', 'investigation failed')
    check('SIMULATED DATA' in result['data_notice'], 'missing synthetic notice')
    check(len(result['ranked_regions']) == 3, 'expected three ranked regions')
    check(all(r['bbox_wgs84'][0] >= AOI[0] and r['bbox_wgs84'][2] <= AOI[2]
              and r['bbox_wgs84'][1] >= AOI[1] and r['bbox_wgs84'][3] <= AOI[3]
              for r in result['ranked_regions']), 'region outside AOI')
    check(all(claim['evidence_id'] in result['evidence_ids'] for claim in result['claims']),
          'unbacked claim')
    check(result['map_actions'][0]['type'] == 'map.focus_bbox', 'missing map action')
    return result, elapsed


def main() -> None:
    check(call('GET', '/api/health')['status'] == 'ok', 'health failed')
    status = call('GET', '/api/agent/status')
    cases = []
    for label, question in [
        ('Q1', '分析目前選取的區域。'),
        ('Q2', '找出變化最大的三個區域。'),
        ('Q3', '比較第一個與第二個區域。'),
        ('Q4', '解釋這個 Radar Fingerprint。'),
        ('Q5', '產生一份可以分享的地表變化故事。'),
    ]:
        started = time.perf_counter()
        result, _ = investigate(question)
        evidence = [call('GET', '/api/agent/spatial/evidence/' + eid)
                    for eid in result['evidence_ids']]
        check(all(item['data_kind'] == 'synthetic' and item['scene_ids'] == ['SIMULATED_T0', 'SIMULATED_T1']
                  and item['measurements']['unit'] == 'dB' for item in evidence), 'invalid evidence')
        expected_tools = {'analyze_spatial_changes', 'rank_change_regions', 'focus_change_region'}
        check(expected_tools.issubset({event['tool'] for event in result['trace']
                                       if event['status'] == 'complete'}), 'tool execution incomplete')
        if label == 'Q3':
            check(result['intent'] == 'compare' and result['comparison']['evidence_ids'] == result['evidence_ids'][:2],
                  'natural-language comparison did not execute')
            comparison = call('POST', '/api/agent/spatial/compare', {
                'first_evidence_id': result['evidence_ids'][0],
                'second_evidence_id': result['evidence_ids'][1]})
            check(comparison['evidence_ids'] == result['evidence_ids'][:2], 'comparison mismatch')
        if label == 'Q5':
            check(result['intent'] == 'story' and len(result['story']['frames']) == 5,
                  'natural-language story did not execute')
            story = call('POST', '/api/agent/story', {
                'session_id': SESSION, 'evidence_id': result['evidence_ids'][0],
                'locale': 'zh-TW', 'audience': 'public'})
            check(len(story['frames']) == 5 and all(frame['evidence_ids'] and
                  frame['scientific_limitations'] for frame in story['frames']), 'story incomplete')
        cases.append({'question': label, 'passed': True,
                      'duration_ms': round((time.perf_counter() - started) * 1000, 1),
                      'tool_success': True, 'evidence_valid': True, 'map_action': True})
    # Explicit live request must fail closed when no B-team manifest is configured.
    live_refused = False
    try:
        call('POST', '/api/agent/spatial/rank', {
            'case_id': CASE, 'aoi_bbox_wgs84': AOI, 'mode': 'live'})
    except urllib.error.HTTPError as error:
        live_refused = error.code == 422
    check(live_refused, 'live mode did not fail closed')
    report = {'data_mode': 'SYNTHETIC DEMO — NOT NASA OBSERVATIONS',
              'model_status': status['agent']['status'], 'questions': cases,
              'agent_tool_success_rate': 1.0, 'end_to_end_completion_rate': 1.0,
              'evidence_validity_rate': 1.0, 'live_missing_data_refused': live_refused}
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
