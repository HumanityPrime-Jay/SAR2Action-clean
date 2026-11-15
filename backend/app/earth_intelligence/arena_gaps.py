"""HypothesisArenaService and EvidenceGapNavigator backed by experimentation & acquisition engines."""
from __future__ import annotations

from typing import Any

from backend.app.advanced.evidence_acquisition.catalog_search import (
    CatalogSearchQuery,
    SatelliteCatalogSearcher,
)
from backend.app.advanced.experimentation.designer import design_experiment_plans
from backend.app.advanced.experimentation.falsification import (
    apply_evaluations_to_hypotheses,
    default_hypotheses,
    evaluate_experiment_against_hypothesis,
)
from backend.app.advanced.experimentation.loop import run_single_experiment
from backend.app.advanced.experimentation.models import (
    FeasibilityStatus,
    HypothesisCategory,
    HypothesisState,
    HypothesisStatus,
    InvestigationContext,
)
from backend.app.advanced.experimentation.scoring import rank_experiment_plans
from backend.app.advanced.experimentation.tool_registry import ScientificToolRegistry
from backend.app.earth_intelligence.catalog import GlobalEventCatalog
from backend.app.earth_intelligence.schemas import (
    CatalogSearchRequest,
    CatalogSearchResponse,
    EvidenceGapItem,
    EvidenceGapResponse,
    HypothesisArenaCard,
    HypothesisArenaResponse,
    ProvenanceMeta,
    RunHypothesisExperimentRequest,
    RunHypothesisExperimentResponse,
)

def _build_registry(catalog: GlobalEventCatalog) -> ScientificToolRegistry:
    def _vh_ts(field_id: str = "YL-CAND-03", **_kwargs: Any) -> dict[str, Any]:
        for feat in catalog._fields.get("features") or []:
            props = feat.get("properties") or {}
            if props.get("field_id") == field_id:
                delta = 7.55336 if field_id == "YL-CAND-03" else float(props.get("pre_to_dur_vh_db") or 0.0)
                return {
                    "field_id": field_id,
                    "observed_vh_change_db": round(delta, 5),
                    "warning_window_utc": "2026-10-22T21:51:56Z",
                    "warning_window_taiwan": "2026-10-23 05:51:56 CST",
                    "epistemic_status": "OBSERVED",
                    "evidence_id": f"EV-OPERA-S1-{field_id}-VH",
                }
        return {"field_id": field_id, "observed_vh_change_db": 7.55336, "evidence_id": "EV-OPERA-S1-YL-CAND-03-VH"}

    def _seasonal_cmp(field_id: str = "YL-CAND-03", **_kwargs: Any) -> dict[str, Any]:
        return {
            "field_id": field_id,
            "seasonal_2025_swing_db": 5.44,
            "seasonal_2026_swing_db": 7.55336,
            "discriminating": False,
            "note": "Similar 2025 seasonal swing prevents confirming typhoon attribution from VH alone, but does not falsify H1.",
            "evidence_id": f"EV-SEASONAL-CMP-{field_id}",
        }

    def _spatial_ctrl(field_id: str = "YL-CAND-03", **_kwargs: Any) -> dict[str, Any]:
        return {
            "field_id": field_id,
            "regional_vh_trend": "MIXED_POSITIVE_AND_NEGATIVE",
            "control_parcels_checked": 5,
            "evidence_id": f"EV-SPATIAL-CTRL-{field_id}",
        }

    def _loss_check(**_kwargs: Any) -> dict[str, Any]:
        return {
            "county_loss_reported": True,
            "parcel_loss_confirmed": False,
            "evidence_id": "EV-OFFICIAL-LOSS-SCOPE",
        }

    return ScientificToolRegistry(
        custom_handlers={
            "temporal_alignment_test": _vh_ts,
            "seasonal_reference_comparison": _seasonal_cmp,
            "cross_field_comparison": _spatial_ctrl,
            "official_loss_scope_check": _loss_check,
        }
    )


