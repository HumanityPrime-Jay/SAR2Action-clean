"""Probe isolated Hermes chat without logging credentials or model text."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
env = (ROOT/'.phase4_hermes'/'.env').read_text(encoding='utf-8-sig').splitlines()
key = next(line.split('=', 1)[1] for line in env if line.startswith('API_SERVER_KEY='))
def check(path, payload=None):
    request = urllib.request.Request('http://127.0.0.1:8642'+path,
        data=None if payload is None else json.dumps(payload).encode(),
        method='GET' if payload is None else 'POST',
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+key})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code

health = check('/health')
models = check('/v1/models')
started = time.perf_counter()
chat = check('/v1/chat/completions', {'model': 'default', 'messages': [
    {'role': 'user', 'content': 'Reply with one word.'}], 'max_tokens': 16})
report = {'gateway_health_http': health, 'models_http': models, 'chat_http': chat,
          'chat_duration_ms': round((time.perf_counter()-started)*1000, 1),
          'inference_status': 'RUNNING' if chat == 200 else 'BLOCKED',
          'tool_calling_status': 'NOT_VERIFIED' if chat != 200 else 'REQUIRES_SEPARATE_TOOL_PROBE',
          'reason_if_blocked': 'Actual server context 4096 is below Hermes minimum 64000; see gateway log.'
                               if chat != 200 else None}
(ROOT/'docs'/'phase5_hermes_probe.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
