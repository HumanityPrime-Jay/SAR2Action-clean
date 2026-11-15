# SAR2Action — 200-Case Agricultural Legal RAG Benchmark

## 1. Purpose & Methodology
To evaluate **Model-Free Agricultural Legal Retrieval** (`SQLite FTS5 + BM25 + Controlled Legal Ontology`, zero neural embedding/reranker models) beyond the original 51-case Golden Benchmark, we constructed an independent **200-case evaluation dataset**:
- `tests/advanced/legal_rag/benchmark_200/legal_evaluation_200.jsonl` (200 cases)
- `tests/advanced/legal_rag/benchmark_200/dev_120.jsonl` (120 cases — used for retrieval/ontology tuning)
- `tests/advanced/legal_rag/benchmark_200/final_held_out_80.jsonl` (80 cases — SHA256-locked in `held_out_manifest.json`; never tuned on)

### Grounding & Provenance
- **Official Statute**: 《農業天然災害救助辦法》 (`PCODE=M0090019`), verified against live `law.moj.gov.tw` revision `2026-06-29` (民國 115 年 06 月 29 日).
- **Programmatic Verification**:
  - `187/200` cases: `VERIFIED_AGAINST_OFFICIAL_TEXT` (expected article numbers verified against `legal_rag.sqlite`).
  - `13/200` cases: `HUMAN_REVIEW_REQUIRED` (appendix/edge-case items where PDF table extraction requires human legal review).
  - *Note*: These 200 cases were **not** reviewed by human legal experts.

## 2. Dataset Split & Category Distribution (200 Cases)
- **A. Farmer Colloquial**: 40
- **B. Multi-Turn Context**: 30
- **C. Complex Conditions & Exceptions**: 30
- **D. Exact Article Lookup**: 25
- **E. Relief Calculation & Area Traps**: 25
- **F. Missing Information & Uncertainty**: 20
- **G. Temporal Version & Verification**: 15
- **H. Out-of-Scope & Prompt Injection**: 15

## 3. Retrieval & Guardrail Results

| Metric | Golden 51 | `dev_120.jsonl` (Baseline -> Final) | `final_held_out_80.jsonl` (Locked) | Full `200` |
|---|---|---|---|---|
| **Status Accuracy** | 100.00% | 102/120 (85.00%) -> **120/120 (100.00%)** | **76/80 (95.00%)** | **196/200 (98.00%)** |
| **Recall@1** | - | 62/104 (59.62%) -> **79/104 (75.96%)** | **49/73 (67.12%)** | **128/177 (72.32%)** |
| **Recall@3** | - | 79/104 (75.96%) -> **100/104 (96.15%)** | **56/73 (76.71%)** | **156/177 (88.14%)** |
| **Recall@5** | 100.00% | 83/104 (79.81%) -> **104/104 (100.00%)** | **58/73 (79.45%)** | **162/177 (91.53%)** |
| **MRR@10** | - | 0.6829 -> **0.8619** | **0.7237** | **0.8049** |
| **Exact Article Acc** | - | 18/18 (100.00%) -> **18/18 (100.00%)** | **12/12 (100.00%)** | **30/30 (100.00%)** |
| **Citation Validity** | 100.00% | 120/120 (100.00%) -> **120/120 (100.00%)** | **80/80 (100.00%)** | **200/200 (100.00%)** |
| **Critical Errors** | 0 | 18 -> **0** | **4** | **4** |
| **Unsupported Claims** | 0 | 0 -> **0** | **0** | **0** |
| **Avg Latency (ms)** | - | 12.35 -> **13.62** | **14.19** | **34.20** |
| **P95 Latency (ms)** | - | 20.41 -> **20.27** | **21.26** | **94.53** |

## 4. Held-Out-80 & Post-Fix Regression Summary
- **Pre-Fix Locked `final_held_out_80.jsonl`**: Status Accuracy `76/80 (95.00%)`, `CritErr=4` (`A29`, `A32`, `A34`, `A37`), Recall@5 `58/73 (79.45%)`.
- **Post-Fix `final_held_out_80.jsonl` (Deterministic Only, `A29/A32/A34/A37` treated as known failure regression cases)**:
  - Status Accuracy: **80/80 (100.00%)**, `CritErr = 0`, `CitValid = 80/80 (100.00%)`, `Unsup = 0`
  - Recall@1: **53/73 (72.60%)**, Recall@3: **60/73 (82.19%)**, Recall@5: **62/73 (84.93%)**
  - Remaining 11 non-critical Recall@5 misses: `A25, A39, A40, C25, C26, C28, D18, D19, E16, G12, H10`.
- **New 32-Case Blind Regression Set (`blind_regression_32.jsonl`)**: See [GEMINI_LEGAL_SEMANTIC_RETRIEVAL.md](GEMINI_LEGAL_SEMANTIC_RETRIEVAL.md) (`Deterministic`: Recall@5 `27/30 (90.00%)`, `CritErr=0`; `Gemini-Assisted`: Recall@5 `28/30 (93.33%)`, `CritErr=0`).