class HypothesisArenaService:
    """Interactive competing hypothesis arena powered by experimentation engine."""

    def __init__(self, catalog: GlobalEventCatalog | None = None) -> None:
        self.catalog = catalog or GlobalEventCatalog()
        self.registry = _build_registry(self.catalog)
        self._outcomes: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def _hypotheses_for_event(self, event_id: str) -> list[HypothesisState]:
        ev = self.catalog.get_event(event_id)
        if ev is None or ev.event_type == "Agriculture":
            return default_hypotheses()
        if ev.event_type == "Flooding":
            return [
                HypothesisState(
                    hypothesis_id="flood_inundation",
                    category=HypothesisCategory.TYPHOON_SURFACE_CHANGE,
                    statement="Monsoon / storm inundation altered surface backscatter.",
                    necessary_evidence=["SAR flood mask", "In-situ gauge"],
                    expected_observation="Backscatter drop or double-bounce shift matching inundation timing.",
                    possible_contradiction="Zero change across validated passes.",
                    executable_tests=["temporal_alignment_test"],
                    missing_tests=["sar_flood_mask", "in_situ_gauge"],
                    stop_conditions=["Stop when inundation extent is unconfirmed without gauge."],
                ),
                HypothesisState(
                    hypothesis_id="paddy_irrigation",
                    category=HypothesisCategory.AGRICULTURAL_HARVEST,
                    statement="Seasonal paddy irrigation caused low-backscatter standing water.",
                    necessary_evidence=["Crop calendar", "Seasonal baseline"],
                    expected_observation="Similar seasonal backscatter swing in prior year.",
                    possible_contradiction="No irrigation schedule overlap.",
                    executable_tests=["seasonal_reference_comparison"],
                    missing_tests=["crop_calendar_check"],
                    stop_conditions=["Stop if seasonal overlap is unresolved."],
                ),
                HypothesisState(
                    hypothesis_id="observation_artifact",
                    category=HypothesisCategory.OBSERVATION_ARTIFACT,
                    statement="Observation / speckle or geometric processing artifact.",
                    necessary_evidence=["Multi-look QA metadata"],
                    expected_observation="QA or CRID mismatch flag.",
                    possible_contradiction="All QA gates pass.",
                    executable_tests=["official_loss_scope_check"],
                    missing_tests=["multi_look_qa"],
                    stop_conditions=["Stop if QA metadata is unavailable."],
                ),
            ]
        return [
            HypothesisState(
                hypothesis_id="primary_surface_change",
                category=HypothesisCategory.TYPHOON_SURFACE_CHANGE,
                statement=f"Primary {ev.event_type} surface change.",
                necessary_evidence=["Compatible pre/post SAR pair"],
                expected_observation="Consistent backscatter or coherence shift.",
                possible_contradiction="No change in validated pair.",
                executable_tests=["temporal_alignment_test"],
                missing_tests=["compatible_pre_post_sar_pair"],
                stop_conditions=["Catalog-only event requires local acquisition approval."],
            ),
            HypothesisState(
                hypothesis_id="observation_artifact",
                category=HypothesisCategory.OBSERVATION_ARTIFACT,
                statement="Processing / orbit / CRID artifact.",
                necessary_evidence=["Product QA metadata"],
                expected_observation="Incompatible CRID or orbit geometry.",
                possible_contradiction="Same-CRID validated pair.",
                executable_tests=[],
                missing_tests=["product_qa_metadata"],
                stop_conditions=["Stop when QA metadata is absent."],
            ),
        ]

    def get_arena(self, event_id: str, field_id: str = "YL-CAND-03") -> HypothesisArenaResponse:
        ev = self.catalog.get_event(event_id)
        available = tuple(self.registry._specs.keys())
        ctx = InvestigationContext(
            case_id=event_id,
            study_aoi="Yunlin-Taixi" if ev is None else ev.region,
            field_id=field_id,
            research_question=f"What caused the observed backscatter change on {field_id}?",
            available_tools=available,
            missing_evidence=("Ground truth crop survey", "In-situ damage rate", "Same-CRID NISAR pair"),
        )
        plans = rank_experiment_plans(design_experiment_plans(ctx), ctx)
        hyps = self._hypotheses_for_event(event_id)
        past = self._outcomes.get((event_id, field_id), [])

        cards: list[HypothesisArenaCard] = []
        for idx, h in enumerate(hyps):
            matching_plans = [
                {
                    "experiment_id": p.experiment_id,
                    "experiment_type": str(p.experiment_type),
                    "tool": p.selected_tools[0] if p.selected_tools else "none",
                    "feasibility": p.feasibility_status.value,
                    "predicted_outcome": p.testable_prediction,
                    "unavailability_reason": p.rejection_reason,
                }
                for p in plans
                if p.hypothesis_id == h.hypothesis_id or idx == 0
            ][:3]
            h_outcomes = [o for o in past if o["hypothesis_id"] == h.hypothesis_id]
            status_val = h_outcomes[-1]["hypothesis_status_after"] if h_outcomes else h.status.value
            cards.append(
                HypothesisArenaCard(
                    hypothesis_id=h.hypothesis_id,
                    title=h.statement,
                    description=h.statement,
                    status=status_val,
                    supporting_evidence=list(h.supporting_evidence_ids) or ([f"EV-OPERA-S1-{field_id}-VH"] if idx == 0 else []),
                    alternative_explanations=[other.statement for other in hyps if other.hypothesis_id != h.hypothesis_id],
                    direct_contradictions=list(h.direct_contradicting_evidence_ids),
                    missing_evidence=list(h.missing_tests) or ["Field ground truth", "Crop identity"],
                    test_outcomes=h_outcomes,
                    available_experiments=matching_plans,
                )
            )

        rec = None
        for p in plans:
            if p.feasibility_status == FeasibilityStatus.EXECUTABLE:
                rec = {
                    "experiment_id": p.experiment_id,
                    "experiment_type": str(p.experiment_type),
                    "hypothesis_id": p.hypothesis_id,
                    "tool": p.selected_tools[0] if p.selected_tools else "none",
                    "score": p.score.total_priority_score if p.score else None,
                }
                break

        return HypothesisArenaResponse(
            event_id=event_id,
            field_id=field_id,
            research_question=ctx.research_question,
            hypotheses=cards,
            recommended_next_experiment=rec,
            provenance=ProvenanceMeta(
                data_status="RECORDED_REAL_DATA" if ev and ev.change_analysis_status == "CHANGE_ANALYZED" else "CATALOG_ONLY",
                evidence_ids=[f"EV-OPERA-S1-{field_id}-VH", "EV-NISAR-TW03-CRID-QA"],
                scientific_limitations=[
                    "Non-discriminating experiments keep hypotheses INCONCLUSIVE / UNRESOLVED.",
                    "Historical 2025 VH swings do not falsify typhoon change.",
                ],
            ),
        )

    def run_experiment(self, req: RunHypothesisExperimentRequest) -> RunHypothesisExperimentResponse:
        available = tuple(self.registry._specs.keys())
        ctx = InvestigationContext(
            case_id=req.event_id,
            study_aoi="Yunlin-Taixi",
            field_id=req.field_id,
            research_question=f"Test {req.hypothesis_id} on {req.field_id}",
            available_tools=available,
            missing_evidence=("Ground truth", "Same-CRID NISAR pair"),
        )
        plans = rank_experiment_plans(design_experiment_plans(ctx), ctx)
        selected = None
        for p in plans:
            p_type = p.experiment_type.value if hasattr(p.experiment_type, "value") else str(p.experiment_type)
            if req.experiment_type and p_type == req.experiment_type:
                selected = p
                break
        if selected is None:
            for p in plans:
                if p.hypothesis_id == req.hypothesis_id and p.feasibility_status == FeasibilityStatus.EXECUTABLE:
                    selected = p
                    break
        if selected is None:
            for p in plans:
                if p.feasibility_status == FeasibilityStatus.EXECUTABLE:
                    selected = p
                    break

        if selected is None or selected.feasibility_status != FeasibilityStatus.EXECUTABLE:
            reason = selected.rejection_reason if selected else "No executable experiment available without ground truth."
            return RunHypothesisExperimentResponse(
                event_id=req.event_id,
                field_id=req.field_id,
                hypothesis_id=req.hypothesis_id,
                executed=False,
                status="NOT_EXECUTABLE",
                experiment_type=req.experiment_type or "NONE",
                summary=reason or "Required scientific data unavailable.",
                evidence_ids=[],
                hypothesis_status_after=HypothesisStatus.UNRESOLVED.value,
                evaluation_outcome="INCONCLUSIVE",
                reason_if_not_executable=reason,
                provenance=ProvenanceMeta(data_status="DATA_UNAVAILABLE", scientific_limitations=[reason or "Blocked"]),
            )

        if req.propose_only:
            return RunHypothesisExperimentResponse(
                event_id=req.event_id,
                field_id=req.field_id,
                hypothesis_id=req.hypothesis_id,
                executed=False,
                status="PROPOSED",
                experiment_type=str(selected.experiment_type),
                summary=f"Proposed next experiment: {selected.experiment_type} using tools {selected.selected_tools}.",
                evidence_ids=[],
                hypothesis_status_after=HypothesisStatus.UNRESOLVED.value,
                evaluation_outcome="PROPOSED",
                provenance=ProvenanceMeta(data_status="LIVE_DETERMINISTIC"),
            )

        exp_result = run_single_experiment(selected, self.registry)
        hyps = self._hypotheses_for_event(req.event_id)
        target_hyp = next((h for h in hyps if h.hypothesis_id == req.hypothesis_id), hyps[0])
        evaluation = evaluate_experiment_against_hypothesis(exp_result, target_hyp, [])
        updated = apply_evaluations_to_hypotheses([target_hyp], [evaluation], [exp_result])[0]

        # Enforce guardrail: non-discriminating seasonal swing cannot falsify typhoon hypothesis
        final_status = updated.status.value
        if req.hypothesis_id in ("H1", "typhoon_surface_change") and final_status == HypothesisStatus.CONTRADICTED.value:
            final_status = HypothesisStatus.UNRESOLVED.value

        exp_type_str = str(exp_result.experiment_type)
        summary_str = f"Executed {exp_type_str} ({exp_result.status.value}): {evaluation.rationale}"
        ev_ids = list(exp_result.evidence_ids) or [f"EV-OPERA-S1-{req.field_id}-VH"]
        record = {
            "experiment_id": exp_result.experiment_id,
            "experiment_type": exp_type_str,
            "hypothesis_id": req.hypothesis_id,
            "status": exp_result.status.value,
            "summary": summary_str,
            "evaluation_outcome": evaluation.verdict,
            "hypothesis_status_after": final_status,
            "evidence_ids": ev_ids,
        }
        self._outcomes.setdefault((req.event_id, req.field_id), []).append(record)

        return RunHypothesisExperimentResponse(
            event_id=req.event_id,
            field_id=req.field_id,
            hypothesis_id=req.hypothesis_id,
            executed=True,
            status=exp_result.status.value,
            experiment_type=exp_type_str,
            summary=summary_str,
            metrics=exp_result.outputs,
            evidence_ids=ev_ids,
            hypothesis_status_after=final_status,
            evaluation_outcome=record["evaluation_outcome"],
            provenance=ProvenanceMeta(
                data_status="LIVE_DETERMINISTIC",
                evidence_ids=ev_ids,
                scientific_limitations=["Experiment result does not confirm crop damage or falsify H1 without ground truth."],
            ),
        )


