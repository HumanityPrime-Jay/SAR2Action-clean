"""SQLite Legal Database (Phase D5) with FTS5 trigram index & versioned lookup."""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from backend.app.advanced.legal_rag.parser import LEGAL_DATA_DIR, build_legal_dataset

DB_PATH = LEGAL_DATA_DIR / "legal_rag.sqlite"


def build_sqlite_database(
    data_dir: Path | None = None,
    db_path: Path | None = None,
) -> Path:
    """Create and populate the SQLite legal database from manifest + articles.csv."""
    target_dir = data_dir or LEGAL_DATA_DIR
    sqlite_path = db_path or (target_dir / "legal_rag.sqlite")

    manifest_path = target_dir / "legal_source_manifest.json"
    csv_path = target_dir / "articles.csv"
    app_path = target_dir / "appendices" / "appendices_manifest.json"
    if not manifest_path.is_file() or not csv_path.is_file():
        build_legal_dataset(target_dir)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with csv_path.open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    appendices = json.loads(app_path.read_text(encoding="utf-8")) if app_path.is_file() else []

    if sqlite_path.exists():
        sqlite_path.unlink()

    conn = sqlite3.connect(str(sqlite_path))
    try:
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE legal_documents (
                law_id TEXT PRIMARY KEY,
                law_name TEXT NOT NULL,
                official_url TEXT NOT NULL,
                auxiliary_official_url TEXT,
                source_status TEXT NOT NULL
            );
            CREATE TABLE legal_source_versions (
                version_id TEXT PRIMARY KEY,
                law_id TEXT NOT NULL,
                revision_date TEXT NOT NULL,
                effective_from TEXT NOT NULL,
                effective_to TEXT,
                retrieved_at TEXT NOT NULL,
                source_sha256 TEXT NOT NULL
            );
            CREATE TABLE legal_articles (
                article_id TEXT PRIMARY KEY,
                law_id TEXT NOT NULL,
                version TEXT NOT NULL,
                article_no TEXT NOT NULL,
                chapter TEXT,
                text TEXT NOT NULL,
                normalized_text TEXT NOT NULL,
                effective_from TEXT NOT NULL,
                effective_to TEXT,
                source_url TEXT NOT NULL,
                source_sha256 TEXT NOT NULL
            );
            CREATE TABLE legal_provisions (
                citation_id TEXT PRIMARY KEY,
                law_id TEXT NOT NULL,
                version TEXT NOT NULL,
                article_id TEXT NOT NULL,
                paragraph_id TEXT,
                item_id TEXT,
                text TEXT NOT NULL,
                normalized_text TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_sha256 TEXT NOT NULL
            );
            CREATE TABLE legal_appendices (
                appendix_id TEXT PRIMARY KEY,
                law_id TEXT NOT NULL,
                version TEXT NOT NULL,
                title TEXT NOT NULL,
                source_pdf_url TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                raw_json TEXT NOT NULL
            );
            CREATE TABLE legal_cross_references (
                ref_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_article_id TEXT NOT NULL,
                target_article_no TEXT NOT NULL,
                relation_type TEXT NOT NULL
            );
            CREATE TABLE legal_query_audit (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT NOT NULL,
                query TEXT NOT NULL,
                event_date TEXT,
                resolved_version TEXT,
                top_citations_json TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE legal_articles_fts USING fts5(
                citation_id,
                article_id,
                text,
                tokenize='trigram'
            );
            """
        )

        cur.execute(
            "INSERT INTO legal_documents VALUES (?, ?, ?, ?, ?)",
            (
                manifest["law_id"],
                manifest["law_name"],
                manifest["official_url"],
                manifest.get("auxiliary_official_url"),
                manifest["source_status"],
            ),
        )
        cur.execute(
            "INSERT INTO legal_source_versions VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                f"{manifest['law_id']}@{manifest['revision_date']}",
                manifest["law_id"],
                manifest["revision_date"],
                manifest["effective_date"],
                "",
                manifest["retrieved_at"],
                manifest["source_sha256"],
            ),
        )

        for row in rows:
            is_article_level = not row["paragraph_id"] and not row["item_id"]
            if is_article_level:
                art_no = row["article_id"].split("-ARTICLE-")[-1]
                cur.execute(
                    "INSERT INTO legal_articles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row["article_id"],
                        row["law_id"],
                        row["version"],
                        art_no,
                        row["chapter"],
                        row["text"],
                        row["normalized_text"],
                        row["effective_from"],
                        row["effective_to"],
                        row["source_url"],
                        row["source_sha256"],
                    ),
                )
                # Extract intra-law cross references (e.g., 第十二條, 第六條)
                for ref in re.findall(r"第([一二三四五六七八九十0-9-]+)條", row["text"]):
                    cur.execute(
                        "INSERT INTO legal_cross_references (source_article_id, target_article_no, relation_type) VALUES (?, ?, ?)",
                        (row["article_id"], ref, "INTRA_LAW_REFERENCE"),
                    )
            else:
                cur.execute(
                    "INSERT INTO legal_provisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row["citation_id"],
                        row["law_id"],
                        row["version"],
                        row["article_id"],
                        row["paragraph_id"],
                        row["item_id"],
                        row["text"],
                        row["normalized_text"],
                        row["source_url"],
                        row["source_sha256"],
                    ),
                )
            cur.execute(
                "INSERT INTO legal_articles_fts (citation_id, article_id, text) VALUES (?, ?, ?)",
                (row["citation_id"], row["article_id"], row["text"]),
            )

        for app in appendices:
            cur.execute(
                "INSERT INTO legal_appendices VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    app["appendix_id"],
                    manifest["law_id"],
                    app["version"],
                    app["title"],
                    app["source_pdf_url"],
                    app["verification_status"],
                    json.dumps(app, ensure_ascii=False),
                ),
            )

        conn.commit()
    finally:
        conn.close()
    return sqlite_path


class LegalDatabase:
    """Parameterized read/audit wrapper around legal_rag.sqlite."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        if not self.db_path.is_file():
            build_sqlite_database(self.db_path.parent, self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_manifest_summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            doc = dict(conn.execute("SELECT * FROM legal_documents LIMIT 1").fetchone())
            ver = dict(conn.execute("SELECT * FROM legal_source_versions LIMIT 1").fetchone())
            art_cnt = conn.execute("SELECT COUNT(*) FROM legal_articles").fetchone()[0]
            prov_cnt = conn.execute("SELECT COUNT(*) FROM legal_provisions").fetchone()[0]
            apps = [dict(r) for r in conn.execute("SELECT appendix_id, version, title, source_pdf_url, verification_status FROM legal_appendices").fetchall()]
        return {
            **doc,
            "revision_date": ver["revision_date"],
            "effective_from": ver["effective_from"],
            "source_sha256": ver["source_sha256"],
            "article_count": art_cnt,
            "provision_count": prov_cnt,
            "appendices": apps,
        }

    def resolve_version_for_date(self, event_date: str | None) -> dict[str, Any]:
        """Verify if the stored revision covers event_date; otherwise return VERSION_NOT_VERIFIED."""
        with self._connect() as conn:
            ver = dict(conn.execute("SELECT * FROM legal_source_versions LIMIT 1").fetchone())
        if not event_date:
            return {
                "status": "VERIFIED_CURRENT_VERSION",
                "version": ver["revision_date"],
                "effective_from": ver["effective_from"],
                "source_sha256": ver["source_sha256"],
            }
        # Only dates >= effective_from are covered by this revision snapshot
        if event_date >= ver["effective_from"]:
            return {
                "status": "VERIFIED_FOR_EVENT_DATE",
                "version": ver["revision_date"],
                "effective_from": ver["effective_from"],
                "event_date": event_date,
                "source_sha256": ver["source_sha256"],
            }
        return {
            "status": "VERSION_NOT_VERIFIED",
            "version": None,
            "effective_from": ver["effective_from"],
            "event_date": event_date,
            "reason": (
                f"Event date {event_date} precedes the verified {ver['revision_date']} revision; "
                "historical amendment snapshot is not in the local verified database."
            ),
        }

    def get_article_exact(self, article_no: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM legal_articles WHERE article_no = ?",
                (article_no,),
            ).fetchone()
            return dict(row) if row else None

    def get_provision_exact(self, citation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM legal_provisions WHERE citation_id = ?",
                (citation_id,),
            ).fetchone()
            if row:
                return dict(row)
            row_art = conn.execute(
                "SELECT * FROM legal_articles WHERE article_id = ?",
                (citation_id,),
            ).fetchone()
            return dict(row_art) if row_art else None

    def list_all_articles(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM legal_articles ORDER BY rowid").fetchall()]

    def fts_search(self, query_terms: list[str], limit: int = 10) -> list[dict[str, Any]]:
        """Safe parameterized FTS5 trigram search with LIKE fallback for <3-char terms."""
        results: dict[str, dict[str, Any]] = {}
        with self._connect() as conn:
            for term in query_terms:
                clean = term.strip()
                if not clean:
                    continue
                if len(clean) >= 3:
                    # Quote term for FTS5 trigram literal match to avoid syntax/injection issues
                    escaped = '"' + clean.replace('"', '""') + '"'
                    try:
                        rows = conn.execute(
                            "SELECT f.citation_id, f.article_id, f.text, bm25(legal_articles_fts) AS rank "
                            "FROM legal_articles_fts f WHERE legal_articles_fts MATCH ? ORDER BY rank LIMIT ?",
                            (escaped, limit),
                        ).fetchall()
                    except sqlite3.OperationalError:
                        rows = []
                else:
                    rows = conn.execute(
                        "SELECT article_id AS citation_id, article_id, text, -1.0 AS rank "
                        "FROM legal_articles WHERE text LIKE ? LIMIT ?",
                        (f"%{clean}%", limit),
                    ).fetchall()
                for r in rows:
                    cid = r["article_id"]
                    if cid not in results:
                        results[cid] = dict(r)
        return list(results.values())[:limit]

    def log_query_audit(self, timestamp_utc: str, query: str, event_date: str | None, resolved_version: str | None, citations: list[str]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO legal_query_audit (timestamp_utc, query, event_date, resolved_version, top_citations_json) VALUES (?, ?, ?, ?, ?)",
                (timestamp_utc, query, event_date, resolved_version, json.dumps(citations, ensure_ascii=False)),
            )
            conn.commit()
