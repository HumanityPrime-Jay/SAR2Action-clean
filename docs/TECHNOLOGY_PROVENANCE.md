# SAR2Action Technology Provenance & Supply Chain Audit (P0)

> **Policy**: This project excludes AI models, embedding models, rerankers, vector database services, AI cloud platforms, and non-essential third-party SDKs provided or led by Chinese companies or organizations.
>
> **Audit Scope Notice**: Only the direct dependencies and core runtime components listed below have been reviewed against verifiable package metadata and official project sources. Transitive dependencies not explicitly verified are marked **`PROVENANCE_UNVERIFIED`**; this document does **not** claim that every direct and transitive dependency has completed full provenance verification.

---

## 1. AI & LLM Services
| Component | Version / ID | Official Source | Maintainer Organization | License | Actually Used | Provenance Status |
| --- | --- | --- | --- | --- | --- | --- |
| Google Gemini API (`v1beta` REST) | `gemini-3.1-flash-lite-preview` / `gemini-3-flash-preview` | `https://generativelanguage.googleapis.com/v1beta` | Google LLC (USA) | Proprietary API | Yes (Conversation, Tool Calling, Summarization) | Verified |
| `google-genai` | `3.3.0` | `https://pypi.org/project/google-genai/` | Google LLC (USA) | Apache-2.0 | Declared in `pyproject.toml` (REST client used in `gemini_client.py`) | Verified |

### Removed Neural / Embedding / Vector Components (P1)
- **Removed**: `Qwen/Qwen3-Embedding-0.6B` (Alibaba Qwen), `Qwen/Qwen3-Reranker-0.6B` (Alibaba Qwen), `transformers` / `sentence-transformers` / `FAISS` loading logic, and CJK Hash Embedding pseudo-vector search (`embeddings.py`, `legal_embeddings` table).
- **Legal Retrieval Status**: 100% **Model-Free Deterministic Legal Semantic Retrieval** (SQLite FTS5 + BM25 + Controlled Legal Ontology + Exact Article Lookup). Zero GPU or model weights required.

---

## 2. Core Python Backend & Geospatial Dependencies
| Package | Version | Official Source | Maintainer Organization | License | Actually Used | Provenance Status |
| --- | --- | --- | --- | --- | --- | --- |
| `fastapi` | `0.163.0` | `https://pypi.org/project/fastapi/` | Sebastián Ramírez / FastAPI | MIT | Yes (HTTP API) | Verified |
| `pydantic` | `2.14.3` | `https://pypi.org/project/pydantic/` | Pydantic Services Inc. (UK/EU) | MIT | Yes (Schemas) | Verified |
| `uvicorn` | `0.54.0` | `https://pypi.org/project/uvicorn/` | Encode OSS Ltd (UK) | BSD-3-Clause | Yes (ASGI server) | Verified |
| `sqlite3` / SQLite FTS5 | Python 3.12 stdlib | `https://www.sqlite.org/` | SQLite Consortium (USA) | Public Domain | Yes (Legal DB & FTS5 BM25) | Verified |
| `pypdf` | `7.1.0` | `https://pypi.org/project/pypdf/` | pypdf maintainers (OSS) | BSD-3-Clause | Yes (Official Appendix PDF parser) | Verified |
| `numpy` | `2.5.4` | `https://pypi.org/project/numpy/` | NumPy Developers (NumFOCUS, USA) | BSD-3-Clause | Yes (SAR/Geospatial math) | Verified |
| `scipy` | `1.18.1` | `https://pypi.org/project/scipy/` | SciPy Developers (NumFOCUS, USA) | BSD-3-Clause | Yes (Statistical analysis) | Verified |
| `rasterio` | `1.5.2` | `https://pypi.org/project/rasterio/` | Mapbox / Rasterio OSS | BSD-3-Clause | Yes (GeoTIFF I/O) | Verified |
| `geopandas` | `1.2.0` | `https://pypi.org/project/geopandas/` | GeoPandas Developers (NumFOCUS) | BSD-3-Clause | Yes (Vector parcels) | Verified |
| `shapely` | `2.2.0` | `https://pypi.org/project/shapely/` | Shapely Developers | BSD-3-Clause | Yes (Geometry operations) | Verified |
| `pyproj` | `3.8.0` | `https://pypi.org/project/pyproj/` | pyproj / OSGeo | MIT | Yes (CRS transforms) | Verified |
| `h5py` | `3.16.0` | `https://pypi.org/project/h5py/` | HDF Group / h5py | BSD-3-Clause | Yes (NISAR HDF5) | Verified |
| `asf_search` | `14.1.0` | `https://pypi.org/project/asf-search/` | Alaska Satellite Facility (UAF, USA) | BSD-3-Clause | Yes (NASA ASF catalog) | Verified |
| `httpx` | `0.28.1` | `https://pypi.org/project/httpx/` | Encode OSS Ltd (UK) | BSD-3-Clause | Yes (Testing/HTTP) | Verified |
| `jsonschema` | `4.26.0` | `https://pypi.org/project/jsonschema/` | Julian Berman / JSON Schema | MIT | Yes (Contract validation) | Verified |
| `pytest` | `9.2.0` | `https://pypi.org/project/pytest/` | pytest-dev (OSS) | MIT | Yes (Test runner) | Verified |
| Other transitive Python wheels (`anyio`, `starlette`, `click`, `pyogrio`, `dateparser`, `cryptography`, `tzdata`, etc.) | Various | PyPI | Various OSS maintainers | Various | Transitive | **`PROVENANCE_UNVERIFIED`** |

---

## 3. Authoritative Scientific & Legal Data Sources
| Data Source | Official URL / Origin | Authority | Actually Used | Provenance Status |
| --- | --- | --- | --- | --- |
| 《農業天然災害救助辦法》 (`M0090019`, `2026-06-29`) | `https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=M0090019` | Ministry of Justice / Ministry of Agriculture (Taiwan) | Yes (`legal_rag.sqlite`, `articles.csv`) | Verified |
| Official Appendices 1–4 (`appendix_01.pdf`–`04.pdf`) | `https://law.moj.gov.tw/` | Ministry of Agriculture (Taiwan) | Yes (`parsed_appendices.json`) | Verified |
| Sentinel-1 OPERA L2 RTC-S1 & NISAR GCOV | `https://asf.alaska.edu/` / NASA Earthdata | NASA / JPL / ASF (USA) | Yes (Local `D:\NASA\data`) | Verified |

---

## 4. Frontend Dependencies (`frontend/package.json`)
| Package | Official Source | Maintainer Organization | Actually Used | Provenance Status |
| --- | --- | --- | --- | --- |
| `react`, `react-dom`, `vite`, `typescript`, `vitest`, `maplibre-gl` | npmjs | Meta / VoidZero / Microsoft / MapLibre (OSS) | Yes | Verified (Direct) |
| Transitive npm packages (`node_modules`) | npmjs | Various OSS maintainers | Transitive | **`PROVENANCE_UNVERIFIED`** |
