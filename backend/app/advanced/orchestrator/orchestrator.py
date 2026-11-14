"""Adaptive Advanced Investigation Orchestrator (Phase I)."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from backend.app.advanced.evidence_acquisition import (
    AcquisitionController,
    CatalogSearchQuery,
    SatelliteCatalogSearcher,
    detect_evidence_gaps,
)
from backend.app.advanced.experimentation.adapter import (
    build_v3_context,
    design_experiments,
    evaluate_experiment,
    execute_experiment,
    rank_experiments,
    revise_hypotheses,
    to_v3_adapter_payload,
)
from backend.app.advanced.experimentation.falsification import default_hypotheses
from backend.app.advanced.experimentation.models import (
    BoundedInvestigationResult,
    EvidenceItem,
    ExperimentStatus,
    FeasibilityStatus,
)
from backend.app.advanced.experimentation.tool_registry import ScientificToolRegistry
from backend.app.advanced.legal_rag import LegalRAGService
from backend.app.advanced.reproducibility import InvestigationRecorder
from backend.app.advanced.spatial_controls import match_spatial_reference_fields
from backend.app.advanced.uncertainty import analyze_robust_vh_change, assess_sar_quality

ROOT = Path(__file__).resolve().parents[4]


def _classify_intent(question: str) -> str:
    q = question.lower()
    legal_kw = ("救助", "補助", "申請", "法規", "條", "期限", "損失率", "資格", "金額")
    sci_kw = ("vh", "sar", "nisar", "opera", "雷達", "衛星", "欄位", "yl-cand", "變化", "crid")
    has_legal = any(k in q for k in legal_kw)
    has_sci = any(k in q for k in sci_kw)
    if has_legal and has_sci:
        return "SCIENTIFIC_AND_LEGAL"
    if has_legal:
        return "LEGAL_QUERY"
    return "SCIENTIFIC_INVESTIGATION"


class AdvancedOrchestrator:
    """Adaptive orchestrator unifying Experimentation, Uncertainty, Spatial, Acquisition, Repro & Legal RAG."""

    def __init__(
        self,
        data_root: Path | None = None,
        legal_service: LegalRAGService | None = None,
        catalog_searcher: SatelliteCatalogSearcher | None = None,
    ):
        self.data_root = data_root or ROOT
        self.registry = ScientificToolRegistry(data_root=self.data_root)
        self.legal_service = legal_service or LegalRAGService()
        self.catalog_searcher = catalog_searcher or SatelliteCatalogSearcher()
        self.acq_controller = AcquisitionController()
        self.recorder = InvestigationRecorder()

    def _select_next_adaptive_experiment(self, ranked, executed_results):
        """Adaptively pick next experiment based on previous experiment outputs (not static list)."""
        executable = [p for p in ranked if p.feasibility_status == FeasibilityStatus.EXECUTABLE]
        if not executable:
            return None
        if not executed_results:
            return executable[0]

        last = executed_results[-1]
        # If temporal alignment showed single pre-warning point, prioritize seasonal or cross-field next
        if last.experiment_type == "temporal_alignment":
            for pref in ("seasonal_reference", "cross_field_comparison"):
                hit = next((p for p in executable if p.experiment_type == pref), None)
                if hit:
                    return hit
        # If seasonal reference challenged uniqueness, prioritize cross_field_comparison or missing_evidence_audit
        if last.experiment_type == "seasonal_reference":
            for pref in ("cross_field_comparison", "missing_evidence_audit"):
                hit = next((p for p in executable if p.experiment_type == pref), None)
                if hit:
                    return hit
        return executable[0]

    def investigate(
        self,
        question: str,
        *,
        field_id: str = "YL-CAND-03",
        aoi_id: str = "10009160",
        event_date: str | None = "2026-10-23",
        include_catalog_search: bool = False,
        max_experiments: int = 3,
        timeout_seconds: float = 10.0,
    ) -> dict[str, Any]:
        intent = _classify_intent(question)
        ctx = build_v3_context(field_id=field_id, research_question=question, data_root=self.data_root)
        ctx = replace(ctx, max_experiments=min(max(1, max_experiments), 3), timeout_seconds=timeout_seconds)

        # Adaptive closed loop
        hypotheses = default_hypotheses()
        ledger = list(ctx.existing_evidence)
        executed_sigs: list[str] = []
        executed_results = []
        evaluations = []
        planned_initial = []
        all_missing = list(ctx.missing_evidence)
        full_trace = []
        limitations: list[str] = []
        stop_reason = "MAX_EXPERIMENTS_REACHED"
        status = "COMPLETED_BOUNDED"

        for step_idx in range(ctx.max_experiments):
            iter_ctx = replace(
                ctx,
                competing_hypotheses=hypotheses,
                existing_evidence=ledger,
                missing_evidence=all_missing,
                executed_experiment_signatures=executed_sigs,
            )
            candidates = design_experiments(iter_ctx, tool_registry=self.registry)
            ranked = rank_experiments(candidates, iter_ctx, tool_registry=self.registry)
            if step_idx == 0:
                planned_initial = ranked
            chosen = self._select_next_adaptive_experiment(ranked, executed_results)
            if chosen is None:
                stop_reason = "NO_EXECUTABLE_EXPERIMENTS"
                status = "STOPPED_NO_EXECUTABLE_EXPERIMENTS"
                break

            executed_sigs.append(chosen.signature)
            res = execute_experiment(chosen, self.registry, timeout_seconds=timeout_seconds)
            executed_results.append(res)
            full_trace.extend(res.tool_trace)

            for eid in res.evidence_ids:
                if not any(e.evidence_id == eid for e in ledger):
                    ledger.append(EvidenceItem(evidence_id=eid, source=chosen.experiment_id, summary=chosen.objective, field_id=field_id))
            for m in res.missing_evidence:
                if m not in all_missing:
                    all_missing.append(m)

            ev = evaluate_experiment(res, ledger, replace(iter_ctx, competing_hypotheses=hypotheses))
            evaluations.append(ev)
            hypotheses = revise_hypotheses(replace(iter_ctx, competing_hypotheses=hypotheses), [res], [ev])

            for lim in chosen.scientific_limitations + ev.limitations:
                if lim not in limitations:
                    limitations.append(lim)

            if res.status == ExperimentStatus.MISSING_EVIDENCE:
                stop_reason = "INSUFFICIENT_EVIDENCE_STOP"
                status = "STOPPED_MISSING_EVIDENCE"
                break

        bounded_result = BoundedInvestigationResult(
            investigation_id=f"ADV-{field_id}-{len(executed_results)}",
            case_id=ctx.case_id,
            study_aoi=ctx.study_aoi,
            field_id=field_id,
            research_question=question,
            status=status,
            stop_reason=stop_reason,
            experiments_planned=planned_initial,
            experiments_executed=executed_results,
            evaluations=evaluations,
            revised_hypotheses=hypotheses,
            missing_evidence=all_missing,
            tool_trace=full_trace,
            evidence_ledger=ledger,
            scientific_limitations=limitations,
            crop_damage_confirmed=False,
        )

        sar_qa = assess_sar_quality(field_id, data_root=self.data_root)
        vh_change = analyze_robust_vh_change(field_id, data_root=self.data_root)
        spatial_match = match_spatial_reference_fields(field_id, aoi_id=aoi_id, data_root=self.data_root)
        gaps = detect_evidence_gaps(field_id, sar_quality=sar_qa.to_dict(), cross_crid_qa={"crid_match": False})
        repro = self.recorder.record(ctx, bounded_result)

        catalog_plan = None
        if include_catalog_search:
            search_res = self.catalog_searcher.search(
                CatalogSearchQuery(
                    aoi_bbox=(120.15, 23.65, 120.25, 23.75),
                    start_utc="2026-10-01T00:00:00Z",
                    end_utc="2026-11-10T23:59:59Z",
                )
            )
            catalog_plan = self.acq_controller.execute_action(
                "PLAN",
                scenes=search_res.get("scenes", []),
                reason="Search additional pre-warning 2026 Sentinel-1/OPERA scenes",
            ).to_dict()

        legal_resp = None
        if intent in ("SCIENTIFIC_AND_LEGAL", "LEGAL_QUERY"):
            legal_resp = self.legal_service.query(
                question,
                event_date=event_date,
                available_evidence={
                    "disaster_type": "颱風",
                    "land_area_ha": (sar_qa.polygon_area_m2 / 10000.0) if sar_qa.polygon_area_m2 else None,
                },
            ).to_dict()

        return {
            "intent": intent,
            "decision_posture": "DECISION_SUPPORT_ONLY",
            "experimentation": to_v3_adapter_payload(bounded_result),
            "uncertainty": {
                "sar_quality": sar_qa.to_dict(),
                "vh_change": vh_change.to_dict(),
            },
            "spatial_controls": spatial_match.to_dict(),
            "evidence_gaps": gaps.to_dict(),
            "catalog_acquisition_plan": catalog_plan,
            "legal_rag": legal_resp,
            "reproducibility": repro.to_dict(),
        }
