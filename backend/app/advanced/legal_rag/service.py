"""Grounded Legal Answering Service (Phase G) with Citation Verification."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.app.advanced.legal_rag.database import LegalDatabase
from backend.app.advanced.legal_rag.parser import LAW_NAME
from backend.app.advanced.legal_rag.retriever import HybridLegalRetriever
from backend.app.advanced.legal_rag.rules.engine import evaluate_legal_rules

PROMPT_INJECTION_PATTERNS = (
    "ignore previous", "ignore all", "ignore instructions", "忽略之前", "忽略規則",
    "無視規則", "編造", "虛構", "直接核准", "假裝已核准", "override",
    "system prompt", "jailbreak", "approve 500000", "approve 100000",
)

OUT_OF_SCOPE_LAWS = (
    "勞動基準法", "勞基法", "民法", "刑法", "所得稅法", "建築法", "公司法", "交通", "健保",
)


@dataclass
class VerifiedCitation:
    law_name: str
    article: str
    paragraph_or_item: str
    version: str
    official_url: str
    exact_source_text: str
    source_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LegalRAGResponse:
    status: str  # "ANSWERED" | "VERSION_NOT_VERIFIED" | "OUT_OF_SCOPE" | "INSUFFICIENT_LEGAL_BASIS"
    answer: str
    citations: list[dict[str, Any]]
    applicable_law_version: dict[str, Any]
    rule_evaluations: dict[str, Any]
    missing_information: list[str]
    limitations: list[str]
    retrieval_trace: dict[str, Any]
    citation_verification: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LegalRAGService:
    """High-accuracy Legal RAG restricted strictly to《農業天然災害救助辦法》."""

    def __init__(self, db: LegalDatabase | None = None, retriever: HybridLegalRetriever | None = None):
        self.db = db or LegalDatabase()
        self.retriever = retriever or HybridLegalRetriever(self.db)

    def _build_citation(self, hit: dict[str, Any]) -> VerifiedCitation:
        cid = hit.get("citation_id") or hit["article_id"]
        art_no = hit.get("article_no") or hit["article_id"].split("-ARTICLE-")[-1]
        sub = ""
        if "-P" in cid:
            sub = cid.split(f"ARTICLE-{art_no}-", 1)[-1]
        return VerifiedCitation(
            law_name=LAW_NAME,
            article=f"第{art_no}條",
            paragraph_or_item=sub or "全文",
            version=hit["version"],
            official_url=hit["source_url"],
            exact_source_text=hit["text"],
            source_id=cid,
        )

    def verify_citations(self, citations: list[VerifiedCitation], expected_version: str) -> dict[str, Any]:
        """Deterministically verify every citation exists in SQLite with matching version & text."""
        errors: list[str] = []
        for cit in citations:
            art_no = cit.article.removeprefix("第").removesuffix("條")
            row = self.db.get_article_exact(art_no)
            if row is None:
                errors.append(f"Article {cit.article} does not exist in M0090019.")
                continue
            if row["version"] != expected_version:
                errors.append(f"Version mismatch for {cit.article}: {row['version']} != {expected_version}")
            if cit.exact_source_text not in row["text"] and row["text"] not in cit.exact_source_text:
                errors.append(f"Cited text snippet for {cit.article} does not match official source.")
        return {"verified": len(errors) == 0, "checked_count": len(citations), "errors": errors}

    def query(
        self,
        question: str,
        *,
        event_date: str | None = None,
        region: str | None = None,
        crop: str | None = None,
        available_evidence: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> LegalRAGResponse:
        q_lower = question.lower()
        ev = available_evidence or {}

        # 1. Version resolution for event_date
        version_info = self.db.resolve_version_for_date(event_date)
        if version_info["status"] == "VERSION_NOT_VERIFIED":
            rules = evaluate_legal_rules(
                disaster_type=ev.get("disaster_type"),
                crop_name=crop,
                applicable_version_verified=False,
            )
            return LegalRAGResponse(
                status="VERSION_NOT_VERIFIED",
                answer=(
                    f"無法驗證事件日期 {event_date} 當時適用的《{LAW_NAME}》歷史版本。"
                    f"目前本地僅驗證 {version_info['effective_from']} 起施行之版本，不得推測歷史條文。"
                ),
                citations=[],
                applicable_law_version=version_info,
                rule_evaluations=rules,
                missing_information=[f"Verified M0090019 revision covering {event_date}"],
                limitations=["Historical version prior to 2026-06-29 is not stored locally."],
                retrieval_trace={"skipped_reason": "VERSION_NOT_VERIFIED"},
                citation_verification={"verified": True, "checked_count": 0, "errors": []},
            )

        # 2. Prompt-injection or out-of-scope law guard
        if any(pat in q_lower for pat in PROMPT_INJECTION_PATTERNS):
            rules = evaluate_legal_rules(applicable_version_verified=True)
            return LegalRAGResponse(
                status="INSUFFICIENT_LEGAL_BASIS",
                answer="依規範拒絕虛構法條或直接核准之要求；僅能依據《農業天然災害救助辦法》正式條文提供決策支援。",
                citations=[],
                applicable_law_version=version_info,
                rule_evaluations=rules,
                missing_information=["Valid legal question within M0090019 scope"],
                limitations=["Prompt injection or fabricated claim request rejected."],
                retrieval_trace={"blocked": "prompt_injection_guard"},
                citation_verification={"verified": True, "checked_count": 0, "errors": []},
            )

        if any(law in question for law in OUT_OF_SCOPE_LAWS):
            rules = evaluate_legal_rules(applicable_version_verified=True)
            return LegalRAGResponse(
                status="OUT_OF_SCOPE",
                answer=(
                    f"本次法源知識庫僅授權收錄《{LAW_NAME}》及其正式附表，無法回答其他法規問題；"
                    "本次法源範圍不足。"
                ),
                citations=[],
                applicable_law_version=version_info,
                rule_evaluations=rules,
                missing_information=["Authorized text of external statute outside M0090019"],
                limitations=["Legal RAG scope is strictly limited to M0090019."],
                retrieval_trace={"blocked": "out_of_scope_law"},
                citation_verification={"verified": True, "checked_count": 0, "errors": []},
            )

        # 3. Model-Free Deterministic Semantic Retrieval
        retrieval = self.retriever.hybrid_search(question, top_k=top_k)
        hits = retrieval["hits"]
        citations_obj = [self._build_citation(h) for h in hits]
        verification = self.verify_citations(citations_obj, version_info["version"])

        if not citations_obj or not verification["verified"]:
            rules = evaluate_legal_rules(crop_name=crop, applicable_version_verified=True)
            return LegalRAGResponse(
                status="INSUFFICIENT_LEGAL_BASIS",
                answer="無法在《農業天然災害救助辦法》中找到經完整驗證的對應條文依據。",
                citations=[],
                applicable_law_version=version_info,
                rule_evaluations=rules,
                missing_information=["Verified statutory basis in M0090019"],
                limitations=verification.get("errors", []) or ["No matching verified article found."],
                retrieval_trace=retrieval,
                citation_verification=verification,
            )

        # 4. Deterministic Rule Evaluation
        rules = evaluate_legal_rules(
            disaster_type=ev.get("disaster_type"),
            relief_type=ev.get("relief_type"),
            applicant_verified=ev.get("applicant_verified"),
            actual_agricultural_production=ev.get("actual_agricultural_production"),
            declared_relief_area_verified=ev.get("declared_relief_area_verified"),
            declared_relief_item_verified=ev.get("declared_relief_item_verified"),
            announcement_date=ev.get("announcement_date"),
            application_deadline=ev.get("application_deadline"),
            land_area_ha=ev.get("land_area_ha"),
            loss_rate_pct=ev.get("loss_rate_pct"),
            weather_param_or_severe_exception=ev.get("weather_param_or_severe_exception"),
            is_livestock_headcount=bool(ev.get("is_livestock_headcount", False)),
            crop_name=crop,
            ground_evidence_verified=ev.get("ground_evidence_verified"),
            applicable_version_verified=True,
        )

        # 5. Compose strictly grounded answer from verified source text + rules
        top = citations_obj[0]
        preview = top.exact_source_text.replace("\n", " ")[:220]
        answer_parts = [f"依據《{LAW_NAME}》{top.article}（{top.version}版）：{preview}"]
        if len(citations_obj) > 1:
            also = "、".join(c.article for c in citations_obj[1:3])
            answer_parts.append(f"相關條文另包含：{also}。")
        if rules["missing_information"]:
            answer_parts.append(
                "注意：依規則檢核，目前仍缺少下列必要資料，尚無法單憑現有資訊認定符合救助資格："
                + "、".join(rules["missing_information"][:4])
                + "。"
            )

        self.db.log_query_audit(
            datetime.now(timezone.utc).isoformat(),
            question,
            event_date,
            version_info["version"],
            [c.source_id for c in citations_obj],
        )

        return LegalRAGResponse(
            status="ANSWERED",
            answer=" ".join(answer_parts),
            citations=[c.to_dict() for c in citations_obj],
            applicable_law_version=version_info,
            rule_evaluations=rules,
            missing_information=rules["missing_information"],
            limitations=[
                "DECISION_SUPPORT_ONLY：法規檢索與條件檢核僅供決策支援，正式核定仍由鄉（鎮、市、區）公所及主管機關辦理。",
                "附表金額與計算單位標記為 EXTRACTION_REQUIRES_REVIEW，未經人工核對前不直接代入試算。",
            ],
            retrieval_trace={
                "retrieval_mode": retrieval.get("retrieval_mode", "MODEL_FREE_DETERMINISTIC_SEMANTIC"),
                "ontology_id": retrieval.get("ontology_id"),
                "structured_query": retrieval.get("structured_query"),
                "top_article_ids": [h["article_id"] for h in hits],
                "uses_neural_models": False,
                "requires_gpu": False,
            },
            citation_verification=verification,
        )
