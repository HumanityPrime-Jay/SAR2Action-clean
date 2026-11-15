from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.router import create_auth_router
from backend.app.auth.store import MemoryUserStore
from backend.app.schemas.taiwan_agro import TwAgroReliefEstimateRequest
from backend.app.services.taiwan_agro_service import TaiwanAgroService

CLIENT_ID = "test-client.apps.googleusercontent.com"
CREDENTIAL = "x" * 40
SERVICE = TaiwanAgroService()


def estimator(req: TwAgroReliefEstimateRequest):
    return SERVICE.compute_relief_estimate(req), SERVICE.get_relief_catalog().schedule_version_id


def signed_in(sub="g-1", store=None):
    claims = {"iss": "accounts.google.com", "aud": CLIENT_ID, "sub": sub, "email": f"{sub}@example.com", "email_verified": True}
    app = FastAPI()
    app.include_router(create_auth_router(CLIENT_ID, store or MemoryUserStore(), set(), lambda t, cid: claims, estimator))
    c = TestClient(app)
    assert c.post("/api/auth/google", json={"credential": CREDENTIAL}).status_code == 200
    return c


def test_everything_under_me_needs_sign_in():
    app = FastAPI()
    app.include_router(create_auth_router(CLIENT_ID, MemoryUserStore(), set(), lambda t, cid: {}, estimator))
    c = TestClient(app)
    assert c.get("/api/me/fields").status_code == 401
    assert c.put("/api/me/fields/champi-2026-yunlin", json={"crop": "rice"}).status_code == 401
    assert c.get("/api/me/assistant-log").status_code == 401
    assert c.post("/api/me/estimates", json={"field_id": "YL-CAND-01", "crop_item_id": "veg_6", "area_ha": 1, "loss_threshold": "meets_20_percent"}).status_code == 401


def test_one_field_per_event_with_optional_cadastral():
    c = signed_in()
    r = c.put("/api/me/fields/champi-2026-yunlin", json={"crop": "garlic", "cadastral": "  "})
    assert r.json() == {"event_id": "champi-2026-yunlin", "field_id": None, "crop": "garlic", "crop_other": None, "cadastral": None}
    c.put("/api/me/fields/champi-2026-yunlin", json={"crop": "other", "crop_other": "芋頭", "field_id": "YL-CAND-02", "cadastral": "海口段 123"})
    assert c.get("/api/me/fields").json() == [
        {"event_id": "champi-2026-yunlin", "field_id": "YL-CAND-02", "crop": "other", "crop_other": "芋頭", "cadastral": "海口段 123"}
    ]
    assert c.delete("/api/me/fields/champi-2026-yunlin").status_code == 204
    assert c.get("/api/me/fields").json() == []


def test_field_input_is_validated():
    c = signed_in()
    assert c.put("/api/me/fields/champi-2026-yunlin", json={"crop": "other"}).status_code == 422
    assert c.put("/api/me/fields/champi-2026-yunlin", json={"crop": "wheat"}).status_code == 422
    assert c.put("/api/me/fields/Bad%20Id", json={"crop": "rice"}).status_code == 422
    assert c.put("/api/me/fields/champi-2026-yunlin", json={"crop": "rice", "field_id": "x;drop"}).status_code == 422


def test_users_only_see_their_own_data():
    store = MemoryUserStore()
    a, b = signed_in("g-a", store), signed_in("g-b", store)
    a.put("/api/me/fields/champi-2026-yunlin", json={"crop": "rice"})
    a.post("/api/me/assistant-log", json={"field_id": "YL-CAND-01", "view": "farmer", "question": "q", "reply": {}})
    assert b.get("/api/me/fields").json() == []
    assert b.get("/api/me/assistant-log").json() == []


def test_assistant_log_keeps_question_and_law_version():
    c = signed_in()
    reply = {"legal_authority": {"applicable_law_version": {"version": "LAW-1"}}}
    assert c.post("/api/me/assistant-log", json={"field_id": "YL-CAND-01", "view": "authority", "lang": "en", "question": "Eligible?", "reply": reply}).status_code == 204
    [entry] = c.get("/api/me/assistant-log").json()
    assert entry["question"] == "Eligible?" and entry["law_version"] == "LAW-1" and entry["view"] == "authority"
    big = {"x": "a" * 250_000}
    assert c.post("/api/me/assistant-log", json={"field_id": "YL-CAND-01", "view": "farmer", "question": "q", "reply": big}).status_code == 413


def test_saved_estimate_is_recomputed_on_the_server():
    c = signed_in()
    item = SERVICE.get_relief_catalog().items
    rated = next(i for i in item if i.rate_twd_per_ha)
    r = c.post("/api/me/estimates", json={"field_id": "YL-CAND-01", "crop_item_id": rated.item_id, "area_ha": 0.5, "loss_threshold": "meets_20_percent"})
    assert r.status_code == 200
    expected = estimator(TwAgroReliefEstimateRequest(crop_item_id=rated.item_id, assumed_approved_area_ha=0.5, assumed_loss_threshold="meets_20_percent"))[0]
    [saved] = c.get("/api/me/estimates").json()
    assert saved["amount_twd"] == expected.conditional_reference_amount_twd
    assert saved["result_status"] == expected.result_status
    assert saved["schedule_version"] == SERVICE.get_relief_catalog().schedule_version_id


def test_blocked_estimate_is_saved_without_an_amount():
    c = signed_in()
    c.post("/api/me/estimates", json={"field_id": "YL-CAND-01", "crop_item_id": "unknown_crop", "area_ha": 0.5, "loss_threshold": "meets_20_percent"})
    [saved] = c.get("/api/me/estimates").json()
    assert saved["amount_twd"] is None and saved["result_status"].startswith("BLOCKED")


def test_deleting_the_account_removes_saved_data():
    store = MemoryUserStore()
    c = signed_in("g-x", store)
    c.put("/api/me/fields/champi-2026-yunlin", json={"crop": "rice"})
    c.post("/api/me/assistant-log", json={"field_id": "YL-CAND-01", "view": "farmer", "question": "q", "reply": {}})
    assert c.delete("/api/me").status_code == 204
    again = signed_in("g-x", store)
    assert again.get("/api/me/fields").json() == [] and again.get("/api/me/assistant-log").json() == []
