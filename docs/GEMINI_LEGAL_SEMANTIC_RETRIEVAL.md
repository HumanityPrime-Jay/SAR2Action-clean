# SAR2Action — Gemini-Assisted Legal Semantic Retrieval

## 1. Architecture
```
USER QUESTION (zh-TW / English / Mixed / Colloquial)
    ↓  [Prompt-Injection & Out-of-Scope Guards]
GEMINI SEMANTIC PLANNER (GeminiLegalSemanticPlanner, JSON Schema + Pydantic)
    ↓  [LegalSemanticIntent: normalized_zh_tw, legal_topic, search_concepts, candidate_articles]
DETERMINISTIC HYBRID RETRIEVAL (SQLite FTS5 + BM25 + Controlled Legal Ontology + Candidate Fusion)
    ↓
OFFICIAL ARTICLE VERIFICATION (legal_rag.sqlite, M0090019 2026-06-29, source_sha256)
    ↓
RULE / EXCEPTION EVALUATION (evaluate_legal_rules + LegalDecisionEvaluator)
    ↓
GROUNDED RESPONSE (with Uncertainty & Statutory Limitations)
```

- **Gemini Responsibility**: Language detection, Traditional Chinese legal normalization, topic routing (`LOAN_DISBURSEMENT`, `FALLOW_LAND`, `REPLANTING_LOSS`, `CASH_RELIEF_ELIGIBILITY`, etc.), explicit user-fact extraction, and candidate article/concept proposal.
- **Deterministic Authority**: Gemini **never** invents statutes, overrides rule evaluation, fabricates official announcements, estimates unverified relief amounts, or guarantees fixed bank deposit dates. All candidate articles are verified against `legal_rag.sqlite` (`2026-06-29`).
- **Automatic Fallback**: On missing `GEMINI_API_KEY`, timeout, HTTP error, or invalid JSON/Pydantic schema, `LegalRAGService` automatically falls back to `MODEL_FREE_DETERMINISTIC_SEMANTIC`.

## 2. Root Causes & Fixes for the 4 Critical Errors (`A29`, `A32`, `A34`, `A37`)

| Case | Before (Status / Top Hits) | Root Cause | Official Statute (`2026-06-29`) | After (Det & Gemini) |
|---|---|---|---|---|
| **A29** (`申請過了之後，錢大概什麼時候會匯進戶頭？`) | `INSUFFICIENT_LEGAL_BASIS`, `[]` | Colloquial remittance wording (`匯進戶頭`) absent from ontology/FTS5; no routing to disbursement & approval articles | 第 12 條（勘查與核撥發放程序）、第 26-1 條（核定處分機關）、第 24 條（貸款審核與撥付）、第 25 條（動用期限） | `ANSWERED`, `['第12條', '第26-1條', '第24條']`; explicitly states M0090019 fixes no bank deposit days (3/7 days) |
| **A32** (`My rice field in Yunlin was flooded by typhoon, can I get cash relief?`) | `INSUFFICIENT_LEGAL_BASIS`, `[]` | English query produced zero CJK trigram tokens in FTS5 and zero ontology matches | 第 4 條（救助種類）、第 6 條（現金救助及附表二）、第 12 條（申請程序） | `ANSWERED`, `['第6條', '第4條', '第3條']` (Gemini) / `['第6條', '第12-1條', '第3條']` (Det) |
| **A34** (`田裡其實休耕沒種東西，這樣可以跟大家一起報嗎？`) | `INSUFFICIENT_LEGAL_BASIS`, `[]` | Colloquial `休耕沒種東西` missed `未實際做農業生產使用` in Art 12-1 | 第 12-1 條第 1 項第 2 款（未實際生產不予救助）、第 5 條（救助對象） | `ANSWERED`, `['第12-1條', '第5條', '第12條']`; distinguishes long-term non-use vs temporary fallow/post-harvest |
| **A37** (`短期蔬菜淹死後重新翻土再種，損失怎麼算？`) | `INSUFFICIENT_LEGAL_BASIS`, `[]` | Colloquial `翻土再種` missed Art 9 `復耕或轉作` | 第 9 條第 1 項第 1 款（短期作物復耕/轉作損失估算）、第 6 條 | `ANSWERED`, `['第9條', '第6條', '第12-1條']` |

## 3. Deterministic Only vs. Gemini-Assisted Evaluation

### A. Known Failure Regression Cases (`A29, A32, A34, A37`)
- **Deterministic Only**: Status `4/4 (100.00%)`, Recall@1/3/5 `4/4 (100.00%)`, CitValid `4/4 (100.00%)`, CritErr `0`, Avg `12.13 ms`, P95 `15.00 ms`.
- **Gemini-Assisted**: Status `4/4 (100.00%)`, Recall@1/3/5 `4/4 (100.00%)`, CitValid `4/4 (100.00%)`, CritErr `0`, Avg `1567.97 ms`, P95 `1621.48 ms`, `4` Gemini calls (`4` succeeded, `0` fallbacks), `3,447` tokens (`2,246` prompt / `1,201` output).

### B. New 32-Case Blind Regression Set (`blind_regression_32.jsonl`)
- **Deterministic Only**: Status `32/32 (100.00%)`, Recall@1 `16/30 (53.33%)`, Recall@3 `25/30 (83.33%)`, Recall@5 `27/30 (90.00%)`, CitValid `32/32 (100.00%)`, CritErr `0`, Avg `15.04 ms`, P95 `20.37 ms`.
- **Gemini-Assisted**: Status `32/32 (100.00%)`, Recall@1 **`20/30 (66.67%)` (+13.34pp)**, Recall@3 **`27/30 (90.00%)` (+6.67pp)**, Recall@5 **`28/30 (93.33%)` (+3.33pp)**, CitValid `32/32 (100.00%)`, CritErr `0`, Avg `3004.88 ms`, P95 `8056.39 ms`, `30` Gemini calls (`30` succeeded, `0` fallbacks; 2 prompt-injection cases `BL31`/`BL32` blocked pre-Gemini), `25,627` tokens (`16,980` prompt / `8,647` output).
- **Per-Case Diffs (Honest Reporting)**:
  - **Improved by Gemini**: `BL05` (deposit date uncertainty -> lifted `24`, `25` to #1/#4), `BL09` (English working days -> lifted `12` to #3).
  - **Regressed by Gemini**: `BL01` (`低利貸款經農會審核通過後，是怎麼撥付給農民的？` — Deterministic ranked `24` at #5; Gemini expansion boosted `21` into #5 and pushed `24` out).

## 4. Security Limits & Remaining Legal Risks
- `GEMINI_API_KEY` is read strictly from backend environment variables and never logged or committed.
- Prompt injection & external-law guards execute before Gemini planning (`BL31`/`BL32` incurred 0 Gemini calls).
- **Remaining Risks**:
  - Original `final_held_out_80.jsonl` still has 11 non-critical Recall@5 misses (mainly loan sub-articles `22, 23, 25, 26` and historical-version Art `26-3, 27`).
  - Official appendix PDF tables remain marked `EXTRACTION_REQUIRES_REVIEW`; this system is decision-support only and is **not** government-certified or legal-expert-certified.
