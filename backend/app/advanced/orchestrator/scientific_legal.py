"""Scientific x Legal Reasoning Orchestrator (Phase H).

Strictly isolates SCIENTIFIC EVIDENCE from LEGAL AUTHORITY.
Default posture is DECISION_SUPPORT_ONLY (never ELIGIBLE / APPROVED / CONFIRMED_DAMAGE).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from backend.app.advanced.evidence_acquisition import detect_evidence_gaps
from backend.app.advanced.experimentation import (
    build_v3_context,
    run_bounded_investigation,
    to_v3_adapter_payload,
)
from backend.app.advanced.legal_rag import LegalRAGService
from backend.app.advanced.reproducibility import InvestigationRecorder
from backend.app.advanced.spatial_controls import match_spatial_reference_fields
from backend.app.advanced.uncertainty import analyze_robust_vh_change, assess_sar_quality

ROOT = Path(__file__).resolve().parents[4]


@dataclass
class ScientificLegalResponse:
    decision_posture: str  # Always "DECISION_SUPPORT_ONLY" unless verified official decision passed
    field_id: str
    aoi_id: str
    event_date: str | None
    scientific_evidence: dict[str, Any]
    legal_authority: dict[str, Any]
    required_follow_up: dict[str, list[str]]
    summary: str
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScientificLegalOrchestrator:
    """Coordinate scientific SAR analysis and grounded Legal RAG without mixing sources."""

    def __init__(self, data_root: Path | None = None, legal_service: LegalRAGService | None = None):
        self.data_root = data_root or ROOT
        self.legal_service = legal_service or LegalRAGService()
        self.recorder = InvestigationRecorder()

    def analyze(
        self,
        question: str,
        *,
        field_id: str = "YL-CAND-03",
        aoi_id: str = "10009160",
        event_date: str | None = "2026-10-23",
        region: str | None = "雲林縣台西鄉",
        crop: str | None = None,
        external_evidence: dict[str, Any] | None = None,
    ) -> ScientificLegalResponse:
        # 1. Scientific Evidence (isolated namespace)
        ctx = build_v3_context(field_id=field_id, research_question=question, data_root=self.data_root)
        exp_result = run_bounded_investigation(ctx)
        sar_qa = assess_sar_quality(field_id, data_root=self.data_root)
        vh_change = analyze_robust_vh_change(field_id, data_root=self.data_root)
        spatial_match = match_spatial_reference_fields(field_id, aoi_id=aoi_id, data_root=self.data_root)
        gaps = detect_evidence_gaps(
            field_id,
            sar_quality=sar_qa.to_dict(),
            cross_crid_qa={"crid_match": False},
            external_evidence=external_evidence,
        )
        repro = self.recorder.record(ctx, exp_result)

        scientific_bundle = {
            "source_boundary": "SCIENTIFIC_EVIDENCE_ONLY",
            "observation_status": vh_change.status,
            "crop_damage_confirmed": exp_result.crop_damage_confirmed,
            "vh_change": vh_change.to_dict(),
            "sar_quality": sar_qa.to_dict(),
            "spatial_reference_matching": spatial_match.to_dict(),
            "experimentation": to_v3_adapter_payload(exp_result),
            "evidence_gaps": gaps.to_dict(),
            "reproducibility": {
                "investigation_id": repro.investigation_id,
                "input_sha256": repro.input_sha256,
                "evidence_ids": repro.evidence_ids,
            },
        }

        # 2. Legal Authority (isolated namespace — M0090019 only)
        legal_resp = self.legal_service.query(
            question,
            event_date=event_date,
            region=region,
            crop=crop,
            available_evidence={
                "disaster_type": "颱風",
                "land_area_ha": (sar_qa.polygon_area_m2 / 10000.0) if sar_qa.polygon_area_m2 else None,
                # SAR dB change is NEVER passed as loss_rate_pct!
                "loss_rate_pct": (external_evidence or {}).get("loss_rate_pct"),
                "applicant_verified": (external_evidence or {}).get("applicant_verified"),
                "actual_agricultural_production": (external_evidence or {}).get("actual_agricultural_production"),
                "declared_relief_area_verified": (external_evidence or {}).get("declared_relief_area_verified"),
                "declared_relief_item_verified": (external_evidence or {}).get("declared_relief_item_verified"),
                "announcement_date": (external_evidence or {}).get("announcement_date"),
                "application_deadline": (external_evidence or {}).get("application_deadline"),
                "ground_evidence_verified": (external_evidence or {}).get("ground_evidence_verified"),
            },
        )
        legal_bundle = {
            "source_boundary": "LEGAL_AUTHORITY_M0090019_ONLY",
            **legal_resp.to_dict(),
        }

        required_follow_up = {
            "farmer": [
                "確認實際耕作作物種類與種植/養殖客觀證明文件",
                "確認申請人農民資格及實際受損面積/情況（如現勘照片）",
            ],
            "authority": [
                "核對農業部或地方政府是否已正式公告雲林縣台西鄉為救助地區與品項",
                "辦理鄉（鎮、市、區）公所現場勘查或天氣參數/免勘查條件核對",
            ],
            "field_survey": gaps.missing_ground_truth + gaps.missing_weather_evidence,
        }

        vh_val = vh_change.median_change_db
        vh_str = f"{vh_val:+.3f} dB" if vh_val is not None else "NOT_EVALUATED"
        summary = (
            f"【科學觀測】{field_id} 於警報前至警報期間之 Sentinel-1 VH 中位數變化為 {vh_str}（狀態：{vh_change.status}），"
            "目前缺乏地塊級農損真值，不得將雷達訊號變化直接認定為農損率。"
            f"【法規檢核】依《農業天然災害救助辦法》{legal_resp.applicable_law_version.get('version') or '未驗證'}版，"
            f"目前條件狀態為 {legal_resp.rule_evaluations.get('overall_status')}（DECISION_SUPPORT_ONLY），"
            "不可由 AI 自行核定救助資格。"
        )

        limitations = list(dict.fromkeys(
            vh_change.limitations
            + sar_qa.limitations
            + spatial_match.scientific_limitations
            + legal_resp.limitations
        ))

        return ScientificLegalResponse(
            decision_posture="DECISION_SUPPORT_ONLY",
            field_id=field_id,
            aoi_id=aoi_id,
            event_date=event_date,
            scientific_evidence=scientific_bundle,
            legal_authority=legal_bundle,
            required_follow_up=required_follow_up,
            summary=summary,
            limitations=limitations,
        )
