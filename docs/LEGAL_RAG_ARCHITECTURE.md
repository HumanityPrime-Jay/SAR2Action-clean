# Hybrid Legal RAG Architecture

## Authorized Law Scope
- Strictly limited to **《農業天然災害救助辦法》** (`PCODE=M0090019`).
- Official sources:
  - `https://law.moj.gov.tw/LawClass/LawAll.aspx?PCODE=M0090019`
  - `https://law.moa.gov.tw/LawContent.aspx?id=FL014287`
- Verified revision date: **2026-06-29** (38 articles, 149 provision rows, 4 official appendix PDFs).

## Data Pipeline
- `data/legal/agricultural_disaster_relief/legal_source_manifest.json`
- `data/legal/agricultural_disaster_relief/articles.csv`
- `data/legal/agricultural_disaster_relief/appendices/appendices_manifest.json` (marked `EXTRACTION_REQUIRES_REVIEW` until PDF table extraction is human-verified)
- `data/legal/agricultural_disaster_relief/legal_rag.sqlite` (8 tables + `legal_articles_fts` SQLite FTS5 trigram index).

## Hybrid Retrieval & Model Selection
- **Exact Article Retrieval**: Direct lookup distinguishing `12` vs `12-1`, paragraphs, and items.
- **Keyword Retrieval**: SQLite FTS5 trigram + parameterized `<3 char` `LIKE` fallback.
- **Semantic & Concept Retrieval**: Model-free deterministic legal concept expansion + BM25 + lexical reranking (`uses_neural_models=False`, `requires_gpu=False`). No neural or external embedding model is downloaded or run.
- **Rank Fusion**: Reciprocal Rank Fusion (RRF) with deterministic legal priority boosts.
- **Deterministic Rule Engine**: 4-valued logic (`TRUE`, `FALSE`, `UNKNOWN`, `NOT_APPLICABLE`) over 12 statutory dimensions (`DEADLINE_UNKNOWN` without official announcement date; `LOSS_RATE_UNKNOWN` without field survey; Article 12-1 `< 20%` exceptions).
