"""Capture a sanitized real-model scientific investigation for review."""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=ROOT/'docs'/'phase5_scientific_agent_trace.json')
parser.add_argument('--session-id', default='phase5-delivery-trace')
args = parser.parse_args()
payload = {'case_id': 'case-flagship-oki-f2',
           'aoi_bbox_wgs84': [105.28, -3.28, 105.48, -3.08],
           'session_id': args.session_id,
           'query': '找出目前選取範圍中變化最大的三個區域，比較它們，帶我查看證據。',
           'data_mode': 'fixture', 'agent_mode': 'real'}
request = urllib.request.Request('http://127.0.0.1:8000/api/agent/investigate',
    data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), method='POST',
    headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(request, timeout=90) as response:
    result = json.load(response)
artifact = {key: result.get(key) for key in ('status', 'agent_mode', 'model_name',
    'model_provider', 'data_notice', 'evidence_ids', 'investigation_plan',
    'scientific_assessment', 'narrative', 'trace')}
artifact['has_comparison'] = bool(result.get('comparison'))
output = args.output
output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': artifact['status'], 'has_comparison': artifact['has_comparison'],
                  'observed_count': len((artifact['scientific_assessment'] or {}).get('observed', [])),
                  'plan': artifact['investigation_plan']}, ensure_ascii=False))
raise SystemExit(0 if artifact['status'] == 'completed' and artifact['has_comparison'] else 1)
