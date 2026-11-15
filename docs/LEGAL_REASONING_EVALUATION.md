# SAR2Action — Legal Reasoning & Relief Calculation Evaluation

## 1. `LegalDecisionEvaluator` (`backend/app/advanced/legal_rag/rules/decision_evaluator.py`)
`LegalDecisionEvaluator` provides deterministic preliminary legal condition evaluation backed by `evaluate_legal_rules()` (`M0090019`). It never issues government approval (`APPROVED` / `GUARANTEED`) and never promotes `INSUFFICIENT_INFORMATION` to `ELIGIBILITY_POSSIBLE`.

### Five Preliminary Decision Statuses
1. `OUT_OF_SCOPE`: Query or facts fall outside 《農業天然災害救助辦法》 (`M0090019`).
2. `ANNOUNCEMENT_NOT_VERIFIED`: Official disaster relief announcement (`announcement_verified`) is missing or unverified.
3. `CONDITION_NOT_MET`: Hard statutory disqualifier triggered (e.g. `loss_rate_pct < 20.0` without an Article 12-1 weather parameter or livestock headcount exception).
4. `INSUFFICIENT_INFORMATION`: Core statutory facts (`land_area_ha`, `loss_rate_pct`, `ground_evidence_verified`, etc.) are missing.
5. `ELIGIBILITY_POSSIBLE`: Preliminary statutory criteria satisfied, subject to official appendix verification and local township survey (`第12條`).

## 2. Deterministic Relief Amount Calculation (`ReliefAmountEstimator`)
Tested in `tests/advanced/legal_rag/test_200_evaluation.py`:
- **Unit Conversion & Formula (`CALCULATION_CORRECTNESS`)**: `3.5 分地` -> `0.3395 公頃` via `SQ_M_PER_FEN = 969.917` / `SQ_M_PER_HA = 10000.0`; `0.3395 * 20000 NTD/ha = 6790 NTD` (`POTENTIAL_RELIEF_ESTIMATE`, `is_approved_amount = False`).
- **Missing Announcement Guard**: Missing or unverified `verified_announcement` returns `CANNOT_ESTIMATE_MISSING_REQUIREMENTS` with `POTENTIAL_RELIEF_ESTIMATE_NTD = None`.
- **Appendix Rate Verification Guard**: Unverified appendix rate (`None` when `EXTRACTION_REQUIRES_REVIEW`) returns `CANNOT_ESTIMATE_MISSING_REQUIREMENTS`.
- **20% Threshold & Exception Guard**: `loss_rate_pct = 15.0` without exception returns `NOT_ELIGIBLE_BELOW_20_PERCENT` (`0 NTD`); with `exception_applies = True` (Article 12-1), returns `POTENTIAL_RELIEF_ESTIMATE`.

## 3. Unit Test Verification
`tests/advanced/legal_rag/test_200_evaluation.py` (`4/4` passed):
- `test_benchmark_200_manifest_sha256_integrity`
- `test_dev_120_retrieval_quality`
- `test_legal_decision_evaluator_five_statuses`
- `test_relief_amount_calculation_and_guards`
