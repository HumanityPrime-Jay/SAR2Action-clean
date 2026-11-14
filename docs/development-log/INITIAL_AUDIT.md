# Phase 0 Initial Project & Workspace Audit

- **Date:** 2026-10-23
- **Project:** SAR2Action — NISAR Earth Change Intelligence
- **Challenge:** NASA Space Apps Challenge 2026 (*Dancing with the SARs*)
- **Development Mode:** `PROJECT_MODE = PRE_COMPETITION_RND`
- **Master Source of Truth:** `D:\NASA\NASA計劃書.docx` (Read in full; 34 sections; untouched and preserved)

---

## 1. Understanding of the Project

Based on a complete reading of `D:\NASA\NASA計劃書.docx` (Sections 0–34), **SAR2Action** is positioned NOT as an "AI Wildfire Prediction System", NOT as "Another SAR Viewer", and NOT as "ChatGPT for Satellite Images".

Instead, **SAR2Action** is:
> **A NISAR-native Earth Change Intelligence platform that enables non-SAR specialists to see Earth-surface change, understand radar evidence, recognize what remains unknown, and transform investigations into verifiable, claim-to-pixel scientific stories.**

### 1.1 Strategic Architecture: Platform + Flagship Story
- **Platform:** `SAR2Action` (applicable to wildfire, subsidence, earthquake, flood, wetland change, forest disturbance, and agriculture).
- **Flagship Story:** *When Fire Becomes Hard to See* — focusing on post-fire landscape and surface scattering changes where optical imagery or simple active-fire points cannot answer what happened to the surface structure afterward.
- **Science-First Case Hierarchy:**
  - **Case A:** Indonesia wildfire / peatland-related landscape (strongest narrative hook, subject to Gate A data verification).
  - **Case B:** 2026 California wildfire-related NISAR observations (strong reference methodology and data density).
  - **Case C:** Another region with strong, scientifically valid NISAR L-band GCOV surface change (disaster type unconstrained).
  - **Rule:** *Science quality > story preference.*

