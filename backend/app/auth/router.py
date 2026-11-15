"""Optional Google sign-in (`/api/auth/*`) and what a signed-in user saves (`/api/me/*`).

The site works without signing in; signing in only lets a user's own data be kept: their crop and
field per disaster, the assistant answers they got, and the relief estimates they chose to save. The browser
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
import json
from typing import Any, Callable, Literal

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.app.auth.store import CloudSqlUserStore, FarmerField, MemoryUserStore, Role, User, UserStore
from backend.app.schemas.taiwan_agro import TwAgroReliefEstimateRequest, TwAgroReliefEstimateResponse

COOKIE = "sar2action_session"
SESSION_TTL = timedelta(days=30)
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

Verifier = Callable[[str, str], dict[str, Any]]
# Runs the official relief schedule; returns the estimate and the schedule version it used.
Estimator = Callable[[TwAgroReliefEstimateRequest], tuple[TwAgroReliefEstimateResponse, str]]

CropKey = Literal["rice", "garlic", "peanut", "corn", "sweet_potato", "vegetables", "other"]
EVENT_ID = r"^[a-z0-9-]{1,64}$"
FIELD_ID = r"^[A-Z0-9-]{1,32}$"
MAX_REPLY_BYTES = 200_000


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


class FieldIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_id: str | None = Field(default=None, pattern=FIELD_ID)
    crop: CropKey
    crop_other: str | None = Field(default=None, max_length=40)
    cadastral: str | None = Field(default=None, max_length=64)


class FieldOut(FieldIn):
    event_id: str


class AssistantLogIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_id: str = Field(pattern=FIELD_ID)
    view: Role
    lang: Literal["zh", "en"] = "zh"
    question: str = Field(min_length=1, max_length=2000)
    reply: dict[str, Any]


class EstimateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_id: str = Field(pattern=FIELD_ID)
    crop_item_id: str = Field(min_length=1, max_length=64)
    area_ha: float = Field(gt=0, le=10_000)
    loss_threshold: Literal["unverified", "below_20_percent", "meets_20_percent", "article_12_simplified_exception"]


def _blank(text: str | None) -> str | None:
    return (text or "").strip() or None


def _me(user: User) -> Me:
    return Me(email=user.email, name=user.name, role=user.role)


def create_auth_router(
    client_id: str | None = None,
    store: UserStore | None = None,
    authority_emails: set[str] | None = None,
    verifier: Verifier = verify_google_id_token,
    estimator: Estimator | None = None,
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

    def _signed_in(request: Request) -> tuple[UserStore, User]:
        user = _session_user(request)
        if not user:
            raise HTTPException(401, "Not signed in.")
        return _require(), user

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

    @router.get("/api/me/fields")
    def my_fields(request: Request) -> list[FieldOut]:
        users, user = _signed_in(request)
        return [FieldOut(**f.__dict__) for f in users.list_fields(user.id)]

    @router.put("/api/me/fields/{event_id}")
    def put_my_field(body: FieldIn, request: Request, event_id: str = Path(pattern=EVENT_ID)) -> FieldOut:
        users, user = _signed_in(request)
        crop_other = _blank(body.crop_other) if body.crop == "other" else None
        if body.crop == "other" and not crop_other:
            raise HTTPException(422, "Name the crop when it is 'other'.")
        saved = users.put_field(user.id, FarmerField(event_id, body.field_id, body.crop, crop_other, _blank(body.cadastral)))
        return FieldOut(**saved.__dict__)

    @router.delete("/api/me/fields/{event_id}", status_code=204)
    def delete_my_field(request: Request, event_id: str = Path(pattern=EVENT_ID)) -> Response:
        users, user = _signed_in(request)
        users.delete_field(user.id, event_id)
        return Response(status_code=204)

    @router.post("/api/me/assistant-log", status_code=204)
    def log_answer(body: AssistantLogIn, request: Request) -> Response:
        users, user = _signed_in(request)
        if len(json.dumps(body.reply, ensure_ascii=False).encode()) > MAX_REPLY_BYTES:
            raise HTTPException(413, "Reply too large to keep.")
        law = body.reply.get("legal_authority", {}).get("applicable_law_version", {}).get("version")
        users.add_assistant_log(user.id, {**body.model_dump(), "law_version": law if isinstance(law, str) else None})
        return Response(status_code=204)

    @router.get("/api/me/assistant-log")
    def my_answers(request: Request, limit: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
        users, user = _signed_in(request)
        return users.list_assistant_log(user.id, limit)

    @router.post("/api/me/estimates")
    def save_estimate(body: EstimateIn, request: Request) -> TwAgroReliefEstimateResponse:
        users, user = _signed_in(request)
        if estimator is None:
            raise HTTPException(503, "Relief estimates are not available.")
        # Recomputed here from the official schedule, so a saved amount is never one the browser made up.
        result, schedule = estimator(
            TwAgroReliefEstimateRequest(
                crop_item_id=body.crop_item_id, assumed_approved_area_ha=body.area_ha, assumed_loss_threshold=body.loss_threshold
            )
        )
        users.add_estimate(
            user.id,
            {
                **body.model_dump(),
                "result_status": result.result_status,
                "amount_twd": result.conditional_reference_amount_twd if result.calculation_allowed else None,
                "schedule_version": schedule,
            },
        )
        return result

    @router.get("/api/me/estimates")
    def my_estimates(request: Request, limit: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
        users, user = _signed_in(request)
        return users.list_estimates(user.id, limit)

    return router


def router_from_env(estimator: Estimator | None = None) -> APIRouter:
    emails = set(os.environ.get("SAR2ACTION_AUTHORITY_EMAILS", "").split(","))
    return create_auth_router(os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip() or None, store_from_env(), emails, estimator=estimator)
