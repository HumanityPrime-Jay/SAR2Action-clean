"""Write an evidence-based demo checklist; keep live and synthetic readiness separate."""
from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8000'


def http(url: str, payload: dict | None = None) -> tuple[int, dict | None]:
    request = urllib.request.Request(url, method='POST' if payload is not None else 'GET',
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            try:
                return response.status, json.loads(body)
            except ValueError:
                return response.status, None
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return 0, None


def main() -> int:
    checks: dict[str, dict] = {}
    checks['backend_running'] = {'status': 'PASS' if http(BASE+'/api/health')[0] == 200 else 'FAIL'}
    checks['frontend_running'] = {'status': 'PASS' if http('http://127.0.0.1:5173/')[0] == 200 else 'FAIL'}
    model_http, _ = http('http://127.0.0.1:8086/health')
    agent_http, agent = http(BASE+'/api/agent/status')
    checks['model_running'] = {'status': 'PASS' if model_http == 200 and agent_http == 200 and
                               agent and agent.get('agent', {}).get('status') == 'online' else 'FAIL',
                               'provider': 'local llama.cpp OpenAI-compatible'}
    inventory_path = ROOT/'docs'/'phase6_nisar_data_validation.json'
    inventory = json.loads(inventory_path.read_text(encoding='utf-8')) if inventory_path.is_file() else {}
    live_ready = inventory.get('status') == 'CONTRACT_VALID_PENDING_SCIENCE'
    checks['scene_data_available'] = {'status': 'CONTRACT_ONLY' if live_ready else 'BLOCKED',
                                      'reason': 'Signed change GeoTIFF and valid live manifest are absent.'
                                      if not live_ready else 'Scientific spot checks and live E2E remain required.'}

    if checks['backend_running']['status'] == 'PASS':
        payload = {'case_id': 'case-flagship-oki-f2',
                   'aoi_bbox_wgs84': [105.28, -3.28, 105.48, -3.08],
                   'session_id': 'phase6-readiness', 'query': 'Rank the top three regions.',
                   'data_mode': 'fixture', 'agent_mode': 'deterministic'}
        code, result = http(BASE+'/api/agent/investigate', payload)
        evidence_id = (result or {}).get('evidence_ids', [None])[0]
        evidence_code, evidence = http(BASE+'/api/agent/spatial/evidence/'+str(evidence_id)) if evidence_id else (0, None)
        checks['evidence_api_healthy'] = {'status': 'PASS_SYNTHETIC_ONLY' if code == evidence_code == 200
            and evidence and evidence.get('evidence_id') == evidence_id else 'FAIL'}
        story_code, story = http(BASE+'/api/agent/story', {'session_id': 'phase6-readiness',
            'evidence_id': evidence_id, 'locale': 'en', 'audience': 'scientific'}) if evidence_id else (0, None)
        checks['story_builder_ready'] = {'status': 'PASS_SYNTHETIC_ONLY' if story_code == 200 and story
            and len(story.get('frames', [])) == 5 and story.get('evidence_ids') == [evidence_id] else 'FAIL'}
    else:
        checks['evidence_api_healthy'] = {'status': 'FAIL'}
        checks['story_builder_ready'] = {'status': 'FAIL'}

    try:
        chrome = subprocess.run(['npm.cmd', 'run', 'test:e2e', '--', '--project=chrome'],
                                cwd=ROOT/'frontend', capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=150)
        matched = re.search(r'(\d+) passed', chrome.stdout or '')
        checks['maplibre_ready'] = {'status': 'PASS_SYNTHETIC_E2E' if chrome.returncode == 0 and matched
            and int(matched.group(1)) >= 3 else 'FAIL', 'chrome_tests_passed': int(matched.group(1)) if matched else 0}
    except (OSError, subprocess.TimeoutExpired):
        checks['maplibre_ready'] = {'status': 'FAIL', 'chrome_tests_passed': 0}

    synthetic_ready = all(checks[key]['status'].startswith('PASS') for key in
                          ('backend_running', 'frontend_running', 'model_running',
                           'evidence_api_healthy', 'story_builder_ready', 'maplibre_ready'))
    report = {'live_competition_demo': 'BLOCKED' if not live_ready else 'REQUIRES_LIVE_E2E',
              'synthetic_demo': 'READY' if synthetic_ready else 'FAIL',
              'checks': checks, 'synthetic_notice': 'SIMULATED DATA — NOT NASA OBSERVATIONS'}
    output = ROOT/'docs'/'phase6_demo_readiness.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0 if synthetic_ready else 1


if __name__ == '__main__':
    raise SystemExit(main())
