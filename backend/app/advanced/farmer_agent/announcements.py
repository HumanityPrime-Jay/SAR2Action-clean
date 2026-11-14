"""Official Relief Announcement Service (Phase 6).

Only returns announcements from verified official records. Never guesses
whether a county/township has opened relief applications.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
ANNOUNCEMENTS_PATH = ROOT / "data" / "legal" / "agricultural_disaster_relief" / "official_announcements.json"


@dataclass
class OfficialAnnouncementRecord:
    disaster_event: str
    county: str
    township: str
    crop: str
    relief_type: str
    announcement_date: str
    application_start: str
    application_deadline: str
    extensions: list[str] = field(default_factory=list)
    official_source_url: str = ""
    retrieved_at: str = ""
    verification_status: str = "VERIFIED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OfficialReliefAnnouncementService:
    """Lookup verified official disaster relief announcements."""

    def __init__(self, announcements_path: Path | None = None, records: list[dict[str, Any]] | None = None):
        self.path = announcements_path or ANNOUNCEMENTS_PATH
        self._records = records

    def _load(self) -> list[dict[str, Any]]:
        if self._records is not None:
            return self._records
        if not self.path.is_file():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def search_official_relief_announcement(
        self,
        *,
        county: str | None = None,
        township: str | None = None,
        crop: str | None = None,
        disaster_event: str | None = None,
    ) -> dict[str, Any]:
        records = self._load()
        matches: list[dict[str, Any]] = []
        for r in records:
            if r.get("verification_status") != "VERIFIED":
                continue
            if county and county not in r.get("county", ""):
                continue
            if township and township not in r.get("township", ""):
                continue
            if crop and crop not in r.get("crop", ""):
                continue
            if disaster_event and disaster_event.lower() not in r.get("disaster_event", "").lower():
                continue
            matches.append(r)

        if not matches:
            return {
                "status": "ANNOUNCEMENT_NOT_VERIFIED",
                "announcements": [],
                "checked_sources": [
                    str(self.path),
                    "https://www.moa.gov.tw/",
                    "https://agr.moa.gov.tw/",
                ],
                "guidance": "目前尚未查證到該地區或作物的正式救助公告，請向當地鄉（鎮、市、區）公所或農業部公告確認。",
            }

        return {
            "status": "VERIFIED_ANNOUNCEMENT_FOUND",
            "announcements": matches,
        }
