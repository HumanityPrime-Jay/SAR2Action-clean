"""Public Python API and non-invasive V3 Adapter for Autonomous Experimentation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.advanced.experimentation.designer import ExperimentModelProtocol, design_experiment_plans
from backend.app.advanced.experimentation.falsification import (
    apply_evaluations_to_hypotheses,
    default_hypotheses,
    evaluate_experiment_against_hypothesis,
)
from backend.app.advanced.experimentation.loop import run_bounded_loop, run_single_experiment
from backend.app.advanced.experimentation.models import (
    BoundedInvestigationResult,
    EvidenceItem,
    ExperimentEvaluation,
    ExperimentPlan,
    ExperimentResult,
    HypothesisState,
    InvestigationContext,
)
from backend.app.advanced.experimentation.scoring import rank_experiment_plans
from backend.app.advanced.experimentation.tool_registry import ROOT, ScientificToolRegistry


def design_experiments(
    context: InvestigationContext,
    model: ExperimentModelProtocol | None = None,
    tool_registry: ScientificToolRegistry | None = None,
) -> list[ExperimentPlan]:
    """Design and deterministically validate candidate experiments for a context."""
    return design_experiment_plans(context, model=model, registry=tool_registry)


def rank_experiments(
    experiments: list[ExperimentPlan],
    context: InvestigationContext | None = None,
    tool_registry: ScientificToolRegistry | None = None,
) -> list[ExperimentPlan]:
    """Deterministically score and rank candidate experiments (heuristic priority only)."""
    ctx = context or InvestigationContext(research_question="", study_aoi="Taixi Township (10009160)")
    return rank_experiment_plans(experiments, ctx, registry=tool_registry)


def execute_experiment(
    experiment: ExperimentPlan,
    tool_registry: ScientificToolRegistry | None = None,
    *,
    timeout_seconds: float = 10.0,
    max_steps: int = 5,
) -> ExperimentResult:
    """Execute a single validated experiment over the whitelisted read-only tool registry."""
    reg = tool_registry or ScientificToolRegistry()
    return run_single_experiment(experiment, reg, timeout_seconds=timeout_seconds, max_steps=max_steps)


def evaluate_experiment(
    result: ExperimentResult,
    evidence_ledger: list[EvidenceItem],
    context: InvestigationContext | None = None,
) -> ExperimentEvaluation:
    """Evaluate an experiment result against the target hypothesis's falsification criteria."""
    hyps = (context.competing_hypotheses if context and context.competing_hypotheses else default_hypotheses())
    target = next((h for h in hyps if h.hypothesis_id == result.hypothesis_id), hyps[0])
    return evaluate_experiment_against_hypothesis(result, target, evidence_ledger)


def revise_hypotheses(
    context: InvestigationContext,
    results: list[ExperimentResult],
    evaluations: list[ExperimentEvaluation] | None = None,
) -> list[HypothesisState]:
    """Revise competing hypotheses based on executed experiment results and evaluations."""
    hyps = list(context.competing_hypotheses) if context.competing_hypotheses else default_hypotheses()
    evals = evaluations if evaluations is not None else [
        evaluate_experiment(res, context.existing_evidence, context) for res in results
    ]
    return apply_evaluations_to_hypotheses(hyps, evals, results)


def run_bounded_investigation(
    context: InvestigationContext,
    model: ExperimentModelProtocol | None = None,
    tool_registry: ScientificToolRegistry | None = None,
) -> BoundedInvestigationResult:
    """Execute the full bounded closed-loop scientific investigation."""
    return run_bounded_loop(context, model=model, registry=tool_registry)


def build_v3_context(
    field_id: str = "YL-CAND-03",
    research_question: str | None = None,
    study_aoi: str = "Taixi Township (10009160)",
    data_root: Path | None = None,
) -> InvestigationContext:
    """Build an InvestigationContext directly from verified SAR2Action V3/OPERA artifacts."""
    base = data_root or ROOT
    comp_path = base / "data" / "exports" / "yunlin_vh_2025_2026" / "field_comparison.json"
    observations: list[dict[str, Any]] = []
    existing_evidence: list[EvidenceItem] = []

    if comp_path.is_file():
        comp = json.loads(comp_path.read_text(encoding="utf-8"))
        field_entry = next((f for f in comp.get("fields", []) if f.get("field_id") == field_id), None)
        if field_entry:
            for year in ("2025", "2026"):
                for obs in field_entry.get("observations", {}).get(year, []):
                    observations.append({"year": int(year), **obs})
                    existing_evidence.append(
                        EvidenceItem(
                            evidence_id=obs["evidence_id"],
                            source="data/exports/yunlin_vh_2025_2026/field_comparison.json",
                            summary=f"{field_id} {obs['acquisition_taiwan']} VH median {obs['vh_median_db']} dB",
                            field_id=field_id,
                            metrics={"vh_median_db": obs["vh_median_db"]},
                        )
                    )

    question = research_question or (
        f"What caused the observed +7.553 dB VH change in {field_id} between pre-warning and "
        "Typhoon CHAMPI warning-window 2026 observations compared with 2025?"
    )
    return InvestigationContext(
        research_question=question,
        study_aoi=study_aoi,
        case_id="CHAMPI-YUNLIN-TAIXI",
        field_id=field_id,
        observations=observations,
        existing_evidence=existing_evidence,
        competing_hypotheses=default_hypotheses(),
        missing_evidence=[
            "Parcel-level crop type, planting, and harvest calendar records",
            "In-situ or high-resolution rainfall and soil moisture records",
            "Geolocated ground damage survey or cloud-free optical validation",
        ],
        available_tools=sorted(ScientificToolRegistry(data_root=base).whitelist),
        max_experiments=3,
        max_steps_per_experiment=5,
        timeout_seconds=10.0,
    )


def to_v3_adapter_payload(result: BoundedInvestigationResult) -> dict[str, Any]:
    """Convert BoundedInvestigationResult into a JSON-serializable V3 adapter payload."""
    return {
        "adapter_version": "advanced-experimentation-v1",
        "investigation_id": result.investigation_id,
        "case_id": result.case_id,
        "field_id": result.field_id,
        "status": result.status,
        "stop_reason": result.stop_reason,
        "crop_damage_confirmed": result.crop_damage_confirmed,
        "experiments_executed_count": len(result.experiments_executed),
        "experiments_planned": [p.to_dict() for p in result.experiments_planned],
        "experiments_executed": [r.to_dict() for r in result.experiments_executed],
        "evaluations": [e.to_dict() for e in result.evaluations],
        "hypotheses": [h.to_dict() for h in result.revised_hypotheses],
        "missing_evidence": list(result.missing_evidence),
        "tool_trace": [t.to_dict() for t in result.tool_trace],
        "evidence_ids": [e.evidence_id for e in result.evidence_ledger],
        "scientific_limitations": list(result.scientific_limitations),
    }
