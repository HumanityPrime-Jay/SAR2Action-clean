# Scientific Hypothesis Arena (`HypothesisArenaService`)

## Purpose
Enforces scientific falsification and competing-hypothesis evaluation rather than single-cause confirmation bias.

## Engine Integration
Directly reuses `backend/app/advanced/experimentation`:
- `default_hypotheses()`
- `ScientificToolRegistry`
- `design_experiment_plans()`
- `rank_experiment_plans(plans, context)`
- `run_single_experiment()`
- `evaluate_experiment_against_hypothesis(result, hypothesis, evidence_ledger)`
- `apply_evaluations_to_hypotheses(hypotheses, evaluations, results)`

## Scientific Honesty Guardrails
- `YL-CAND-03` (`+7.55336 dB` VH shift at `2026-10-22T21:51:56Z` / `2026-10-23 05:51:56 CST`, `DURING_TYPHOON_WARNING`) is recorded as `OBSERVED`.
- `Typhoon Cause` remains `UNRESOLVED` and `Crop Damage` remains `NOT CONFIRMED` until independent optical, ground-truth, or multi-temporal evidence falsifies competing explanations (such as aquaculture pond management or wind-roughened standing water).

## API
- `GET /api/earth/hypotheses/{event_id}?field_id=...`
- `POST /api/earth/hypotheses/experiment`
