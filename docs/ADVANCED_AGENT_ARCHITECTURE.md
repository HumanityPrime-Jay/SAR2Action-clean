# SAR2Action — Advanced Agent Architecture

## Overview
The Advanced Scientific Agent extends Scientific Agent V3 in `backend/app/advanced/` without breaking existing `/api/agent/investigate-v3` contracts.

## Modules
- `experimentation/`: Autonomous experiment designer, hypothesis-specific falsification (`UNRESOLVED` vs `CONTRADICTED` vs `SUPPORTED`), heuristic priority scoring (`is_statistical_probability=False`), read-only tool whitelist, and bounded loop (max 3 experiments, 5 steps/experiment).
- `uncertainty/`: Deterministic Python SAR quality assessment (`assess_sar_quality`) and robust VH change analysis (`analyze_robust_vh_change`). Missing data returns `NOT_EVALUATED`.
- `spatial_controls/`: Spatial reference field matching (`match_spatial_reference_fields`) across `YL-CAND-01..05` with explicit sample-size and non-causal limitations.
- `evidence_acquisition/`: Gap detection (`detect_evidence_gaps`), NASA CMR/ASF catalog search (`SatelliteCatalogSearcher`), and controlled acquisition (`SEARCH`, `VALIDATE`, `PLAN`, `REQUEST_APPROVAL`; bulk download blocked).
- `reproducibility/`: `InvestigationRecorder` capturing `input_sha256`, scene IDs, tool params/results, evidence IDs, and deterministic non-LLM replay.
- `orchestrator/`: `AdvancedOrchestrator` (adaptive closed-loop) and `ScientificLegalOrchestrator` (isolated scientific vs legal reasoning).
- `farmer_agent/`: Human-like multi-turn Taiwan Traditional Chinese assistant, WGS84 geodesic area engine, damage/yield/financial loss calculators, official announcement lookup, and step-by-step application guide.
- `dual_mode/` & `indicator_explainer/`: `FARMER` / `AUTHORITY` mode separation, Authority GIS workspace, and 22-indicator context-aware explanation system.

## Real Data Validation (`YL-CAND-03`)
- Observed 2026 pre-warning to warning-window VH median change: `+7.55336 dB` (`OBSERVED`).
- `crop_damage_confirmed`: `False` (missing parcel ground truth and crop records).
