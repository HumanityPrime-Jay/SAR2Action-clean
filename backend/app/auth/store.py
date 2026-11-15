"""Users, sign-in sessions and what a signed-in user saves: Cloud SQL in production, in memory for local development and tests."""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Protocol

Role = Literal["farmer", "authority"]


@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str | None
    role: Role


@dataclass(frozen=True)
class FarmerField:
    """A farmer's own field for one disaster; one per event."""

    event_id: str
    field_id: str | None
    crop: str
    crop_other: str | None
    cadastral: str | None


def _hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


class UserStore(Protocol):
    def upsert_google_user(self, google_sub: str, email: str, name: str | None, role: Role) -> User: ...
    def create_session(self, user_id: str, ttl: timedelta) -> str: ...
    def user_for_session(self, token: str) -> User | None: ...
    def delete_session(self, token: str) -> None: ...
    def delete_user(self, user_id: str) -> None: ...
    def list_fields(self, user_id: str) -> list[FarmerField]: ...
    def put_field(self, user_id: str, field: FarmerField) -> FarmerField: ...
    def delete_field(self, user_id: str, event_id: str) -> None: ...
    def add_assistant_log(self, user_id: str, entry: dict[str, Any]) -> None: ...
    def list_assistant_log(self, user_id: str, limit: int) -> list[dict[str, Any]]: ...
    def add_estimate(self, user_id: str, entry: dict[str, Any]) -> None: ...
    def list_estimates(self, user_id: str, limit: int) -> list[dict[str, Any]]: ...


