"""Official Legal Appendix PDF Parser & Verifier (P2).

Parses official PDFs downloaded from law.moj.gov.tw using pypdf, preserves raw
text, page numbers, SHA256, official version, conditions, and notes, and
programmatically cross-checks Chinese monetary amounts and units.
Ambiguous or multi-column rows are strictly marked HUMAN_REVIEW_REQUIRED.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[4]
APPENDICES_DIR = ROOT / "data" / "legal" / "agricultural_disaster_relief" / "appendices"
PARSED_APPENDICES_PATH = APPENDICES_DIR / "parsed_appendices.json"
MANIFEST_PATH = APPENDICES_DIR / "appendices_manifest.json"
OFFICIAL_VERSION = "2026-06-29 (M0090019)"

CN_NUM_MAP = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
CN_SMALL_UNIT = {"十": 10, "百": 100, "千": 1000}


def parse_chinese_ntd(text: str) -> int | None:
    """Deterministically convert Chinese NTD strings (e.g. '二萬五千元', '一百十二萬五千元') to integer NTD."""
    s = text.strip().replace(" ", "")
    m = re.search(r"([零〇一二兩三四五六七八九十百千萬]+)元", s)
    if not m:
        return None
    body = m.group(1)

    def _parse_under_10k(part: str) -> int | None:
        if not part:
            return 0
        total = 0
        current = 0
        has_digit = False
        for ch in part:
            if ch in CN_NUM_MAP:
                current = CN_NUM_MAP[ch]
                has_digit = True
            elif ch in CN_SMALL_UNIT:
                unit = CN_SMALL_UNIT[ch]
                if not has_digit and unit == 10:
                    current = 1
                elif not has_digit:
                    return None
                total += current * unit
                current = 0
                has_digit = False
            else:
                return None
        return total + current

    if "萬" in body:
        parts = body.split("萬")
        if len(parts) != 2:
            return None
        high = _parse_under_10k(parts[0])
        low_str = parts[1]
        if low_str and len(low_str) == 1 and low_str in CN_NUM_MAP and "千" not in body:
            # e.g. '二萬五' without 千 -> ambiguous, require review
            return None
        low = _parse_under_10k(low_str) if low_str else 0
        if high is None or low is None:
            return None
        return high * 10000 + low
    return _parse_under_10k(body)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class ParsedAppendixRecord:
    appendix_id: str
    crop_name: str
    relief_type: str
    amount_ntd: int | None
    unit: str | None
    page_number: int
    raw_text: str
    conditions: str
    notes: str
    official_version: str
    pdf_sha256: str
    verification_status: str  # "VERIFIED_FROM_OFFICIAL_PDF" | "HUMAN_REVIEW_REQUIRED"
    aliases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_pdf_pages(pdf_path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(pdf_path))
    return [(idx + 1, page.extract_text() or "") for idx, page in enumerate(reader.pages)]


def parse_appendix_02(pdf_path: Path) -> list[ParsedAppendixRecord]:
    """Parse Appendix 2 (Cash Relief Items & Rates) with strict ambiguity detection."""
    sha = _sha256_file(pdf_path)
    pages = _extract_pdf_pages(pdf_path)
    records: list[ParsedAppendixRecord] = []

    amount_unit_re = re.compile(r"([零〇一二兩三四五六七八九十百千萬]+元)\s*/\s*(公頃|箱|群|坪|頭|隻|平方公尺)")
    # Track pending multi-line item text until a rate line terminates it
    pending_lines: list[str] = []
    current_note = "適用一百十五年一月一日以後發生之天然災害（依附表二各壹貳參肆註記）。"
    current_section = "壹、農產業"

    for page_no, text in pages:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(("附表二", "第六條附表二", "農業天然災害現金救助項目", "現金救助項目")):
                continue
            if line.startswith(("壹、", "貳、", "參、", "肆、")):
                current_section = line
                pending_lines.clear()
                continue
            if line.startswith("註："):
                current_note = line
                pending_lines.clear()
                continue

            matches = list(amount_unit_re.finditer(line))
            if not matches:
                pending_lines.append(line)
                continue

            combined_raw = " ".join([*pending_lines, line]).strip()
            pending_lines.clear()

            if len(matches) > 1:
                # Multiple rates on a single line (e.g. 傳統式 vs 鋼構型, 乳牛 vs 肉牛): flag for human review
                records.append(ParsedAppendixRecord(
                    appendix_id="APPENDIX_02",
                    crop_name=combined_raw[:80],
                    relief_type="CASH_RELIEF",
                    amount_ntd=None,
                    unit=None,
                    page_number=page_no,
                    raw_text=combined_raw,
                    conditions=current_section,
                    notes="偵測到單行多個救助額度欄位，需人工核對細項對應關係。",
                    official_version=OFFICIAL_VERSION,
                    pdf_sha256=sha,
                    verification_status="HUMAN_REVIEW_REQUIRED",
                ))
                continue

            m = matches[0]
            amt_str, unit = m.group(1), m.group(2)
            amount_ntd = parse_chinese_ntd(amt_str)
            prefix = combined_raw[: combined_raw.rfind(amt_str)].strip()
            suffix = combined_raw[combined_raw.rfind(unit) + len(unit):].strip()

            # Clean item prefix (strip leading numbering like 一、 or (一))
            cleaned_name = re.sub(r"^(?:[一二三四五六七八九十]+、|\([一二三四五六七八九十]+\))\s*", "", prefix).strip()
            # If prefix still has category header like "稻米 稻米", deduplicate
            tokens = cleaned_name.split()
            if len(tokens) == 2 and tokens[0] == tokens[1]:
                cleaned_name = tokens[0]

            # Ambiguity check: if suffix contains extra rate/percentage caveats or name is empty
            if amount_ntd is None or not cleaned_name or "半數" in combined_raw:
                status = "HUMAN_REVIEW_REQUIRED"
            else:
                status = "VERIFIED_FROM_OFFICIAL_PDF"

            records.append(ParsedAppendixRecord(
                appendix_id="APPENDIX_02",
                crop_name=cleaned_name,
                relief_type="CASH_RELIEF",
                amount_ntd=amount_ntd,
                unit=unit,
                page_number=page_no,
                raw_text=combined_raw,
                conditions=f"{current_section}" + (f" | {suffix}" if suffix else ""),
                notes=current_note,
                official_version=OFFICIAL_VERSION,
                pdf_sha256=sha,
                verification_status=status,
            ))

    return records


def parse_appendix_03(pdf_path: Path) -> list[ParsedAppendixRecord]:
    """Parse Appendix 3 (Low-Interest Loan Items & Caps)."""
    sha = _sha256_file(pdf_path)
    pages = _extract_pdf_pages(pdf_path)
    records: list[ParsedAppendixRecord] = []
    loan_re = re.compile(r"最高([零〇一二兩三四五六七八九十百千萬]+元)\s*/\s*(公頃|箱|群|坪|戶|頭|隻|平方公尺)")
    pending_lines: list[str] = []
    current_section = "壹、農產業"
    current_note = "適用中華民國一百十五年一月一日以後發生之天然災害。"

    for page_no, text in pages:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("附表三", "第六條附表三", "農業天然災害低利貸款", "低利貸款項目")):
                continue
            if line.startswith(("壹、", "貳、", "參、", "肆、")):
                current_section = line
                pending_lines.clear()
                continue
            if line.startswith("註："):
                current_note = line
                pending_lines.clear()
                continue

            matches = list(loan_re.finditer(line))
            if not matches:
                pending_lines.append(line)
                continue

            combined_raw = " ".join([*pending_lines, line]).strip()
            pending_lines.clear()
            if len(matches) != 1:
                records.append(ParsedAppendixRecord(
                    appendix_id="APPENDIX_03",
                    crop_name=combined_raw[:80],
                    relief_type="LOW_INTEREST_LOAN",
                    amount_ntd=None,
                    unit=None,
                    page_number=page_no,
                    raw_text=combined_raw,
                    conditions=current_section,
                    notes="偵測到多個貸款額度欄位，需人工核對。",
                    official_version=OFFICIAL_VERSION,
                    pdf_sha256=sha,
                    verification_status="HUMAN_REVIEW_REQUIRED",
                ))
                continue

            m = matches[0]
            amt_str, unit = m.group(1), m.group(2)
            amount_ntd = parse_chinese_ntd(amt_str)
            prefix = combined_raw[: combined_raw.find("最高")].strip()
            cleaned_name = re.sub(r"^(?:[一二三四五六七八九十]+、|\([一二三四五六七八九十]+\))\s*", "", prefix).strip()
            status = "VERIFIED_FROM_OFFICIAL_PDF" if (amount_ntd is not None and cleaned_name) else "HUMAN_REVIEW_REQUIRED"
            records.append(ParsedAppendixRecord(
                appendix_id="APPENDIX_03",
                crop_name=cleaned_name,
                relief_type="LOW_INTEREST_LOAN",
                amount_ntd=amount_ntd,
                unit=unit,
                page_number=page_no,
                raw_text=combined_raw,
                conditions=current_section,
                notes=current_note,
                official_version=OFFICIAL_VERSION,
                pdf_sha256=sha,
                verification_status=status,
            ))

    return records


def parse_appendix_01_and_04(pdf_path: Path, appendix_id: str) -> list[ParsedAppendixRecord]:
    """Extract raw text & metadata from Appendix 1 (seasons) and 4 (extra relief formula)."""
    sha = _sha256_file(pdf_path)
    pages = _extract_pdf_pages(pdf_path)
    records: list[ParsedAppendixRecord] = []
    for page_no, text in pages:
        records.append(ParsedAppendixRecord(
            appendix_id=appendix_id,
            crop_name=f"{appendix_id}_PAGE_{page_no}",
            relief_type="SEASON_OR_EXTRA_FORMULA",
            amount_ntd=None,
            unit=None,
            page_number=page_no,
            raw_text=text.strip(),
            conditions="產季認定或一年一收長期作額外現金救助計算公式",
            notes="非固定單價表；額外現金救助公式須依附表二基準金額 A 人工核對。",
            official_version=OFFICIAL_VERSION,
            pdf_sha256=sha,
            verification_status="HUMAN_REVIEW_REQUIRED",
        ))
    return records


def build_and_save_parsed_appendices(appendices_dir: Path | None = None) -> dict[str, Any]:
    """Parse all 4 official appendix PDFs, save parsed_appendices.json, and update manifest."""
    target_dir = appendices_dir or APPENDICES_DIR
    all_records: list[ParsedAppendixRecord] = []

    p1 = target_dir / "appendix_01.pdf"
    p2 = target_dir / "appendix_02.pdf"
    p3 = target_dir / "appendix_03.pdf"
    p4 = target_dir / "appendix_04.pdf"

    if p1.is_file():
        all_records.extend(parse_appendix_01_and_04(p1, "APPENDIX_01"))
    if p2.is_file():
        all_records.extend(parse_appendix_02(p2))
    if p3.is_file():
        all_records.extend(parse_appendix_03(p3))
    if p4.is_file():
        all_records.extend(parse_appendix_01_and_04(p4, "APPENDIX_04"))

    verified_count = sum(1 for r in all_records if r.verification_status == "VERIFIED_FROM_OFFICIAL_PDF")
    review_count = sum(1 for r in all_records if r.verification_status == "HUMAN_REVIEW_REQUIRED")

    payload = {
        "official_version": OFFICIAL_VERSION,
        "total_records": len(all_records),
        "verified_from_official_pdf": verified_count,
        "human_review_required": review_count,
        "records": [r.to_dict() for r in all_records],
    }
    (target_dir / "parsed_appendices.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest_path = target_dir / "appendices_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest if isinstance(manifest, list) else manifest.get("appendices", [])
        for entry in entries:
            aid = entry.get("appendix_id")
            sub = [r for r in all_records if r.appendix_id == aid]
            v_cnt = sum(1 for r in sub if r.verification_status == "VERIFIED_FROM_OFFICIAL_PDF")
            h_cnt = sum(1 for r in sub if r.verification_status == "HUMAN_REVIEW_REQUIRED")
            entry["parsed_records_count"] = len(sub)
            entry["verified_records_count"] = v_cnt
            entry["human_review_required_count"] = h_cnt
            entry["parsed_summary_file"] = "parsed_appendices.json"
            if v_cnt > 0 and h_cnt == 0:
                entry["verification_status"] = "VERIFIED_FROM_OFFICIAL_PDF"
            elif v_cnt > 0:
                entry["verification_status"] = "PARTIALLY_VERIFIED_HUMAN_REVIEW_REQUIRED"
            else:
                entry["verification_status"] = "HUMAN_REVIEW_REQUIRED"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return payload


class AppendixLookupService:
    """Lookup ONLY VERIFIED_FROM_OFFICIAL_PDF appendix rates for ReliefAmountEstimator."""

    def __init__(self, parsed_path: Path | None = None):
        self.parsed_path = parsed_path or PARSED_APPENDICES_PATH
        self._data: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._data is None:
            if not self.parsed_path.is_file():
                self._data = build_and_save_parsed_appendices(self.parsed_path.parent)
            else:
                self._data = json.loads(self.parsed_path.read_text(encoding="utf-8"))
        return self._data

    def lookup_rate(self, crop: str, relief_type: str = "CASH_RELIEF") -> dict[str, Any]:
        data = self._load()
        crop_q = crop.strip()
        if crop_q in ("水稻", "稻"):
            crop_q = "稻米"
        elif crop_q == "高麗菜":
            crop_q = "甘藍"
        elif crop_q == "花生":
            crop_q = "落花生"

        for rec in data.get("records", []):
            if rec.get("relief_type") != relief_type:
                continue
            if crop_q in rec.get("crop_name", "") or crop_q in rec.get("raw_text", ""):
                if rec.get("verification_status") != "VERIFIED_FROM_OFFICIAL_PDF":
                    return {
                        "status": "HUMAN_REVIEW_REQUIRED",
                        "record": rec,
                        "verified": False,
                    }
                return {
                    "status": "VERIFIED_FROM_OFFICIAL_PDF",
                    "record": rec,
                    "verified": True,
                }
        return {"status": "NOT_FOUND_IN_APPENDIX", "record": None, "verified": False}
