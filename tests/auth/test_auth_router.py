from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.router import COOKIE, create_auth_router
from backend.app.auth.store import MemoryUserStore

CLIENT_ID = "test-client.apps.googleusercontent.com"
CREDENTIAL = "x" * 40


def claims(**over):
    base = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "g-123", "email": "farmer@example.com", "email_verified": True, "name": "A Farmer"}
    return {**base, **over}


def client(verify=lambda token, cid: claims(), **kw):
    app = FastAPI()
    app.include_router(create_auth_router(CLIENT_ID, MemoryUserStore(), kw.get("authority", set()), verify))
    return TestClient(app)


def test_sign_in_is_off_without_configuration():
    app = FastAPI()
    app.include_router(create_auth_router(None, None))
    c = TestClient(app)
    assert c.get("/api/auth/config").json() == {"enabled": False, "google_client_id": None}
    assert c.post("/api/auth/google", json={"credential": CREDENTIAL}).status_code == 503
    assert c.get("/api/me").status_code == 401


def test_config_exposes_only_the_public_client_id():
    assert client().get("/api/auth/config").json() == {"enabled": True, "google_client_id": CLIENT_ID}


def test_login_sets_an_httponly_session_cookie_and_me_works():
    c = client()
    r = c.post("/api/auth/google", json={"credential": CREDENTIAL})
    assert r.status_code == 200
    assert r.json() == {"email": "farmer@example.com", "name": "A Farmer", "role": "farmer"}
    cookie = r.headers["set-cookie"]
    assert COOKIE in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert c.get("/api/me").json()["email"] == "farmer@example.com"


def test_cookie_is_secure_behind_https():
    r = client().post("/api/auth/google", json={"credential": CREDENTIAL}, headers={"x-forwarded-proto": "https"})
    assert "Secure" in r.headers["set-cookie"]


def test_authority_role_only_for_listed_emails_case_insensitive():
    c = client(authority={"Officer@Example.com"}, verify=lambda t, cid: claims(email="officer@example.com", sub="g-9"))
    assert c.post("/api/auth/google", json={"credential": CREDENTIAL}).json()["role"] == "authority"


def test_rejects_bad_or_foreign_tokens():
    def boom(token, cid):
        raise ValueError("bad signature")

    assert client(verify=boom).post("/api/auth/google", json={"credential": CREDENTIAL}).status_code == 401
    assert client(verify=lambda t, cid: claims(aud="someone-else")).post("/api/auth/google", json={"credential": CREDENTIAL}).status_code == 401
    assert client(verify=lambda t, cid: claims(iss="evil.example")).post("/api/auth/google", json={"credential": CREDENTIAL}).status_code == 401
    assert client(verify=lambda t, cid: claims(email_verified=False)).post("/api/auth/google", json={"credential": CREDENTIAL}).status_code == 401


def test_logout_ends_the_session():
    c = client()
    c.post("/api/auth/google", json={"credential": CREDENTIAL})
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/me").status_code == 401


def test_delete_me_removes_the_user_and_session():
    c = client()
    c.post("/api/auth/google", json={"credential": CREDENTIAL})
    assert c.delete("/api/me").status_code == 204
    assert c.get("/api/me").status_code == 401


def test_me_without_cookie_is_401():
    assert client().get("/api/me").status_code == 401
