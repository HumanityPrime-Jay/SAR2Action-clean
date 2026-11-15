"""Optional Google sign-in (`/api/auth/*`, `/api/me`).

The site works without signing in; signing in only lets a user's own data be kept. The browser
gets a Google ID token from Google Identity Services, the backend verifies it, and answers with
an HttpOnly session cookie. Configuration (all optional; sign-in is off unless the first two are set):

- GOOGLE_OAUTH_CLIENT_ID: the web client ID (public, not a secret)
- SAR2ACTION_USER_STORE: "cloudsql" or "memory" (local development only)
- SAR2ACTION_CLOUDSQL_INSTANCE, SAR2ACTION_DB_NAME, SAR2ACTION_DB_IAM_USER: for "cloudsql"
- SAR2ACTION_AUTHORITY_EMAILS: comma-separated Google accounts given the authority role
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.app.auth.store import CloudSqlUserStore, MemoryUserStore, Role, User, UserStore

COOKIE = "sar2action_session"
SESSION_TTL = timedelta(days=30)
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

Verifier = Callable[[str, str], dict[str, Any]]


def verify_google_id_token(credential: str, client_id: str) -> dict[str, Any]:
    """Checks signature, audience, expiry and issuer against Google's public keys."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)


def store_from_env() -> UserStore | None:
    kind = os.environ.get("SAR2ACTION_USER_STORE", "").strip().lower()
    if kind == "memory":
        return MemoryUserStore()
    if kind == "cloudsql":
        return CloudSqlUserStore(
            os.environ["SAR2ACTION_CLOUDSQL_INSTANCE"],
            os.environ.get("SAR2ACTION_DB_NAME", "sar2action"),
            os.environ["SAR2ACTION_DB_IAM_USER"],
        )
    return None


class GoogleLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential: str = Field(min_length=20, max_length=4096)


class Me(BaseModel):
    email: str
    name: str | None
    role: Role


def _me(user: User) -> Me:
    return Me(email=user.email, name=user.name, role=user.role)


def create_auth_router(
    client_id: str | None = None,
    store: UserStore | None = None,
    authority_emails: set[str] | None = None,
    verifier: Verifier = verify_google_id_token,
) -> APIRouter:
    router = APIRouter(tags=["Auth"])
    enabled = bool(client_id and store)
    authorities = {e.strip().lower() for e in (authority_emails or set()) if e.strip()}

    def _require() -> UserStore:
        if not enabled or store is None:
            raise HTTPException(503, "Sign-in is not enabled on this server.")
        return store

    def _session_user(request: Request) -> User | None:
        token = request.cookies.get(COOKIE)
        return _require().user_for_session(token) if token else None

    def _set_cookie(request: Request, response: Response, token: str) -> None:
        # Cloud Run terminates TLS in front of the app, so trust its forwarded scheme.
        https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
        response.set_cookie(COOKIE, token, max_age=int(SESSION_TTL.total_seconds()), httponly=True, secure=https, samesite="lax", path="/")

    @router.get("/api/auth/config")
    def auth_config() -> dict[str, Any]:
        return {"enabled": enabled, "google_client_id": client_id if enabled else None}

    @router.post("/api/auth/google")
    def login(body: GoogleLogin, request: Request, response: Response) -> Me:
        users = _require()
        try:
            claims = verifier(body.credential, client_id or "")
        except Exception:
            raise HTTPException(401, "Google sign-in could not be verified.")
        if claims.get("iss") not in GOOGLE_ISSUERS or claims.get("aud") != client_id:
            raise HTTPException(401, "Google sign-in could not be verified.")
        email = str(claims.get("email") or "")
        if not email or claims.get("email_verified") is not True:
            raise HTTPException(401, "The Google account has no verified email.")
        # Re-evaluated at every sign-in, so removing an address from the list takes the role away.
        role: Role = "authority" if email.lower() in authorities else "farmer"
        user = users.upsert_google_user(str(claims["sub"]), email, claims.get("name"), role)
        _set_cookie(request, response, users.create_session(user.id, SESSION_TTL))
        return _me(user)

    @router.post("/api/auth/logout", status_code=204)
    def logout(request: Request, response: Response) -> Response:
        token = request.cookies.get(COOKIE)
        if token and enabled and store is not None:
            store.delete_session(token)
        response.delete_cookie(COOKIE, path="/")
        response.status_code = 204
        return response

    @router.get("/api/me")
    def me(request: Request) -> Me:
        user = _session_user(request)
        if not user:
            raise HTTPException(401, "Not signed in.")
        return _me(user)

    @router.delete("/api/me", status_code=204)
    def delete_me(request: Request, response: Response) -> Response:
        user = _session_user(request)
        if not user:
            raise HTTPException(401, "Not signed in.")
        _require().delete_user(user.id)
        response.delete_cookie(COOKIE, path="/")
        response.status_code = 204
        return response

    return router


def router_from_env() -> APIRouter:
    emails = set(os.environ.get("SAR2ACTION_AUTHORITY_EMAILS", "").split(","))
    return create_auth_router(os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip() or None, store_from_env(), emails)