class MemoryUserStore:
    """Process-local store; everything is lost on restart."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users: dict[str, User] = {}
        self._by_sub: dict[str, str] = {}
        self._sessions: dict[bytes, tuple[str, datetime]] = {}
        self._fields: dict[tuple[str, str], FarmerField] = {}
        self._logs: dict[str, list[dict[str, Any]]] = {}
        self._estimates: dict[str, list[dict[str, Any]]] = {}

    def upsert_google_user(self, google_sub: str, email: str, name: str | None, role: Role) -> User:
        with self._lock:
            user_id = self._by_sub.get(google_sub) or str(uuid.uuid4())
            self._by_sub[google_sub] = user_id
            self._users[user_id] = User(user_id, email, name, role)
            return self._users[user_id]

    def create_session(self, user_id: str, ttl: timedelta) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[_hash(token)] = (user_id, datetime.now(timezone.utc) + ttl)
        return token

    def user_for_session(self, token: str) -> User | None:
        with self._lock:
            hit = self._sessions.get(_hash(token))
            if not hit or hit[1] <= datetime.now(timezone.utc):
                return None
            return self._users.get(hit[0])

    def delete_session(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(_hash(token), None)

    def delete_user(self, user_id: str) -> None:
        with self._lock:
            self._users.pop(user_id, None)
            self._by_sub = {s: u for s, u in self._by_sub.items() if u != user_id}
            self._sessions = {h: v for h, v in self._sessions.items() if v[0] != user_id}
            self._fields = {k: v for k, v in self._fields.items() if k[0] != user_id}
            self._logs.pop(user_id, None)
            self._estimates.pop(user_id, None)

    def list_fields(self, user_id: str) -> list[FarmerField]:
        with self._lock:
            return [f for (u, _), f in self._fields.items() if u == user_id]

    def put_field(self, user_id: str, field: FarmerField) -> FarmerField:
        with self._lock:
            self._fields[(user_id, field.event_id)] = field
            return field

    def delete_field(self, user_id: str, event_id: str) -> None:
        with self._lock:
            self._fields.pop((user_id, event_id), None)

    def _add(self, table: dict[str, list[dict[str, Any]]], user_id: str, entry: dict[str, Any]) -> None:
        with self._lock:
            table.setdefault(user_id, []).insert(0, {**entry, "created_at": datetime.now(timezone.utc).isoformat()})

    def add_assistant_log(self, user_id: str, entry: dict[str, Any]) -> None:
        self._add(self._logs, user_id, entry)

    def list_assistant_log(self, user_id: str, limit: int) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._logs.get(user_id, [])[:limit])

    def add_estimate(self, user_id: str, entry: dict[str, Any]) -> None:
        self._add(self._estimates, user_id, entry)

    def list_estimates(self, user_id: str, limit: int) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._estimates.get(user_id, [])[:limit])


class CloudSqlUserStore:
    """PostgreSQL on Cloud SQL through the Cloud SQL connector with IAM database auth (no password)."""

    def __init__(self, instance: str, db: str, iam_user: str) -> None:
        self._instance, self._db, self._iam_user = instance, db, iam_user
        self._lock = threading.Lock()
        self._connector = None
        self._conn = None

    def _connect(self):
        from google.cloud.sql.connector import Connector  # imported lazily: only production needs it

        if self._connector is None:
            self._connector = Connector()
        return self._connector.connect(self._instance, "pg8000", user=self._iam_user, db=self._db, enable_iam_auth=True)

    def _run(self, sql: str, args: tuple = (), fetch: bool = False) -> list[tuple]:
        # One shared connection, reopened once if it went stale; traffic is low.
        with self._lock:
            for attempt in (0, 1):
                try:
                    if self._conn is None:
                        self._conn = self._connect()
                    cur = self._conn.cursor()
                    cur.execute(sql, args)
                    rows = cur.fetchall() if fetch else []
                    self._conn.commit()
                    return rows
                except Exception:
                    try:
                        if self._conn is not None:
                            self._conn.close()
                    except Exception:
                        pass
                    self._conn = None
                    if attempt:
                        raise
        return []

    def upsert_google_user(self, google_sub: str, email: str, name: str | None, role: Role) -> User:
        rows = self._run(
            """INSERT INTO users (google_sub, email, name, role) VALUES (%s, %s, %s, %s)
               ON CONFLICT (google_sub) DO UPDATE
               SET email = EXCLUDED.email, name = EXCLUDED.name, role = EXCLUDED.role, last_login_at = now()
               RETURNING id::text, email, name, role""",
            (google_sub, email, name, role),
            fetch=True,
        )
        return User(*rows[0])

    def create_session(self, user_id: str, ttl: timedelta) -> str:
        token = secrets.token_urlsafe(32)
        self._run(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (%s, %s::uuid, %s)",
            (_hash(token), user_id, datetime.now(timezone.utc) + ttl),
        )
        return token

    def user_for_session(self, token: str) -> User | None:
        rows = self._run(
            """SELECT u.id::text, u.email, u.name, u.role FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = %s AND s.expires_at > now()""",
            (_hash(token),),
            fetch=True,
        )
        return User(*rows[0]) if rows else None

    def delete_session(self, token: str) -> None:
        self._run("DELETE FROM sessions WHERE token_hash = %s", (_hash(token),))

    def delete_user(self, user_id: str) -> None:
        # Sessions and every user-owned row go with the user (ON DELETE CASCADE).
        self._run("DELETE FROM users WHERE id = %s::uuid", (user_id,))

    def list_fields(self, user_id: str) -> list[FarmerField]:
        rows = self._run(
            "SELECT event_id, field_id, crop, crop_other, cadastral FROM farmer_fields WHERE user_id = %s::uuid ORDER BY updated_at DESC",
            (user_id,),
            fetch=True,
        )
        return [FarmerField(*r) for r in rows]

    def put_field(self, user_id: str, field: FarmerField) -> FarmerField:
        rows = self._run(
            """INSERT INTO farmer_fields (user_id, event_id, field_id, crop, crop_other, cadastral)
               VALUES (%s::uuid, %s, %s, %s, %s, %s)
               ON CONFLICT (user_id, event_id) DO UPDATE
               SET field_id = EXCLUDED.field_id, crop = EXCLUDED.crop, crop_other = EXCLUDED.crop_other,
                   cadastral = EXCLUDED.cadastral, updated_at = now()
               RETURNING event_id, field_id, crop, crop_other, cadastral""",
            (user_id, field.event_id, field.field_id, field.crop, field.crop_other, field.cadastral),
            fetch=True,
        )
        return FarmerField(*rows[0])

    def delete_field(self, user_id: str, event_id: str) -> None:
        self._run("DELETE FROM farmer_fields WHERE user_id = %s::uuid AND event_id = %s", (user_id, event_id))

    def add_assistant_log(self, user_id: str, entry: dict[str, Any]) -> None:
        self._run(
            """INSERT INTO assistant_log (user_id, field_id, view, lang, question, reply, law_version)
               VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb, %s)""",
            (user_id, entry["field_id"], entry["view"], entry["lang"], entry["question"], json.dumps(entry["reply"], ensure_ascii=False), entry["law_version"]),
        )

    def list_assistant_log(self, user_id: str, limit: int) -> list[dict[str, Any]]:
        # The stored reply is left out of the list; it can be large.
        rows = self._run(
            """SELECT field_id, view, lang, question, law_version, created_at FROM assistant_log
               WHERE user_id = %s::uuid ORDER BY created_at DESC LIMIT %s""",
            (user_id, limit),
            fetch=True,
        )
        keys = ("field_id", "view", "lang", "question", "law_version", "created_at")
        return [{**dict(zip(keys, r)), "created_at": r[5].isoformat()} for r in rows]

    def add_estimate(self, user_id: str, entry: dict[str, Any]) -> None:
        self._run(
            """INSERT INTO relief_estimates
               (user_id, field_id, crop_item_id, area_ha, loss_threshold, result_status, amount_twd, schedule_version)
               VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, entry["field_id"], entry["crop_item_id"], entry["area_ha"], entry["loss_threshold"], entry["result_status"], entry["amount_twd"], entry["schedule_version"]),
        )

    def list_estimates(self, user_id: str, limit: int) -> list[dict[str, Any]]:
        rows = self._run(
            """SELECT field_id, crop_item_id, area_ha, loss_threshold, result_status, amount_twd, schedule_version, created_at
               FROM relief_estimates WHERE user_id = %s::uuid ORDER BY created_at DESC LIMIT %s""",
            (user_id, limit),
            fetch=True,
        )
        keys = ("field_id", "crop_item_id", "area_ha", "loss_threshold", "result_status", "amount_twd", "schedule_version", "created_at")
        return [{**dict(zip(keys, r)), "area_ha": float(r[2]), "created_at": r[7].isoformat()} for r in rows]