### 1.2 Three Hero User Experiences
Only three core experience names are surfaced to judges and users:
1. **Radar Reveal** (*See change*): Transforms raw grayscale NISAR GCOV imagery into an interpretable comparison (`T0`, `T1`, swipe, directional change $+\Delta / -\Delta$, magnitude $|\Delta|$, comparable area, and insufficient-evidence mask). Never labels radar change as "burn severity" or "fire damage".
2. **Radar Fingerprint** (*Understand change*): Point, polygon, or AOI inspection answering three questions: *What changed? How much? Can we trust this comparison?* Displays actual available polarizations (`HH`, `HV`, `ΔHH`, `ΔHV`), valid pixel count, comparable coverage ratio, and scene pair QA status. Gracefully handles `null / unavailable` polarizations without fabricating channels.
3. **Evidence Story** (*Verify & communicate change*): Converts an investigation into a 5-scene interactive narrative (*Scene 1: Before*, *Scene 2: The Shift*, *Scene 3: Investigate*, *Scene 4: What We Know / What We Don't Know*, *Scene 5: Evidence Story*). Every quantitative statement links back to an `evidence_id` via the **Claim-to-Pixel Evidence Ledger** (*One claim → One evidence trail*).

### 1.3 Underlying Pillar Mechanisms
- **Scene Pair Compatibility Gate (`validate_scene_pair`)**: Mandatory deterministic check before any change calculation. Rejects incompatible pairs (`These observations cannot be reliably compared`).
- **Unknown-Aware Science**: Every spatial unit and analysis output carries an explicit epistemic status (`OBSERVED`, `COMPARABLE`, `LIMITED`, `INSUFFICIENT_EVIDENCE`). Missing data is never treated as "no change".
- **Single-Orchestrator AI Earth Investigator**: Translates user intent into deterministic tool calls (`list_nisar_observations`, `validate_scene_pair`, `compute_change_map`, `summarize_selection`, `get_radar_fingerprint`, `inspect_provenance`, `set_map_view`, `build_evidence_story`). Every response enforces a 4-part structure: *Observation*, *Possible Interpretation*, *Unknown / Limitation*, and *Evidence*.

---

## 2. Current Files & Environment Found in `D:\NASA`

### 2.1 Workspace Files Inspected
Prior to scaffolding `D:\NASA\SAR2Action\`, `D:\NASA` contained a single file:

| File Path | Size (Bytes) | Last Modified | Status |
| :--- | ---: | :--- | :--- |
| `D:\NASA\NASA計劃書.docx` | 238,464 | 2026-10-23 20:12 | Preserved untouched (read-only extraction verified all 34 sections) |

No pre-existing `.git` repository or code files existed in `D:\NASA`.

### 2.2 Host Workstation Tooling Audit
Inspection of the Windows workstation revealed a rich set of pre-installed tools:

| Tool / Runtime | Installed Version | Binary Path / Notes |
| :--- | :--- | :--- |
| **OS** | Windows (x64) | PowerShell active |
| **Python** | Python 3.13.9 | `C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe` |
| **Git** | 2.54.0.windows.1 | Available on `PATH` |
| **Node.js / npm** | v24.16.0 / 11.13.0 | Available on `PATH` for React + TypeScript + MapLibre GL JS |
| **`uv` / `conda`** | Not installed | Standard `python -m venv` + `pip` available and fast |

### 2.3 Python Package Audit (Global Python 3.13 Environment)
| Package | Installed Version | Role in SAR2Action | Status |
| :--- | :--- | :--- | :--- |
| `numpy` | 2.4.4 | Array math, dB conversion, masking | Installed |
| `scipy` | 1.17.1 | Statistical summaries & spatial filters | Installed |
| `rasterio` | 1.4.3 | GeoTIFF I/O, CRS, affine transforms, reprojection (includes bundled GDAL) | Installed |
| `geopandas` | 1.1.3 | AOI / ROI vector handling | Installed |
| `shapely` | 2.1.2 | Polygon intersection, overlap ratios, geometry validation | Installed |
| `pyproj` | 3.7.2 | CRS transformation & UTM zone verification | Installed |
| `pyogrio` / `fiona` | 0.12.1 / 1.10.1 | Fast vector I/O | Installed |
| `xarray` | 2025.1.1 | Labeled multi-dimensional array handling | Installed |
| `fastapi` | 0.133.1 | Deterministic REST API & tool server | Installed |
| `pydantic` | 2.12.5 | Strict Evidence, Pair QA, and Fingerprint schemas | Installed |
| `uvicorn` | 0.41.0 | ASGI server | Installed |
| `pytest` | 9.0.3 | Automated unit and scientific regression testing | Installed |
| `httpx` / `requests` | 0.28.1 / 2.33.0 | CMR / ASF API queries | Installed |
| `pystac` | 1.14.3 | STAC catalog metadata parsing | Installed |
| `python-docx` | 1.2.0 | Proposal document reader | Installed |
| **`h5py`** | **Not installed** | **Required for reading NISAR Level-2 GCOV HDF5 granules** | **Install in `.venv`** |
| **`asf_search` / `earthaccess`** | **Not installed** | **Recommended for Gate A NISAR granule discovery via ASF DAAC / NASA CMR** | **Install in `.venv`** |

---

## 3. Proposed System Architecture

We follow the strict **Science-Outward Build Order**:
$$\text{DATA} \rightarrow \text{VALIDATION} \rightarrow \text{SCIENCE} \rightarrow \text{EVIDENCE} \rightarrow \text{API} \rightarrow \text{MAP} \rightarrow \text{AGENT} \rightarrow \text{STORY}$$

1. **SAR Data & Catalog Layer (`sar/ingest`, `sar/catalog`)**: Reads NISAR L-band Level-2 GCOV HDF5 hierarchy (`/science/LSAR/GCOV/grids/frequencyA/...` or `/science/LSAR/identification/...`), extracts acquisition UTC, orbit/track/frame, look direction, CRID, frequency, available diagonal terms (`HHHH`, `HVHV`, `VVVV`), projection (`epsg`), grid coordinates (`xCoordinates`, `yCoordinates`), and mask datasets.
2. **Deterministic Pair Validation Gate (`sar/validation`)**: `validate_scene_pair(scene_a, scene_b, aoi)` checks spatial intersection, distinct timestamps, frequency band match, common diagonal polarizations, orbit/pass consistency, CRID/maturity compatibility, CRS/grid alignment, and valid-pixel overlap ratio. Returns a structured `ScenePairValidationResult`. Blocks downstream computation on failure.
3. **Radiometric Change & Statistics Engine (`sar/change`, `sar/statistics`)**: Masks non-positive power ($P \le 0$), `NaN`, and invalid mask flags; converts valid positive $\gamma^0$ linear power to decibels $B(t,p) = 10\log_{10}(P(t,p))$; computes $\Delta(p) = B(t_1,p) - B(t_0,p)$, $|\Delta(p)|$, and optional dual-pol $D = |\Delta_{\text{HH}}| + |\Delta_{\text{HV}}|$; extracts exact AOI pixel statistics.
4. **Evidence Engine & Provenance Ledger (`backend/app/evidence`, `sar/provenance`)**: Persists immutable `EvidenceRecord` objects to a deterministic JSON store, indexing every metric by `evidence_id` with full provenance so any narrative claim can be traced back to the exact scene pair, AOI geometry, polarization, algorithm version, and valid pixel count.
5. **FastAPI & Single-Agent Tool Layer (`backend/app/api`, `backend/app/tools`)**: Exposes REST endpoints for the frontend and strictly typed deterministic tools for the single AI orchestrator.
6. **2D WebGIS Frontend (`frontend/src`)**: React + TypeScript + MapLibre GL JS implementing *Radar Reveal*, *Radar Fingerprint*, *Claim-to-Pixel Evidence Ledger*, and the *5-Scene Evidence Story*.

---

## 4. Key Scientific Assumptions

1. **Physical Quantity of GCOV Diagonal Terms**: NISAR L-band Level-2 GCOV diagonal grid datasets (`HHHH`, `HVHV`, `VVVV`) represent radiometrically terrain-corrected (RTC) gamma-naught ($\gamma^0$) backscatter power in linear units ($P > 0$).
2. **Logarithmic Transformation Domain**: Decibel conversion $B = 10\log_{10}(P)$ is strictly defined only on finite, positive real values ($0 < P < \infty$) where the GCOV mask indicates valid observation. Pixels with $P \le 0$, `NaN`, fill value, or radar shadow/layover mask are flagged as invalid (`INSUFFICIENT_EVIDENCE`) and never coerced to `0 dB` or `no change`.
3. **Sign-Agnostic Surface Change**: Fire or land disturbance in vegetated/peat landscapes can either decrease backscatter (e.g., canopy loss reducing volume scattering in HV) or increase backscatter (e.g., exposure of rough surface, moisture shifts, or double-bounce changes in HH). Therefore, the engine preserves both signed change ($\Delta$) and sign-agnostic magnitude ($|\Delta|$).
4. **Non-Equivalence of Observation and Attribution**: A statistically large $|\Delta|$ proves *radar-observed surface scattering change* between $T_0$ and $T_1$. It never by itself proves wildfire occurrence, burn severity, underground peat smoldering, or ecological recovery.

---

## 5. Unresolved Questions

Recorded in detail in [`docs/decisions/OPEN_QUESTIONS.md`](../decisions/OPEN_QUESTIONS.md):
1. **OQ-001 (Gate A Data Availability)**: Which specific NISAR L-band Level-2 GCOV granules (commissioned science or sample/provisional products on ASF DAAC / NASA Earthdata as of 2026-10-23) provide $\ge 2$ co-registered, same-orbit repeat-pass observations over Case A (Indonesia), Case B (California), or Case C?
2. **OQ-002 (Frequency A vs. Frequency B Split-Spectrum)**: When a NISAR GCOV granule contains both `frequencyA` (main science band, typically 20/40 MHz) and `frequencyB` (5 MHz), should the default reader lock strictly to `frequencyA` unless explicitly queried? (Proposed default: `frequencyA`).
3. **OQ-003 (RTC Area Normalization Factor / Mask Encoding)**: Exact bitmask values in the NISAR GCOV `mask` dataset across different CRID versions (e.g., valid data vs. shadow/layover vs. sub-swath gap) must be verified directly against the actual HDF5 attributes of the Gate A granules.
4. **OQ-004 (2026-10-28 Official Challenge Statement Rules on External Context)**: Whether the final Space Apps 2026 *Dancing with the SARs* rules encourage or restrict external context overlays (e.g., historical fire perimeters, place names). Our architecture isolates context in a toggleable `ContextLayer` that never touches the quantitative change engine.

---

## 6. Development Risks & Mitigations

| Risk ID | Risk Description | Likelihood | Impact | Mitigation Strategy |
| :--- | :--- | :---: | :---: | :--- |
| **R-01** | Candidate Case A (Indonesia) lacks $\ge 2$ comparable repeat-pass NISAR GCOV scenes in the public archive. | Medium–High | High | Enforce **Gate A** first: evaluate Case A, Case B (California), and Case C in parallel; select purely on science comparability. |
| **R-02** | NISAR GCOV HDF5 files are multi-gigabyte granules that slow down interactive API queries if read raw on every click. | High | Medium | Crop/window to AOI bounding box during ingestion and cache validated, aligned COG/GeoTIFF subsets in `data/processed/`. |
| **R-03** | Ascending vs. descending pass pairs or mismatched look angles introduce geometric artifacts mistaken for surface change. | Medium | High | `validate_scene_pair` checks `lookDirection` and `orbitPassDirection` (and relative orbit/track), flagging mismatches as incompatible or `LIMITED`. |
| **R-04** | Missing cross-pol (`HVHV`) in single-pol acquisitions causes runtime crashes or misleading visualizations. | Medium | Medium | Schema and UI treat every polarization channel as optional (`Optional[PolarizationStats]`); UI renders `HV unavailable` explicitly. |
| **R-05** | LLM invents decibel numbers or claims "fire destroyed X hectares". | Medium | Critical | Strict tool-only numbers + output parser/validator verifying every number maps to an `evidence_id` and blocking forbidden causal phrases. |

---

## 7. Dependency & Windows Environment Recommendations

1. **Use `rasterio` (1.4.3, already installed) rather than raw `osgeo.gdal` pip builds**: On Windows Python 3.13, `rasterio` and `pyogrio` ship with pre-compiled binary GDAL libraries included. Do not attempt `pip install gdal` from source on Windows.
2. **Create a lightweight virtual environment with `--system-site-packages`**:
   - Inherits the already-verified Windows binary wheels (`numpy`, `scipy`, `rasterio`, `geopandas`, `shapely`, `pyproj`, `fastapi`, `pydantic`, `pytest`).
   - Install `h5py` and `asf_search` inside `.venv` so the global Python installation remains untouched.
3. **Path Handling**:
   - Always use `pathlib.Path` across all modules.
   - Avoid POSIX string concatenation (`+ "/"`).
4. **HDF5 File Locking on Windows**:
   - Windows enforces strict OS file locks on open HDF5 handles. Always open `h5py.File(path, "r")` inside a `with` context manager and close immediately after reading window slices; set `HDF5_USE_FILE_LOCKING=FALSE` in read-only pipelines if concurrent readers access the same granule.

---

## 8. Competition-Compliance Considerations (`PRE_COMPETITION_RND`)

- **Current Date:** 2026-10-23 (5 days before the 2026-10-28 full challenge statement).
- **Allowed Scope Now:** Architecture, schemas, scientific contracts, generic GCOV readers, deterministic pair validation logic, unit tests on synthetic arrays (explicitly labeled as unit-test fixtures in `tests/`), and Gate A catalog search scripts.
- **Strictly Prohibited Now:** Representing R&D scaffolding as the final competition submission; fabricating "real" NISAR wildfire results; hardcoding causal claims.
- **Toggleable Context Layer (`ENABLE_EXTERNAL_CONTEXT=true|false`)**: Ensures immediate compliance on 2026-10-28 regardless of whether external contextual perimeters are encouraged or disallowed.
