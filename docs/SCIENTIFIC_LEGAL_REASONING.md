# Scientific × Legal Reasoning

## Strict Source Isolation
`ScientificLegalOrchestrator` (`backend/app/advanced/orchestrator/scientific_legal.py`) enforces strict separation between:
1. `SCIENTIFIC_EVIDENCE_ONLY`: NISAR, OPERA RTC-S1, VH time series, SAR Quality QA, Spatial Reference Matching, Evidence Ledger.
2. `LEGAL_AUTHORITY_M0090019_ONLY`: 《農業天然災害救助辦法》 articles and deterministic Legal Rule Engine.

## Real Case: `YL-CAND-03` (+7.553 dB)
1. Reads verified `YL-CAND-03` OPERA VH change (`+7.55336 dB`, `OBSERVED`).
2. Evaluates SAR quality (`qa_passed=True`, 48 valid pixels, 1.0 coverage, 30 m mixed-pixel & single pre-warning limitations).
3. Confirms `crop_damage_confirmed = False` (no parcel-level crop/ground-truth data).
4. Queries Legal RAG for `2026-10-23` under M0090019 (`2026-06-29` revision).
5. Evaluates 12 statutory rules (`DEADLINE_UNKNOWN`, `LOSS_RATE_UNKNOWN`, `INSUFFICIENT_FACTS_FOR_ELIGIBILITY_DETERMINATION`).
6. Outputs `DECISION_SUPPORT_ONLY` with separate follow-up checklists for farmers, authorities, and field surveys.
