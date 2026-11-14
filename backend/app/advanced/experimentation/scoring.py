"""Deterministic heuristic experiment scoring and ranking.

Scores represent heuristic selection priority only, NEVER a statistical
probability of scientific truth or confirmation.
"""
from __future__ import annotations

from dataclasses import replace

from backend.app.advanced.experimentation.models import (
    ExperimentPlan,
    ExperimentScoreBreakdown,
    FeasibilityStatus,
    InvestigationContext,
)
from backend.app.advanced.experimentation.tool_registry import ScientificToolRegistry


def score_experiment(
    plan: ExperimentPlan,
    context: InvestigationContext,
    registry: ScientificToolRegistry,
) -> ExperimentScoreBreakdown:
    """Compute a deterministic, fully explained heuristic priority score."""
    rationale: dict[str, str] = {}

    # 1. Scientific question relevance (0.0 - 3.0)
    q_lower = context.research_question.lower()
    keywords = {
        "temporal_alignment": ("time", "timing", "warning", "typhoon", "champi", "before", "after", "change", "vh", "temporal"),
        "cross_field_comparison": ("field", "parcel", "compare", "spatial", "taixi", "candidate", "yl-cand"),
        "seasonal_reference": ("2025", "2026", "seasonal", "year", "baseline", "vh", "compare"),
        "cross_crid_check": ("nisar", "crid", "artifact", "processing", "radiometric"),
        "missing_evidence_audit": ("missing", "crop", "rain", "moisture", "ground", "evidence", "insufficient"),
    }
    matched_kw = [kw for kw in keywords.get(plan.experiment_type, ()) if kw in q_lower]
    relevance_score = round(min(3.0, 1.2 + 0.35 * len(matched_kw)), 3)
    rationale["relevance"] = (
        f"Matched {len(matched_kw)} question keywords ({', '.join(matched_kw) or 'baseline domain relevance'})."
    )

    # 2. Data availability (0.0 - 2.5)
    if plan.feasibility_status == FeasibilityStatus.BLOCKED_MISSING_DATA:
        data_availability_score = 0.0
        rationale["data_availability"] = "Required input data is missing from context/verified store."
    elif context.observations or context.existing_evidence:
        data_availability_score = 2.5
        rationale["data_availability"] = "Verified SAR observations/evidence records are available for target AOI/field."
    else:
        data_availability_score = 1.0
        rationale["data_availability"] = "No preloaded observations in context; tool must verify local artifact availability."

    # 3. Executability (0.0 - 2.5)
    if plan.feasibility_status == FeasibilityStatus.EXECUTABLE:
        executability_score = 2.5
        rationale["executability"] = f"All {len(plan.selected_tools)} selected tools are whitelisted and read-only."
    else:
        executability_score = 0.0
        rationale["executability"] = f"Not executable ({plan.feasibility_status.value})."

    # 4. Discrimination across competing hypotheses (0.0 - 2.5)
    target_count = len(set(plan.target_hypotheses) | {plan.hypothesis_id})
    discrimination_score = round(min(2.5, 0.75 * target_count), 3)
    rationale["discrimination"] = f"Tests/distinguishes {target_count} competing hypothesis dimensions."

    # 5. Estimated computational cost penalty (0.0 - 1.5)
    total_cost = 0.0
    for tool_name in plan.selected_tools:
        if registry.is_whitelisted(tool_name):
            total_cost += registry.get_spec(tool_name).estimated_cost
        else:
            total_cost += 2.0
    estimated_cost_penalty = round(min(1.5, 0.35 * total_cost), 3)
    rationale["estimated_cost"] = f"Estimated read-only tool cost={total_cost:.2f} -> penalty={estimated_cost_penalty:.3f}."

    # 6. Duplicate experiment risk penalty (0.0 or 5.0)
    is_duplicate = (
        plan.feasibility_status == FeasibilityStatus.DUPLICATE_EXPERIMENT
        or plan.signature in context.executed_experiment_signatures
    )
    duplication_risk_penalty = 5.0 if is_duplicate else 0.0
    rationale["duplication_risk"] = (
        "Experiment signature already executed in this investigation." if is_duplicate else "No prior duplicate execution."
    )

    total_priority_score = round(
        relevance_score
        + data_availability_score
        + executability_score
        + discrimination_score
        - estimated_cost_penalty
        - duplication_risk_penalty,
        4,
    )

    return ExperimentScoreBreakdown(
        relevance_score=relevance_score,
        data_availability_score=data_availability_score,
        executability_score=executability_score,
        discrimination_score=discrimination_score,
        estimated_cost_penalty=estimated_cost_penalty,
        duplication_risk_penalty=duplication_risk_penalty,
        total_priority_score=total_priority_score,
        rationale=rationale,
        is_statistical_probability=False,
    )


def rank_experiment_plans(
    plans: list[ExperimentPlan],
    context: InvestigationContext,
    registry: ScientificToolRegistry | None = None,
) -> list[ExperimentPlan]:
    """Deterministically score and rank experiment plans (highest priority first)."""
    reg = registry or ScientificToolRegistry()
    scored: list[ExperimentPlan] = []
    for plan in plans:
        breakdown = score_experiment(plan, context, reg)
        scored.append(replace(plan, score=breakdown))
    return sorted(
        scored,
        key=lambda p: (
            p.feasibility_status == FeasibilityStatus.EXECUTABLE,
            p.score.total_priority_score if p.score else -999.0,
            # Deterministic tie-breaker
            p.experiment_id,
        ),
        reverse=True,
    )
