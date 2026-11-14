"""Autonomous Experiment Designer with deterministic validation."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any, Protocol

from backend.app.advanced.experimentation.models import (
    ExperimentPlan,
    FeasibilityStatus,
    InvestigationContext,
)
from backend.app.advanced.experimentation.tool_registry import ScientificToolRegistry


class ExperimentModelProtocol(Protocol):
    """Optional LLM interface for proposing candidate experiments (FakeModel-compatible)."""

    def propose_experiments(self, context_dict: dict[str, Any]) -> list[dict[str, Any]]:
        ...


def compute_signature(experiment_type: str, field_id: str, selected_tools: list[str], parameters: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "experiment_type": experiment_type,
            "field_id": field_id,
            "selected_tools": selected_tools,
            "parameters": parameters,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def validate_experiment_plan(
    plan: ExperimentPlan,
    context: InvestigationContext,
    registry: ScientificToolRegistry,
) -> ExperimentPlan:
    """Deterministically validate legality, tool whitelist, step bounds, and feasibility."""
    if not plan.selected_tools:
        return replace(
            plan,
            feasibility_status=FeasibilityStatus.BLOCKED_INVALID_INPUT,
            rejection_reason="Experiment must select at least one whitelisted tool.",
        )

    if len(plan.selected_tools) > context.max_steps_per_experiment:
        return replace(
            plan,
            feasibility_status=FeasibilityStatus.BLOCKED_INVALID_INPUT,
            rejection_reason=f"Selected tools ({len(plan.selected_tools)}) exceed max_steps_per_experiment ({context.max_steps_per_experiment}).",
        )

    for tool_name in plan.selected_tools:
        if not registry.is_whitelisted(tool_name):
            return replace(
                plan,
                feasibility_status=FeasibilityStatus.BLOCKED_UNSAFE_TOOL,
                rejection_reason=f"Tool '{tool_name}' is not on the read-only scientific whitelist.",
            )
        if context.available_tools and tool_name not in context.available_tools:
            return replace(
                plan,
                feasibility_status=FeasibilityStatus.BLOCKED_UNSAFE_TOOL,
                rejection_reason=f"Tool '{tool_name}' is not in context.available_tools.",
            )

    if plan.signature in context.executed_experiment_signatures:
        return replace(
            plan,
            feasibility_status=FeasibilityStatus.DUPLICATE_EXPERIMENT,
            rejection_reason="Experiment with identical signature was already executed.",
        )

    # Check if required inputs are explicitly declared missing without any observations
    if not context.observations and "observations" in plan.required_inputs:
        return replace(
            plan,
            feasibility_status=FeasibilityStatus.BLOCKED_MISSING_DATA,
            rejection_reason="Required observations are absent from investigation context.",
        )

    return replace(plan, feasibility_status=FeasibilityStatus.EXECUTABLE, rejection_reason=None)


def _canonical_experiment_templates(context: InvestigationContext) -> list[ExperimentPlan]:
    """Deterministic scientific experiment templates grounded in SAR2Action V3 tools."""
    field_id = context.field_id
    params = {"field_id": field_id}

    templates = [
        ExperimentPlan(
            experiment_id=f"EXP-TEMPORAL-{field_id}",
            experiment_type="temporal_alignment",
            hypothesis_id="typhoon_surface_change",
            objective=(
                f"Verify whether the observed VH change in {field_id} aligns strictly with the Typhoon CHAMPI "
                "warning window or reflects pre-warning dynamics."
            ),
            required_inputs=["field_id", "vh_timeseries_or_comparison"],
            selected_tools=["temporal_alignment_test"],
            testable_prediction=(
                f"{field_id} exhibits a measurable VH shift between pre-warning and warning-window acquisitions "
                "with at least two pre-warning baseline points if a pre-event trend is claimed."
            ),
            falsification_criterion=(
                "If fewer than 2 pre-warning acquisitions exist, pre-warning trend attribution is untestable; "
                "if the shift precedes the warning window, typhoon causation is challenged."
            ),
            expected_evidence=["Event-bracketed 2026 OPERA VH acquisition timestamps and median dB differences"],
            scientific_limitations=[
                "Only one 2026 acquisition precedes the typhoon land warning.",
                "Timing alignment alone cannot separate storm disturbance from concurrent rainfall or management.",
            ],
            feasibility_status=FeasibilityStatus.EXECUTABLE,
            signature=compute_signature("temporal_alignment", field_id, ["temporal_alignment_test"], params),
            target_hypotheses=["typhoon_surface_change", "moisture_variation", "agricultural_harvest"],
            parameters=params,
        ),
        ExperimentPlan(
            experiment_id=f"EXP-CROSSFIELD-{field_id}",
            experiment_type="cross_field_comparison",
            hypothesis_id="typhoon_surface_change",
            objective=(
                f"Compare {field_id} against the five official Taixi farmland candidates to test whether the "
                "observed +7.553 dB VH shift is localized or part of a shared multi-field signal."
            ),
            required_inputs=["field_id", "field_comparison"],
            selected_tools=["cross_field_comparison"],
            testable_prediction=(
                "If typhoon wind/flooding affected the locality uniformly, nearby farmland candidates will show "
                "coherent warning-window VH shifts; divergent field behavior points toward parcel-specific factors."
            ),
            falsification_criterion=(
                "A shared multi-field increase challenges isolated single-parcel damage claims, while isolated "
                "field shifts challenge uniform regional storm impact."
            ),
            expected_evidence=["Five-field pre-to-warning VH delta distribution and inter-field distances"],
            scientific_limitations=[
                "Candidate polygons are official farmland boundaries without verified rice crop labels.",
                "Shared temporal signal does not prove a single common physical cause.",
            ],
            feasibility_status=FeasibilityStatus.EXECUTABLE,
            signature=compute_signature("cross_field_comparison", field_id, ["cross_field_comparison"], params),
            target_hypotheses=["typhoon_surface_change", "agricultural_harvest", "moisture_variation"],
            parameters=params,
        ),
        ExperimentPlan(
            experiment_id=f"EXP-SEASONAL-{field_id}",
            experiment_type="seasonal_reference",
            hypothesis_id="typhoon_surface_change",
            objective=(
                f"Compare {field_id} 2026 VH trajectory against matched 2025 same-orbit observations to test "
                "whether the observed peak-and-decline is unique to Typhoon CHAMPI."
            ),
            required_inputs=["field_id", "field_comparison"],
            selected_tools=["seasonal_reference_comparison"],
            testable_prediction=(
                "If the 2026 VH peak is uniquely storm-induced, 2025 same-orbit observations on matched calendar "
                "dates should not exhibit an analogous mid-season peak-and-decline."
            ),
            falsification_criterion=(
                "If 2025 also exhibits a mid-season VH peak followed by decline, the uniqueness claim for 2026 "
                "is falsified (though storm contribution is not ruled out)."
            ),
            expected_evidence=["Matched 2025 vs 2026 same-orbit VH pairs and seasonal peak indicators"],
            scientific_limitations=[
                "Three Sentinel-1 dates per year form a bounded comparison, not a multi-year climatological baseline.",
                "Cross-platform (S1A/S1C) calibration differences require incidence-angle verification.",
            ],
            feasibility_status=FeasibilityStatus.EXECUTABLE,
            signature=compute_signature("seasonal_reference", field_id, ["seasonal_reference_comparison"], params),
            target_hypotheses=["typhoon_surface_change", "agricultural_harvest", "observation_artifact"],
            parameters=params,
        ),
        ExperimentPlan(
            experiment_id=f"EXP-CRID-{field_id}",
            experiment_type="cross_crid_check",
            hypothesis_id="observation_artifact",
            objective="Test whether NISAR CRID mismatch or Sentinel-1 processing conventions explain the observed delta.",
            required_inputs=["science_qa"],
            selected_tools=["cross_crid_compatibility_test"],
            testable_prediction="NISAR pre/post scenes with mismatched CRIDs cannot be combined into a verified radiometric delta.",
            falsification_criterion="If CRIDs match and pass QA, processing-version artifact is weakened.",
            expected_evidence=["NISAR CRID compatibility decision and QA gate status"],
            scientific_limitations=["Covers NISAR CRID gate; Sentinel-1 OPERA RTC-S1 is evaluated separately."],
            feasibility_status=FeasibilityStatus.EXECUTABLE,
            signature=compute_signature("cross_crid_check", field_id, ["cross_crid_compatibility_test"], {}),
            target_hypotheses=["observation_artifact"],
            parameters={},
        ),
        ExperimentPlan(
            experiment_id=f"EXP-MISSING-AUDIT-{field_id}",
            experiment_type="missing_evidence_audit",
            hypothesis_id="insufficient_evidence",
            objective="Audit whether crop calendars, rainfall/soil moisture, and ground-truth records exist to resolve remaining hypotheses.",
            required_inputs=["field_id"],
            selected_tools=["missing_evidence_audit"],
            testable_prediction="If external crop/moisture/ground records are absent, causal attribution must stop as MISSING_EVIDENCE.",
            falsification_criterion="Presence of verified crop, rainfall, and ground-survey records refutes insufficient-evidence stop.",
            expected_evidence=["Explicit inventory of missing external causal records"],
            scientific_limitations=["Cannot fabricate or infer missing ground/crop/rainfall measurements."],
            feasibility_status=FeasibilityStatus.EXECUTABLE,
            signature=compute_signature("missing_evidence_audit", field_id, ["missing_evidence_audit"], params),
            target_hypotheses=["insufficient_evidence", "agricultural_harvest", "moisture_variation"],
            parameters=params,
        ),
    ]
    return templates


def design_experiment_plans(
    context: InvestigationContext,
    model: ExperimentModelProtocol | None = None,
    registry: ScientificToolRegistry | None = None,
) -> list[ExperimentPlan]:
    """Design and deterministically validate candidate scientific experiments."""
    reg = registry or ScientificToolRegistry()
    raw_plans: list[ExperimentPlan] = []

    if model is not None and hasattr(model, "propose_experiments"):
        proposals = model.propose_experiments(context.to_dict())
        for idx, item in enumerate(proposals, 1):
            exp_type = str(item.get("experiment_type", f"custom_{idx}"))
            tools = list(item.get("selected_tools", []))
            params = dict(item.get("parameters", {"field_id": context.field_id}))
            sig = compute_signature(exp_type, context.field_id, tools, params)
            raw_plans.append(
                ExperimentPlan(
                    experiment_id=str(item.get("experiment_id", f"EXP-LLM-{idx:02d}")),
                    experiment_type=exp_type,
                    hypothesis_id=str(item.get("hypothesis_id", "typhoon_surface_change")),
                    objective=str(item.get("objective", "")),
                    required_inputs=list(item.get("required_inputs", ["field_id"])),
                    selected_tools=tools,
                    testable_prediction=str(item.get("testable_prediction", "")),
                    falsification_criterion=str(item.get("falsification_criterion", "")),
                    expected_evidence=list(item.get("expected_evidence", [])),
                    scientific_limitations=list(item.get("scientific_limitations", [])),
                    feasibility_status=FeasibilityStatus.EXECUTABLE,
                    signature=sig,
                    target_hypotheses=list(item.get("target_hypotheses", [])),
                    parameters=params,
                )
            )

    if not raw_plans:
        raw_plans = _canonical_experiment_templates(context)

    return [validate_experiment_plan(plan, context, reg) for plan in raw_plans]
