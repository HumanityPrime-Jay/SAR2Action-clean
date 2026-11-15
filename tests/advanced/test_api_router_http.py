"""HTTP-level checks for the advanced router: JSON bodies must reach the handlers."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.advanced.api_router import create_fastapi_router

app = FastAPI()
app.include_router(create_fastapi_router())
client = TestClient(app)


def test_legal_search_accepts_json_body():
    resp = client.post('/api/agent/legal-search', json={'query': '現金救助', 'top_k': 3, 'use_reranker': False})
    assert resp.status_code == 200, resp.text


def test_legal_query_accepts_json_body():
    resp = client.post('/api/agent/legal-query', json={'question': '大蒜受損可以申請現金救助嗎？', 'crop': '大蒜'})
    assert resp.status_code == 200, resp.text


def test_farmer_chat_accepts_json_body():
    resp = client.post('/api/farmer/chat', json={'message': '我的田受損了，可以申請救助嗎？', 'selected_field_id': 'YL-CAND-01'})
    assert resp.status_code == 200, resp.text


def test_body_validation_still_applies():
    resp = client.post('/api/farmer/chat', json={'message': ''})
    assert resp.status_code == 422
    assert resp.json()['detail'][0]['loc'] == ['body', 'message']


def test_farmer_chat_uses_registered_crop():
    r = client.post('/api/farmer/chat', json={'session_id': 'crop-test', 'message': '可以申請救助嗎？', 'crop': '大蒜'})
    assert r.status_code == 200
    body = r.json()
    assert body['session_state']['crop'] == '大蒜'
    assert body['intent'] == 'CHECK_RELIEF_PROGRAMS'
