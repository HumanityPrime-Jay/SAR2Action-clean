# SAR2Action — Advanced Experimentation & Falsification (Workstream A)

## Overview

Workstream A adds an **Autonomous Experimentation & Falsification** layer under `backend/app/advanced/experimentation/` that integrates with Scientific Agent V3 through a non-invasive adapter without modifying `backend/app/main.py`, `backend/app/services/investigation_v3.py`, `frontend/`, or `requirements.txt`.

## Module Structure

- `backend/app/advanced/experimentation/models.py`: Typed, JSON-serializable dataclasses and enums (`InvestigationContext`, `ExperimentPlan`, `ExperimentResult`, `ExperimentEvaluation`, `HypothesisState`, `ExperimentScoreBreakdown`, `ToolTraceEntry`, `BoundedInvestigationResult`).
- `backend/app/advanced/experimentation/tool_registry.py`: Whitelist-only, read-only `ScientificToolRegistry` with timeout enforcement and source-backed execution over verified SAR2Action artifacts (`data/exports/yunlin_vh_2025_2026/field_comparison.json`, `data/exports/typhoon_champi/science_qa.json`, `official_loss_record.json`).
- `backend/app/advanced/experimentation/designer.py`: `design_experiment_plans` and deterministic `validate_experiment_plan` (enforces tool whitelist, step limits, input availability, and duplicate prevention).
- `backend/app/advanced/experimentation/scoring.py`: Deterministic heuristic priority ranking (`score_experiment`, `rank_experiment_plans`). Explicitly sets `is_statistical_probability = False`.
- `backend/app/advanced/experimentation/falsification.py`: Hypothesis-specific falsification rules for:
  - A. `typhoon_surface_change`
  - B. `agricultural_harvest`
  - C. `moisture_variation`
  - D. `observation_artifact`
  - E. `insufficient_evidence`
- `backend/app/advanced/experimentation/loop.py`: Bounded closed-loop investigation (`OBSERVE -> HYPOTHESIZE -> DESIGN EXPERIMENT -> EXECUTE TOOL -> EVALUATE -> REVISE HYPOTHESIS -> STOP OR CONTINUE`), capped at 3 experiments and 5 tool steps per experiment.
- `backend/app/advanced/experimentation/adapter.py`: Public Python API and V3 adapter helpers (`build_v3_context`, `to_v3_adapter_payload`).

## Public Python API

```python
from backend.app.advanced.experimentation import (
    build_v3_context,
    design_experiments,
    rank_experiments,
    execute_experiment,
    evaluate_experiment,
    revise_hypotheses,
    run_bounded_investigation,
    to_v3_adapter_payload,
)
```

## Executable Read-Only Experiment Tools

1. `temporal_alignment_test`: Checks pre-warning, warning-window, and post-warning SAR acquisition alignment and observed VH dB differences.
2. `cross_field_comparison`: Compares the target field against the five official Taixi farmland candidates (`YL-CAND-01`..`YL-CAND-05`).
3. `seasonal_reference_comparison`: Compares 2026 VH observations against matched 2025 same-orbit observations.
4. `cross_crid_compatibility_test`: Applies the deterministic NISAR cross-CRID compatibility gate (`P05023` vs `P05036`).
5. `official_loss_scope_check`: Verifies Ministry of Agriculture county-level loss scope vs parcel ground truth.
6. `missing_evidence_audit`: Audits missing parcel crop/harvest records, rainfall/soil moisture, and ground survey data.

## Epistemic & Safety Guarantees

- **No Git or Write Operations**: All tools are read-only; arbitrary Python execution and non-whitelisted tools raise `UnauthorizedToolError`.
- **No Unchecked Claims**: Untested checks remain in `untested_checks`; absence of refutation never marks a hypothesis `CONFIRMED`.
- **No Fabricated Results**: Missing field or external records return `MISSING_EVIDENCE` with `None` metrics.
- **No Ungrounded Probabilities**: Experiment scores are heuristic selection priorities only (`is_statistical_probability = False`).

## Offline Verification

Run the offline test suite (uses `FakeModel` where LLM proposals are tested):

```powershell
python -m unittest discover -s tests/advanced/experimentation -v
```
