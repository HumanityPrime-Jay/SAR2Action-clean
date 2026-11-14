"""Capture one live model-planned GIS investigation without model reasoning or secrets."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
payload = {
    'case_id': 'case-flagship-oki-f2',
    'aoi_bbox_wgs84': [105.28, -3.28, 105.48, -3.08],
    'session_id': 'phase4-delivery-trace',
    'query': '找出目前選取範圍中變化最大的三個區域，比較它們，帶我查看證據。',
    'data_mode': 'fixture',
    'agent_mode': 'real',
}
request = urllib.request.Request(
    'http://127.0.0.1:8000/api/agent/investigate',
    data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST',
)
with urllib.request.urlopen(request, timeout=90) as response:
    result = json.load(response)
trace = {
    'status': result.get('status'),
    'agent_mode': result.get('agent_mode'),
    'model_name': result.get('model_name'),
    'model_provider': result.get('model_provider'),
    'data_notice': result.get('data_notice'),
    'evidence_ids': result.get('evidence_ids'),
    'has_comparison': bool(result.get('comparison')),
    'events': result.get('trace', []),
}
output = ROOT / 'docs' / 'phase4_real_agent_trace.json'
output.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in trace.items() if key != 'events'}, ensure_ascii=False))
raise SystemExit(0 if trace['status'] == 'completed' and trace['has_comparison'] else 1)
