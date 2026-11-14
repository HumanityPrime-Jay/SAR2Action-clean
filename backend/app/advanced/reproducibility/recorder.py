"""Scientific Reproducibility Engine (Phase C4).

Records full investigation provenance (inputs, SHA256, scene IDs, tool params/results,
evidence IDs, hypothesis states, missing evidence, errors) and performs deterministic
replay WITHOUT pretending to re-run Gemini.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.advanced.experimentation.adapter import run_bounded_investigation
from backend.app.advanced.experimentation.models import BoundedInvestigationResult, InvestigationContext
from backend.app.advanced.experimentation.tool_registry import ScientificToolRegistry


@dataclass
class ReproducibilityRecord:
    investigation_id: str
    recorded_at_utc: str
    data_source: str
    scene_ids: list[str]
    product_version: str
    input_sha256: str
    tool_parameters: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    evidence_ids: list[str]
    hypothesis_states: list[dict[str, Any]]
    missing_evidence: list[str]
    errors: list[str] = field(default_factory=list)
    llm_replay_mode: str = "DETERMINISTIC_NON_LLM_REPLAY"
    context_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_input_sha256(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class InvestigationRecorder:
    """Record and deterministically replay bounded scientific investigations."""

    def record(
        self,
        context: InvestigationContext,
        result: BoundedInvestigationResult,
        *,
        data_source: str = "OPERA_L2_RTC-S1_AND_NISAR_QA",
        product_version: str = "OPERA_L2_RTC-S1_v1.0",
    ) -> ReproducibilityRecord:
        scene_ids = sorted({str(o.get("source_scene_id")) for o in context.observations if o.get("source_scene_id")})
        tool_params = [
            {"experiment_id": p.experiment_id, "tools": p.selected_tools, "parameters": p.parameters}
            for p in result.experiments_planned
        ]
        tool_results = [
            {"experiment_id": r.experiment_id, "status": r.status.value, "outputs": r.outputs, "error": r.error}
            for r in result.experiments_executed
        ]
        errors = [r.error for r in result.experiments_executed if r.error]

        return ReproducibilityRecord(
            investigation_id=result.investigation_id,
            recorded_at_utc=datetime.now(timezone.utc).isoformat(),
            data_source=data_source,
            scene_ids=scene_ids,
            product_version=product_version,
            input_sha256=compute_input_sha256(context.to_dict()),
            tool_parameters=tool_params,
            tool_results=tool_results,
            evidence_ids=[e.evidence_id for e in result.evidence_ledger],
            hypothesis_states=[h.to_dict() for h in result.revised_hypotheses],
            missing_evidence=list(result.missing_evidence),
            errors=errors,
            llm_replay_mode="DETERMINISTIC_NON_LLM_REPLAY",
            context_snapshot=context.to_dict(),
        )

    def replay(
        self,
        record: ReproducibilityRecord,
        context: InvestigationContext,
        *,
        data_root: Path | None = None,
    ) -> dict[str, Any]:
        """Deterministically replay the scientific tools and verify identical outputs.

        Never pretends to re-invoke Gemini; explicitly flags llm_replay_mode.
        """
        current_sha = compute_input_sha256(context.to_dict())
        reg = ScientificToolRegistry(data_root=data_root)
        replayed = run_bounded_investigation(context, model=None, tool_registry=reg)

        replayed_hyps = [(h.hypothesis_id, h.status.value) for h in replayed.revised_hypotheses]
        recorded_hyps = [(h["hypothesis_id"], h["status"]) for h in record.hypothesis_states]
        replayed_exps = [r.experiment_id for r in replayed.experiments_executed]
        recorded_exps = [r["experiment_id"] for r in record.tool_results]

        matched = (
            current_sha == record.input_sha256
            and replayed_hyps == recorded_hyps
            and replayed_exps == recorded_exps
        )
        return {
            "replay_status": "VERIFIED_DETERMINISTIC_MATCH" if matched else "REPLAY_DRIFT_DETECTED",
            "llm_replay_executed": False,
            "llm_replay_note": "Deterministic replay re-executes verified Python tools only; Gemini is not re-invoked.",
            "input_sha256_match": current_sha == record.input_sha256,
            "hypotheses_match": replayed_hyps == recorded_hyps,
            "experiments_match": replayed_exps == recorded_exps,
            "replayed_investigation_id": replayed.investigation_id,
        }
