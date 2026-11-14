"""Official MOJ LawAll HTML parser for《農業天然災害救助辦法》(PCODE=M0090019).

Builds:
- data/legal/agricultural_disaster_relief/legal_source_manifest.json
- data/legal/agricultural_disaster_relief/articles.csv
- data/legal/agricultural_disaster_relief/appendices/appendices_manifest.json
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LAW_ID = "M0090019"
LAW_NAME = "農業天然災害救助辦法"
OFFICIAL_MOJ_URL = "https://law.moj.gov.tw/LawClass/LawAll.aspx?PCODE=M0090019"
OFFICIAL_MOA_URL = "https://law.moa.gov.tw/LawContent.aspx?id=FL014287"

ROOT = Path(__file__).resolve().parents[4]
LEGAL_DATA_DIR = ROOT / "data" / "legal" / "agricultural_disaster_relief"

CHINESE_NUM_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
}


def _strip_tags(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    text = re.sub(r"</div>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _parse_roc_date(raw_html: str) -> str:
    m = re.search(r"民國\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日", raw_html)
    if m:
        year = int(m.group(1)) + 1911
        month = int(m.group(2))
        day = int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"
    m_iso = re.search(r"(\d{4}-\d{2}-\d{2})", raw_html)
    return m_iso.group(1) if m_iso else "UNKNOWN"


def _decompose_provisions(article_no: str, full_text: str) -> list[dict[str, str]]:
    """Decompose an article into article-level and paragraph/item-level records."""
    rows: list[dict[str, str]] = []
    article_id = f"{LAW_ID}-ARTICLE-{article_no}"
    rows.append({
        "article_id": article_id,
        "paragraph_id": "",
        "item_id": "",
        "citation_id": article_id,
        "text": full_text,
    })

    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
    p_idx = 0
    for ln in lines:
        m_item = re.match(r"^([一二三四五六七八九十]+)、", ln)
        if m_item:
            item_num = CHINESE_NUM_MAP.get(m_item.group(1), m_item.group(1))
            p_num = max(1, p_idx)
            pid = f"{article_id}-P{p_num}"
            iid = f"{pid}-I{item_num}"
            rows.append({
                "article_id": article_id,
                "paragraph_id": pid,
                "item_id": iid,
                "citation_id": iid,
                "text": ln,
            })
        else:
            p_idx += 1
            pid = f"{article_id}-P{p_idx}"
            rows.append({
                "article_id": article_id,
                "paragraph_id": pid,
                "item_id": "",
                "citation_id": pid,
                "text": ln,
            })
    return rows


def parse_m0090019_html(raw_html: str, *, retrieved_at: str | None = None) -> dict[str, Any]:
    """Parse official MOJ LawAll HTML into structured articles, chapters, and appendices."""
    source_bytes = raw_html.encode("utf-8")
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    revision_date = _parse_roc_date(raw_html)
    retrieved_ts = retrieved_at or datetime.now(timezone.utc).isoformat()

    # Extract official appendix links
    appendices: list[dict[str, Any]] = []
    for idx, m in enumerate(
        re.finditer(r'<a[^>]+href="(LawGetFile\.ashx\?FileId=[^"]+)"[^>]*>(.*?)</a>', raw_html, re.I | re.S),
        1,
    ):
        href = html.unescape(m.group(1))
        title = _normalize_text(_strip_tags(m.group(2)))
        appendices.append({
            "appendix_id": f"{LAW_ID}-APPENDIX-{idx:02d}",
            "version": revision_date,
            "title": title,
            "source_pdf_url": f"https://law.moj.gov.tw/LawClass/{href}",
            "source_page": None,
            "table_row": None,
            "crop_category": None,
            "assistance_type": None,
            "amount": None,
            "unit": None,
            "conditions": None,
            "footnotes": None,
            "original_text": title,
            "verification_status": "EXTRACTION_REQUIRES_REVIEW",
        })

    # Extract chapters and articles in document order
    token_re = re.compile(
        r'(<div class="h3 char-\d+">\s*(第\s*[一二三四五六七八九十]+\s*章[^<]*)</div>)'
        r'|(<div class="col-no">.*?flno=([0-9-]+)[^>]*>([^<]+)</a></div>\s*'
        r'<div class="col-data"><div class="law-article">(.*?)</div>\s*</div>\s*</div>)',
        re.S | re.I,
    )

    current_chapter = ""
    articles_csv_rows: list[dict[str, str]] = []
    article_count = 0
    seen_flno: set[str] = set()

    for m in token_re.finditer(raw_html):
        if m.group(2):
            current_chapter = _normalize_text(html.unescape(m.group(2)))
            continue
        flno = m.group(4).strip()
        if flno in seen_flno:
            continue
        seen_flno.add(flno)
        article_count += 1
        body_text = _strip_tags(m.group(6))
        for prov in _decompose_provisions(flno, body_text):
            articles_csv_rows.append({
                "law_id": LAW_ID,
                "version": revision_date,
                "article_id": prov["article_id"],
                "paragraph_id": prov["paragraph_id"],
                "item_id": prov["item_id"],
                "text": prov["text"],
                "normalized_text": _normalize_text(prov["text"]),
                "chapter": current_chapter,
                "effective_from": revision_date,
                "effective_to": "",
                "source_url": f"https://law.moj.gov.tw/LawClass/LawSingle.aspx?pcode={LAW_ID}&flno={flno}",
                "source_sha256": source_sha256,
                "citation_id": prov["citation_id"],
            })

    manifest = {
        "law_id": LAW_ID,
        "law_name": LAW_NAME,
        "official_url": OFFICIAL_MOJ_URL,
        "auxiliary_official_url": OFFICIAL_MOA_URL,
        "revision_date": revision_date,
        "effective_date": revision_date,
        "retrieved_at": retrieved_ts,
        "source_sha256": source_sha256,
        "source_status": "VERIFIED_OFFICIAL_MOJ_SOURCE",
        "article_count": article_count,
        "provision_row_count": len(articles_csv_rows),
        "appendix_versions": [
            {
                "appendix_id": a["appendix_id"],
                "version": a["version"],
                "title": a["title"],
                "source_pdf_url": a["source_pdf_url"],
                "verification_status": a["verification_status"],
            }
            for a in appendices
        ],
    }
    return {
        "manifest": manifest,
        "rows": articles_csv_rows,
        "appendices": appendices,
    }


def build_legal_dataset(data_dir: Path | None = None, *, fetch_if_missing: bool = False) -> dict[str, Any]:
    """Build manifest, structured articles.csv, and appendices_manifest.json."""
    target_dir = data_dir or LEGAL_DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    html_path = target_dir / "raw_m0090019.html"

    if not html_path.is_file():
        if not fetch_if_missing:
            raise FileNotFoundError(f"Missing official HTML source at {html_path}")
        req = urllib.request.Request(OFFICIAL_MOJ_URL, headers={"User-Agent": "SAR2Action-LegalRAG/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html_path.write_text(resp.read().decode("utf-8"), encoding="utf-8")

    raw_html = html_path.read_text(encoding="utf-8")
    parsed = parse_m0090019_html(raw_html)

    manifest_path = target_dir / "legal_source_manifest.json"
    manifest_path.write_text(json.dumps(parsed["manifest"], indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = target_dir / "articles.csv"
    fieldnames = [
        "law_id", "version", "article_id", "paragraph_id", "item_id",
        "text", "normalized_text", "chapter", "effective_from", "effective_to",
        "source_url", "source_sha256", "citation_id",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(parsed["rows"])

    app_dir = target_dir / "appendices"
    app_dir.mkdir(parents=True, exist_ok=True)
    app_path = app_dir / "appendices_manifest.json"
    app_path.write_text(json.dumps(parsed["appendices"], indent=2, ensure_ascii=False), encoding="utf-8")

    return parsed["manifest"]
