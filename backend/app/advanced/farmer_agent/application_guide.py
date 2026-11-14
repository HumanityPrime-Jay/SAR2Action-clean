"""Step-by-Step Relief Application Guide Service (Phase 7)."""
from __future__ import annotations

from typing import Any


class ReliefApplicationGuideService:
    """Provide actionable next steps, office location, deadline reminders, and document checklist."""

    def get_application_guidance(
        self,
        *,
        county: str | None = None,
        township: str | None = None,
        crop: str | None = None,
        area_ha: float | None = None,
        announcement_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        location = f"{county or ''}{township or ''}".strip() or "受災地"
        office = f"{location}鄉（鎮、市、區）公所"

        ann_status = (announcement_result or {}).get("status", "ANNOUNCEMENT_NOT_VERIFIED")
        anns = (announcement_result or {}).get("announcements") or []
        if ann_status == "VERIFIED_ANNOUNCEMENT_FOUND" and anns:
            deadline = anns[0].get("application_deadline")
            deadline_text = f"已查證申請截止日：{deadline}（請留意是否有展延公告）。"
        else:
            deadline = None
            deadline_text = "目前尚未查證到正式公告日期，依第12條規定須於公告救助地區之翌日起十個工作日內提出申請，請盡快向公所確認是否已公告。"

        documents = [
            "農業天然災害現金救助申請表（可向公所領取或農會協助填具）",
            "國民身分證及印章",
            "土地所有權狀、土地登記謄本或有效耕作/承租契約（實際從事農業生產證明）",
            "種植或養殖客觀證明文件及受災現場照片（如有）",
            "農會或金融機構存摺影本",
        ]

        return {
            "application_office": office,
            "official_submitted": False,
            "announcement_status": ann_status,
            "verified_deadline": deadline,
            "deadline_reminder": deadline_text,
            "required_documents": documents,
            "prepared_summary": {
                "location": location,
                "crop": crop or "待確認",
                "field_area_ha": area_ha,
            },
            "citation_ids": ["M0090019-ARTICLE-5", "M0090019-ARTICLE-12"],
            "disclaimer": "本系統僅協助整理申請準備資料，並未替您向政府機關完成送件。",
        }
