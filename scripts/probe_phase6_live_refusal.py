"""Verify that both agent modes refuse missing live NISAR without substitution."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
results = {}
for mode in ('deterministic', 'real'):
    payload = {'case_id': 'case-flagship-oki-f2',
               'aoi_bbox_wgs84': [105.28, -3.28, 105.48, -3.08],
               'query': 'Rank real NISAR changes.', 'intent': 'rank',
               'session_id': f'phase6-live-refusal-{mode}',
               'data_mode': 'live', 'agent_mode': mode}
    request = urllib.request.Request('http://127.0.0.1:8000/api/agent/investigate',
        data=json.dumps(payload).encode(), method='POST',
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            code, body = response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        code, body = exc.code, json.load(exc)
    passed = (code == 422 and body.get('detail', {}).get('error_code') == 'LIVE_SPATIAL_DATA_UNAVAILABLE'
              if mode == 'deterministic' else
              code == 200 and body.get('status') == 'blocked' and not body.get('claims')
              and not body.get('evidence_ids') and 'synthetic data was not substituted' in body.get('reason', ''))
    results[mode] = {'http_status': code, 'status': body.get('status'),
                     'reason': body.get('reason') or body.get('detail'), 'passed': bool(passed)}
output = ROOT/'docs'/'phase6_live_refusal.json'
output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(results, ensure_ascii=False))
raise SystemExit(0 if all(row['passed'] for row in results.values()) else 1)
