"""Users and sign-in sessions: Cloud SQL in production, in memory for local development and tests."""

from __future__ import annotations

import hashlib
import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Protocol

Role = Literal["farmer", "authority"]


@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str | None
    role: Role


def _hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


class UserStore(Protocol):
    def upsert_google_user(self, google_sub: str, email: str, name: str | None, role: Role) -> User: ...
    def create_session(self, user_id: str, ttl: timedelta) -> str: ...
    def user_for_session(self, token: str) -> User | None: ...
    def delete_session(self, token: str) -> None: ...
    def delete_user(self, user_id: str) -> None: ...


class MemoryUserStore:
    """Process-local store; everything is lost on restart."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users: dict[str, User] = {}
        self._by_sub: dict[str, str] = {}
        self._sessions: dict[bytes, tuple[str, datetime]] = {}

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
