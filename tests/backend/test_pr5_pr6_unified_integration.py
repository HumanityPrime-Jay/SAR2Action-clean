"""Unified integration tests for PR #4 + PR #5 + PR #6 on main FastAPI app."""
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_unified_farmer_chat_zh_and_en():
    r_zh = client.post(
        "/api/farmer/chat",
        json={
            "session_id": "unified-zh",
            "message": "我的蒜頭受損了，可以申請救助嗎？",
            "selected_field_id": "YL-CAND-01",
            "crop": "大蒜",
            "lang": "zh",
        },
    )
    assert r_zh.status_code == 200, r_zh.text
    body_zh = r_zh.json()
    assert body_zh["reply_language"] == "zh"
    assert body_zh["reply"]

    r_en = client.post(
        "/api/farmer/chat",
        json={
            "session_id": "unified-en",
            "message": "我的蒜頭受損了，可以申請救助嗎？",
            "selected_field_id": "YL-CAND-01",
            "crop": "大蒜",
            "lang": "en",
        },
    )
    assert r_en.status_code == 200, r_en.text
    body_en = r_en.json()
    assert body_en["reply_language"] in {"en", "zh"}
    assert body_en["reply"]


def test_unified_model_free_legal_retrieval_on_main_app():
    r = client.post(
        "/api/agent/legal-search",
        json={"query": "受災農民申請現金救助期限幾天", "top_k": 3, "use_reranker": False},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["retrieval_mode"] == "MODEL_FREE_DETERMINISTIC_SEMANTIC"
    assert payload["uses_neural_models"] is False
    assert payload["requires_gpu"] is False
    assert len(payload["hits"]) >= 1


def test_unified_tw05_and_relief_routes_no_405_or_422():
    cat = client.get("/api/tw-agro/relief-catalog")
    assert cat.status_code == 200, cat.text

    est = client.post(
        "/api/tw-agro/relief-estimate",
        json={
            "parcel_feature_id": 74,
            "crop_item_id": "grains_3_peanut_sweetpotato",
            "assumed_approved_area_ha": 0.2815,
            "assumed_loss_threshold": "meets_20_percent",
            "allow_cross_aoi_boundary_area": True,
        },
    )
    assert est.status_code == 200, est.text

    inv = client.post(
        "/api/agent/tw05/investigate",
        json={
            "parcel_feature_id": 74,
            "question": "請查詢坵塊 #74 的雷達與光學證據",
            "agent_mode": "deterministic",
            "session_id": "unified-tw05-74",
        },
    )
    assert inv.status_code == 200, inv.text
