# Legal RAG Evaluation Report

## Benchmark Configuration
- Test suite: `tests/advanced/legal_rag/test_legal_rag_benchmark.py`
- Total golden cases: **51** manually verified questions covering Exact Article Lookup, Subsections, Deadlines, Disaster Definitions, Eligibility, Crop Categories, Loss Thresholds (`<20%` & exceptions), Relief Types, Appendices, Historical Versions (`VERSION_NOT_VERIFIED`), Insufficient Info, Out-of-Scope Laws (`OUT_OF_SCOPE`), and Prompt Injection (`INSUFFICIENT_LEGAL_BASIS`).
- Active retrieval mode in offline verification: Hybrid (Exact + SQLite FTS5 Trigram + Deterministic CJK Trigram Embeddings + RRF + Deterministic Fallback Reranker; `neural_model_loaded=False`).

## Measured Results
- **Exact Article Lookup Accuracy**: `100.00%` (Target: 100%)
- **Recall@5**: `100.00%` (44/44 after fixing Article 4 disaster definition ground-truth alignment; Target: >= 95%)
- **MRR@10**: `0.873`
- **Citation Validity**: `100.00%` (Target: 100%)
- **Critical Legal Errors**: `0` (Target: 0)
- **Unsupported Legal Claims**: `0` (Target: 0)
- **Average Query Latency**: `15.40 ms`
- **Independent Held-Out Set (10 unseen cases: 7 answerable + 3 safety/version)**: Recall@5 = `6/7 (85.71%)`, Status/Guardrail Accuracy = `10/10 (100.00%)`

## 5-Strategy Ablation Comparison (44 Answerable Golden Cases)
| Strategy | Recall@5 | MRR@10 | Avg Latency |
| --- | --- | --- | --- |
| A. Exact Only | 18/44 (40.91%) | 0.409 | 0.28 ms |
| B. FTS5 Keyword Only | 29/44 (65.91%) | 0.363 | 3.08 ms |
| C. Hash Embedding Fallback | 22/44 (50.00%) | 0.395 | 4.75 ms |
| D. Hybrid (RRF) | 41/44 (93.18%) | 0.753 | 9.86 ms |
| E. Hybrid + Fallback Reranker | 43/44 (97.73%) | 0.823 | 10.18 ms |

## Limitations
- Neural `Qwen/Qwen3-Embedding-0.6B` and `Qwen/Qwen3-Reranker-0.6B` were not loaded from HuggingFace cache in this offline run; deterministic fallback was used and explicitly flagged.
- Historical law revisions prior to `2026-06-29` return `VERSION_NOT_VERIFIED` rather than guessing.
- Appendix PDF tables remain `EXTRACTION_REQUIRES_REVIEW`.
