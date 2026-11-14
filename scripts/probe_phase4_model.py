"""Record real local model tool-call metadata without hidden reasoning or keys."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.services.model_provider import ModelProvider
from backend.app.services.real_agent_runtime import NEXT_TOOLS


def handler(request: httpx.Request) -> httpx.Response:
    start = time.perf_counter()
    with httpx.Client(timeout=30) as client:
        response = client.post(str(request.url), content=request.content,
                               headers={'Content-Type': 'application/json'})
    data = response.json()
    choice = (data.get('choices') or [{}])[0]
    message = choice.get('message') or {}
    print(json.dumps({'http_status': response.status_code,
                      'finish_reason': choice.get('finish_reason'),
                      'message_fields': sorted(message),
                      'tool_names': [item.get('function', {}).get('name')
                                     for item in message.get('tool_calls') or []],
                      'usage': data.get('usage'),
                      'duration_ms': round((time.perf_counter() - start) * 1000, 1)}))
    return httpx.Response(response.status_code, json=data)


if __name__ == '__main__':
    os.environ['SAR2ACTION_MODEL_URL'] = 'http://127.0.0.1:8086/v1/chat/completions'
    os.environ['SAR2ACTION_MODEL_NAME'] = httpx.get('http://127.0.0.1:8086/v1/models').json()['data'][0]['id']
    os.environ['SAR2ACTION_MODEL_PROVIDER'] = 'openai_compatible'
    provider = ModelProvider(transport=httpx.MockTransport(handler))
    calls, _ = provider.choose_gis_tools(
        '找出目前選取範圍中變化最大的三個區域，比較它們，帶我查看證據。',
        NEXT_TOOLS, {'ranking_complete': True, 'completed_tools': ['rank_change_regions'],
                     'evidence_ids': ['E1', 'E2', 'E3']})
    print(json.dumps({'validated_calls': calls}, ensure_ascii=False))
