"""Bounded closed-loop scientific investigation engine."""
from __future__ import annotations

import hashlib
import time
from dataclasses import replace
from datetime import datetime, timezone

from backend.app.advanced.experimentation.designer import (
    ExperimentModelProtocol,
    design_experiment_plans,
    validate_experiment_plan,
)
from backend.app.advanced.experimentation.falsification import (
    apply_evaluations_to_hypotheses,
    default_hypotheses,
    evaluate_experiment_against_hypothesis,
)
from backend.app.advanced.experimentation.models import (
    BoundedInvestigationResult,
    EvidenceItem,
    ExperimentEvaluation,
    ExperimentPlan,
    ExperimentResult,
    ExperimentStatus,
    FeasibilityStatus,
    InvestigationContext,
    ToolTraceEntry,
)
from backend.app.advanced.experimentation.scoring import rank_experiment_plans
from backend.app.advanced.experimentation.tool_registry import (
    ScientificToolRegistry,
    ToolExecutionTimeoutError,
    UnauthorizedToolError,
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deterministic_investigation_id(context: InvestigationContext) -> str:
    seed = f"{context.case_id}|{context.study_aoi}|{context.field_id}|{context.research_question}"
    return "INV-EXP-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12].upper()


def run_single_experiment(
    plan: ExperimentPlan,
    registry: ScientificToolRegistry,
    *,
    timeout_seconds: float = 10.0,
    max_steps: int = 5,
    start_step: int = 1,
) -> ExperimentResult:
    """Execute a single validated experiment plan within step and timeout bounds."""
    if plan.feasibility_status != FeasibilityStatus.EXECUTABLE:
        return ExperimentResult(
            experiment_id=plan.experiment_id,
            experiment_type=plan.experiment_type,
            hypothesis_id=plan.hypothesis_id,
            status=ExperimentStatus.REJECTED,
            error=plan.rejection_reason or f"Plan not executable: {plan.feasibility_status.value}",
        )

    if len(plan.selected_tools) > max_steps:
        return ExperimentResult(
            experiment_id=plan.experiment_id,
            experiment_type=plan.experiment_type,
            hypothesis_id=plan.hypothesis_id,
            status=ExperimentStatus.REJECTED,
            error=f"Tool step count {len(plan.selected_tools)} exceeds max_steps={max_steps}",
        )

    started = time.perf_counter()
    outputs: dict[str, dict] = {}
    evidence_ids: list[str] = []
    missing_evidence: list[str] = []
    trace: list[ToolTraceEntry] = []
    step = start_step

    for tool_name in plan.selected_tools:
        try:
            output, tool_trace = registry.execute(
                tool_name,
                plan.parameters,
                timeout_seconds=timeout_seconds,
                experiment_id=plan.experiment_id,
                step_index=step,
            )
            trace.extend(tool_trace)
            step += len(tool_trace)
            outputs[tool_name] = output
            for eid in output.get("evidence_ids", []):
                if eid not in evidence_ids:
                    evidence_ids.append(eid)
            for m in output.get("missing_evidence", []):
                if m not in missing_evidence:
                    missing_evidence.append(m)
        except UnauthorizedToolError as exc:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return ExperimentResult(
                experiment_id=plan.experiment_id,
                experiment_type=plan.experiment_type,
                hypothesis_id=plan.hypothesis_id,
                status=ExperimentStatus.REJECTED,
                outputs=outputs,
                evidence_ids=evidence_ids,
                missing_evidence=missing_evidence,
                tool_trace=trace,
                error=str(exc),
                duration_ms=duration_ms,
            )
        except ToolExecutionTimeoutError as exc:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return ExperimentResult(
                experiment_id=plan.experiment_id,
                experiment_type=plan.experiment_type,
                hypothesis_id=plan.hypothesis_id,
                status=ExperimentStatus.TIMED_OUT,
                outputs=outputs,
                evidence_ids=evidence_ids,
                missing_evidence=missing_evidence,
                tool_trace=trace,
                error=str(exc),
                timed_out=True,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return ExperimentResult(
                experiment_id=plan.experiment_id,
                experiment_type=plan.experiment_type,
                hypothesis_id=plan.hypothesis_id,
                status=ExperimentStatus.FAILED,
                outputs=outputs,
                evidence_ids=evidence_ids,
                missing_evidence=missing_evidence,
                tool_trace=trace,
                error=str(exc),
                duration_ms=duration_ms,
            )

    duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
    status = ExperimentStatus.MISSING_EVIDENCE if missing_evidence else ExperimentStatus.EXECUTED
    return ExperimentResult(
        experiment_id=plan.experiment_id,
        experiment_type=plan.experiment_type,
        hypothesis_id=plan.hypothesis_id,
        status=status,
        outputs=outputs,
        evidence_ids=evidence_ids,
        missing_evidence=missing_evidence,
        tool_trace=trace,
        duration_ms=duration_ms,
    )


def run_bounded_loop(
    context: InvestigationContext,
    model: ExperimentModelProtocol | None = None,
    registry: ScientificToolRegistry | None = None,
) -> BoundedInvestigationResult:
    """Run the bounded OBSERVE -> HYPOTHESIZE -> DESIGN -> EXECUTE -> EVALUATE -> REVISE loop."""
    reg = registry or ScientificToolRegistry()
    max_experiments = min(max(1, context.max_experiments), 3)
    max_steps = min(max(1, context.max_steps_per_experiment), 5)

    hypotheses = list(context.competing_hypotheses) if context.competing_hypotheses else default_hypotheses()
    ledger = list(context.existing_evidence)
    executed_sigs = list(context.executed_experiment_signatures)
    all_missing = list(context.missing_evidence)
    all_planned: list[ExperimentPlan] = []
    all_executed: list[ExperimentResult] = []
    all_evaluations: list[ExperimentEvaluation] = []
    full_trace: list[ToolTraceEntry] = []
    limitations: list[str] = []

    stop_reason = "MAX_EXPERIMENTS_REACHED"
    final_status = "COMPLETED_BOUNDED"

    for iteration in range(max_experiments):
        iter_context = replace(
            context,
            competing_hypotheses=hypotheses,
            existing_evidence=ledger,
            missing_evidence=all_missing,
            executed_experiment_signatures=executed_sigs,
            max_experiments=max_experiments,
            max_steps_per_experiment=max_steps,
        )

        candidates = design_experiment_plans(iter_context, model=model, registry=reg)
        validated = [validate_experiment_plan(c, iter_context, reg) for c in candidates]
        ranked = rank_experiment_plans(validated, iter_context, registry=reg)

        if iteration == 0:
            all_planned = ranked

        executable = [p for p in ranked if p.feasibility_status == FeasibilityStatus.EXECUTABLE]
        if not executable:
            if any(p.feasibility_status == FeasibilityStatus.BLOCKED_MISSING_DATA for p in ranked):
                stop_reason = "STOPPED_MISSING_EVIDENCE"
                final_status = "STOPPED_MISSING_EVIDENCE"
            else:
                stop_reason = "NO_EXECUTABLE_EXPERIMENTS"
                final_status = "STOPPED_NO_EXECUTABLE_EXPERIMENTS"
            full_trace.append(
                ToolTraceEntry(
                    step=len(full_trace) + 1,
                    timestamp_utc=_now_utc(),
                    kind="stop",
                    tool="bounded_loop_controller",
                    status=stop_reason,
                    detail={"iteration": iteration + 1},
                )
            )
            break

        chosen = executable[0]
        executed_sigs.append(chosen.signature)

        result = run_single_experiment(
            chosen,
            reg,
            timeout_seconds=context.timeout_seconds,
            max_steps=max_steps,
            start_step=len(full_trace) + 1,
        )
        all_executed.append(result)
        full_trace.extend(result.tool_trace)

        for eid in result.evidence_ids:
            if not any(item.evidence_id == eid for item in ledger):
                ledger.append(
                    EvidenceItem(
                        evidence_id=eid,
                        source=f"experiment:{chosen.experiment_id}",
                        summary=f"Observed evidence registered by {chosen.experiment_type}",
                        field_id=context.field_id,
                    )
                )

        for m in result.missing_evidence:
            if m not in all_missing:
                all_missing.append(m)

        target_hyp = next((h for h in hypotheses if h.hypothesis_id == chosen.hypothesis_id), hypotheses[0])
        evaluation = evaluate_experiment_against_hypothesis(result, target_hyp, ledger)
        all_evaluations.append(evaluation)
        hypotheses = apply_evaluations_to_hypotheses(hypotheses, [evaluation], [result])

        for lim in chosen.scientific_limitations + evaluation.limitations:
            if lim not in limitations:
                limitations.append(lim)

        if result.status == ExperimentStatus.MISSING_EVIDENCE:
            stop_reason = "INSUFFICIENT_EVIDENCE_STOP"
            final_status = "STOPPED_MISSING_EVIDENCE"
            full_trace.append(
                ToolTraceEntry(
                    step=len(full_trace) + 1,
                    timestamp_utc=_now_utc(),
                    kind="stop",
                    tool="bounded_loop_controller",
                    status=stop_reason,
                    experiment_id=chosen.experiment_id,
                    detail={"missing_evidence": result.missing_evidence},
                )
            )
            break

    return BoundedInvestigationResult(
        investigation_id=_deterministic_investigation_id(context),
        case_id=context.case_id,
        study_aoi=context.study_aoi,
        field_id=context.field_id,
        research_question=context.research_question,
        status=final_status,
        stop_reason=stop_reason,
        experiments_planned=all_planned,
        experiments_executed=all_executed,
        evaluations=all_evaluations,
        revised_hypotheses=hypotheses,
        missing_evidence=all_missing,
        tool_trace=full_trace,
        evidence_ledger=ledger,
        scientific_limitations=limitations,
        crop_damage_confirmed=False,
    )