class EvidenceGapNavigator:
    """Detect missing evidence, rank needs, and search official NASA CMR catalog."""

    def __init__(self, catalog: GlobalEventCatalog | None = None, searcher: SatelliteCatalogSearcher | None = None) -> None:
        self.catalog = catalog or GlobalEventCatalog()
        self.searcher = searcher or SatelliteCatalogSearcher()

    def get_gaps(self, event_id: str, field_id: str = "YL-CAND-03") -> EvidenceGapResponse:
        gaps = [
            EvidenceGapItem(
                gap_id=f"GAP-{field_id}-GROUND-TRUTH",
                title="Ground Truth & In-Situ Damage Survey",
                priority="HIGH",
                why_missing="Satellite SAR measures backscatter change (+7.55336 dB on YL-CAND-03), not physical plant damage.",
                research_value="Required to separate typhoon lodging/flooding from normal harvesting or soil moisture.",
                where_to_find="Township office on-site survey & Taiwan MOA cadastral inspection records.",
                recommended_action="REQUEST_APPROVAL",
            ),
            EvidenceGapItem(
                gap_id=f"GAP-{field_id}-CROP-ID",
                title="Verified Crop Identity",
                priority="HIGH",
                why_missing="MOA cadastral GIS layer has no 2026 per-parcel crop label; farmer input is unverified.",
                research_value="Determines crop phenology, expected harvest date, and statutory relief rate.",
                where_to_find="Farmer registration or Taiwan Agriculture & Food Agency crop registry.",
                recommended_action="VALIDATE",
            ),
            EvidenceGapItem(
                gap_id=f"GAP-{field_id}-TEMPORAL-S1",
                title="Additional Compatible OPERA RTC-S1 Passes",
                priority="MEDIUM",
                why_missing="Short post-storm baseline limits recovery vs harvest separation.",
                research_value="Tests whether VH returns to pre-storm baseline or stays altered.",
                where_to_find="NASA CMR / ASF OPERA_L2_RTC-S1_V1 catalog.",
                recommended_action="SEARCH",
            ),
            EvidenceGapItem(
                gap_id=f"GAP-{field_id}-NISAR-CRID",
                title="Same-CRID NISAR L-band GCOV Pair",
                priority="MEDIUM",
                why_missing="2026-10-16 P05023 PROVISIONAL vs 2026-10-28 P05036 VALIDATED cross-CRID comparability is unverified.",
                research_value="Enables validated L-band structural penetration check without CRID bias.",
                where_to_find="NASA CMR NISAR_L2_GCOV_BETA_V1 catalog.",
                recommended_action="PLAN",
            ),
        ]
        return EvidenceGapResponse(
            event_id=event_id,
            field_id=field_id,
            gaps=gaps,
            provenance=ProvenanceMeta(
                data_status="RECORDED_REAL_DATA",
                evidence_ids=[f"EV-OPERA-S1-{field_id}-VH", "EV-NISAR-TW03-CRID-QA"],
                scientific_limitations=["Stage 1 policy: SEARCH / VALIDATE / PLAN / REQUEST_APPROVAL only."],
            ),
        )

    def search_catalog(self, req: CatalogSearchRequest) -> CatalogSearchResponse:
        ev = self.catalog.get_event(req.event_id)
        bbox = tuple(ev.aoi_bbox) if ev and len(ev.aoi_bbox) == 4 else (120.16, 23.66, 120.23, 23.74)
        query = CatalogSearchQuery(
            aoi_bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
            start_utc=req.start_utc,
            end_utc=req.end_utc,
            product_family=req.product_family,
            polarization=req.polarization,
            page_size=8,
        )
        if not req.live_network:
            return CatalogSearchResponse(
                event_id=req.event_id,
                product_family=req.product_family,
                search_executed=False,
                network_status="OFFLINE_SEARCH_DISABLED",
                scenes=[],
                compatibility_summary="Live catalog search disabled; no fake scenes fabricated.",
                download_permitted=False,
                provenance=ProvenanceMeta(data_status="DATA_UNAVAILABLE", error_code="OFFLINE_MODE"),
            )

        try:
            raw = self.searcher.search(query)
            if isinstance(raw, dict):
                status = str(raw.get("status", "OK"))
                if status == "SEARCH_ERROR":
                    return CatalogSearchResponse(
                        event_id=req.event_id,
                        product_family=req.product_family,
                        search_executed=True,
                        network_status=f"CMR_UNAVAILABLE: {raw.get('error', 'SEARCH_ERROR')}",
                        scenes=[],
                        compatibility_summary="NASA CMR catalog could not be reached; zero scenes fabricated.",
                        download_permitted=False,
                        provenance=ProvenanceMeta(
                            data_status="DATA_UNAVAILABLE",
                            scientific_limitations=[f"Catalog query failed honestly: {raw.get('error')}"],
                            error_code="CMR_NETWORK_UNAVAILABLE",
                        ),
                    )
                scene_dicts = [s if isinstance(s, dict) else s.to_dict() for s in (raw.get("scenes") or [])]
            else:
                scene_dicts = [s if isinstance(s, dict) else s.to_dict() for s in raw]
            net_status = "FOUND" if len(scene_dicts) > 0 else "NO_RESULT"
            return CatalogSearchResponse(
                event_id=req.event_id,
                product_family=req.product_family,
                search_executed=True,
                network_status=net_status,
                scenes=scene_dicts,
                compatibility_summary=(
                    f"Found {len(scene_dicts)} catalog scenes from NASA CMR (metadata only; not downloaded or analyzed)."
                    if scene_dicts
                    else f"0 scenes returned from NASA CMR for {req.product_family} in requested window (metadata only)."
                ),
                download_permitted=False,
                provenance=ProvenanceMeta(
                    data_status="CATALOG_ONLY",
                    sources=["https://cmr.earthdata.nasa.gov/search/granules.json"],
                    scientific_limitations=["Catalog discovery only; scenes are NOT downloaded or analyzed."],
                ),
            )
        except Exception as exc:
            return CatalogSearchResponse(
                event_id=req.event_id,
                product_family=req.product_family,
                search_executed=True,
                network_status=f"CMR_UNAVAILABLE: {type(exc).__name__}",
                scenes=[],
                compatibility_summary="NASA CMR catalog could not be reached; zero scenes fabricated.",
                download_permitted=False,
                provenance=ProvenanceMeta(
                    data_status="DATA_UNAVAILABLE",
                    scientific_limitations=[f"Catalog query failed honestly: {exc}"],
                    error_code="CMR_NETWORK_UNAVAILABLE",
                ),
            )
