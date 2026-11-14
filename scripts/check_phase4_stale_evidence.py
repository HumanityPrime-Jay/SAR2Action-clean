"""Real-model AOI switch followed by a stale Evidence ID story refusal."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path


BASE = 'http://127.0.0.1:8000'
CASE = 'case-flagship-oki-f2'
SESSION = 'phase4-stale-verification'


def post(path: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(BASE + path, data=json.dumps(payload, ensure_ascii=False).encode(),
                                     method='POST', headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


first = post('/api/agent/investigate', {'case_id': CASE,
    'aoi_bbox_wgs84': [105.28, -3.28, 105.48, -3.08],
    'session_id': SESSION, 'query': 'Rank the three largest regions.',
    'data_mode': 'fixture', 'agent_mode': 'real'})[1]
second = post('/api/agent/investigate', {'case_id': CASE,
    'aoi_bbox_wgs84': [105.30, -3.26, 105.47, -3.10],
    'session_id': SESSION, 'query': 'The AOI changed; rank the new region.',
    'data_mode': 'fixture', 'agent_mode': 'real'})[1]
old_id = first.get('evidence_ids', [None])[0]
status, _ = post('/api/agent/story', {'session_id': SESSION, 'evidence_id': old_id,
                                      'locale': 'en', 'audience': 'public'})
passed = first.get('status') == second.get('status') == 'completed' and old_id not in second.get('evidence_ids', []) and status == 422
report = {'real_model_aois_completed': first.get('status') == second.get('status') == 'completed',
          'old_evidence_id': old_id, 'old_id_in_new_aoi': old_id in second.get('evidence_ids', []),
          'stale_story_http_status': status, 'passed': passed}
output = Path(__file__).resolve().parents[1] / 'docs' / 'phase4_stale_evidence_check.json'
output.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
raise SystemExit(0 if passed else 1)
