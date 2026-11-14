# Development Log — Gate A.2 Approval & Phase 2 Workstreams

- **Date:** `2026-10-23`
- **Project:** SAR2Action — NISAR Earth Change Intelligence
- **Development Mode:** `PROJECT_MODE = PRE_COMPETITION_RND`

---

## 1. Gate A.2 Approval & Current State Record

### **Engineering/Product Pipeline Gate A = PASS**

1. **Approved Engineering Validation Dataset:**
   - **Track / Frame / Geometry:** Track `047`, Frame `087`, `DESCENDING`, `Left` look, `4005_DHDH_A` (`HH + HV`), `CRID = P05023`, `EPSG:32648` (`10.0 m × 10.0 m`).
   - **Scene $T_0$ (`2026-07-23`):** `NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001`
   - **Scene $T_1$ (`2026-09-21`):** `NISAR_L2_PR_GCOV_031_047_D_087_4005_DHDH_A_20260921T112603_20260921T112609_P05023_N_P_J_001`
   - **Scientific Comparability Status:** **`COMPARABLE`** (`94,293,840` common valid 10 m dual-pol pixels = `9,429.38 km²`; `80.77%` valid overlap of acquired footprint union; `93.72%` of acquired intersection; `90.82%` valid pixel IoU; bit-for-bit identical coordinate vectors).
2. **Geographic Scope Limitation (Not Final Mainland Riau Flagship Case):**
   - The validated `T047_F087` pair is approved strictly as an **engineering validation dataset**.
   - It is **NOT** approved as the final mainland Riau wildfire flagship case because both granules are ~6.0 s partial-frame acquisitions (`isFullFrame = False`) whose actual illuminated swath (`[103.12°E–105.41°E, 1.59°N–2.50°N]`) primarily covers the **Riau Archipelago (Bintan / Batam / Karimun) & Singapore Strait** rather than mainland Riau (`[100.80°E–103.20°E, -0.30°S–2.10°N]`).

---

## 2. Phase 2 Independent Workstreams

We execute two independent workstreams in parallel without letting flagship story selection block scientific engine engineering:

1. **PHASE 2A — Deterministic Change Engine (`sar/change/`):**
   - Implement windowed HDF5 reading (`reader.py`, `windows.py`), official mask + radiometric validity filtering (`masks.py`), decibel conversion (`radiometry.py`), signed $\Delta\text{HH}$, signed $\Delta\text{HV}$, $|\Delta\text{HH}|$, $|\Delta\text{HV}|$, and optional `Combined Radar Change` (`delta.py`), AOI statistical distributions & `EvidenceRecord` generation (`statistics.py`).
   - Validate deterministically against the approved `T047_F087` engineering pair and 17+ unit/regression tests.
2. **PHASE 2B — Flagship Case Discovery (`docs/science/FLAGSHIP_CASE_SELECTION.md`):**
   - Codify the Gate A.2 illumination rule (`CMR bounding-box overlap != actual SAR illumination`; check `isFullFrame` and `_LATLON.kml` / `boundingPolygon` before approving scenes) into `SCIENCE_CONTRACT.md`, `docs/science/GATE_A_PLAN.md`, and catalog screening code.
   - Retrieve and inspect the complete repeat-pass stack over **South Sumatra (`AOI-A2` — Ogan Komering Ilir peatland corridor, Track `119`, Frame `090`, `DESCENDING`, `LEFT` look, `HH + HV`, `CRID = P05023`)** and companion tracks/frames (`T018_F090`, `AOI-A1` `T148_F088`, and backup `AOI-B1`/`AOI-B2` California stacks) using lightweight sidecars (`_LATLON.kml`, `_QA_SUMMARY.csv`, `.h5.iso.xml`) to verify actual illuminated footprints and event-bracketing sequences (`T-1 → T0 → T+1`).


---

## 3. Phase 2 Execution Summary (Completed `2026-10-23`)

### 3.1 Phase 2A — Deterministic Change Engine (`COMPLETE`)
- **Modules Implemented (`sar/change/`):**
  - [`windows.py`](file:///D:/NASA/SAR2Action/sar/change/windows.py) (`GridDefinition`, `WindowSlice`, `verify_grids_compatible`, `aoi_to_window`)
  - [`masks.py`](file:///D:/NASA/SAR2Action/sar/change/masks.py) (enforces `0 < mask < 255` AND `np.isfinite(power) & (power > 0)`, rejecting `mask == 0` finite-positive-power pixels)
  - [`radiometry.py`](file:///D:/NASA/SAR2Action/sar/change/radiometry.py) (`linear_power_to_db`)
  - [`delta.py`](file:///D:/NASA/SAR2Action/sar/change/delta.py) (`compute_signed_delta_db`, `compute_magnitude_db`, `compute_combined_radar_change` with mandatory `COMBINED_RADAR_CHANGE_DISCLAIMER`)
  - [`statistics.py`](file:///D:/NASA/SAR2Action/sar/change/statistics.py) (AOI statistics including `p10/p25/p50/p75/p90`, `median_abs_change_db`, `positive_change_fraction`, `negative_change_fraction`, `numberOfLooks` summary, and `build_aoi_evidence_record`)
  - [`reader.py`](file:///D:/NASA/SAR2Action/sar/change/reader.py) & [`__init__.py`](file:///D:/NASA/SAR2Action/sar/change/__init__.py) (`read_gcov_window`, `run_aoi_change_analysis`, `export_geotiffs`)
- **Unit & Regression Tests:** `43 passed` across full test suite (including all 17 mandatory Phase 2A.8 tests in [`tests/sar/test_change_engine_phase2a.py`](file:///D:/NASA/SAR2Action/tests/sar/test_change_engine_phase2a.py)).
- **Real-Data Validation on `T047_F087`:**
  - `AOI-ENG-01` (`E-PHASE2A-ENG-001`): `2,770,530` common valid pixels (`277.053 km²`, `100.0%` valid, `COMPARABLE`), `2.59 s` runtime, `68.70 MiB` array memory (`398.5×` memory reduction vs full-frame).
  - `AOI-ENG-02` (`E-PHASE2A-ENG-002`, Swath Edge): Rejected `1,365,558` ($T_0$) and `1,587,393` ($T_1$) real `mask == 0` finite-positive-power pixels; `1,812,679` common valid pixels (`48.01%` coverage, `LIMITED`), `2.83 s` runtime.
  - Validation report: [`docs/science/CHANGE_ENGINE_VALIDATION.md`](file:///D:/NASA/SAR2Action/docs/science/CHANGE_ENGINE_VALIDATION.md).

### 3.2 Phase 2B — Flagship Case Discovery (`COMPLETE`)
- **Rule 7 (Actual Swath Illumination Verification):** Codified in [`SCIENCE_CONTRACT.md`](file:///D:/NASA/SAR2Action/SCIENCE_CONTRACT.md), [`docs/science/GATE_A_PLAN.md`](file:///D:/NASA/SAR2Action/docs/science/GATE_A_PLAN.md), [`sar/catalog/models.py`](file:///D:/NASA/SAR2Action/sar/catalog/models.py), [`sar/catalog/asf_client.py`](file:///D:/NASA/SAR2Action/sar/catalog/asf_client.py), and [`sar/validation/pair_validator.py`](file:///D:/NASA/SAR2Action/sar/validation/pair_validator.py).
- **South Sumatra (`AOI-A2` — Ogan Komering Ilir Peatland Corridor) Findings:**
  - Verified two independent **100% Full-Frame (`isFullFrame = True`)** repeat-pass stacks with **`100.0%` actual illuminated coverage of the OKI core peatland corridor (`[104.80°E, -3.60°S, 106.00°E, -2.60°S]`)**:
    1. **`T119_F090` (`DESCENDING`, `LEFT` look, `4005_DHDH_A`, `HH+HV`, `CRID = P05023`):** 9 scenes (`2026-06-22` to `2026-10-20`), unbroken 12-day cadence from `2026-08-21` to `2026-10-20`.
    2. **`T010_F176` (`ASCENDING`, `LEFT` look, `4005_DHDH_A`, `HH+HV`, `CRID = P05023`):** 9 scenes (`2026-06-26` to `2026-10-12`), `100.0%` illumination of the OKI core peatland corridor (`rfi_comparison_status = UNRELIABLE_METADATA` per `isce-framework/isce3#294`).
  - Eliminated false-positive stacks `T018_F090`, `T111_F176`, and `T119_F089` (`0.0%` overlap with OKI core peatland corridor).
  - Flagship case selection report: [`docs/science/FLAGSHIP_CASE_SELECTION.md`](file:///D:/NASA/SAR2Action/docs/science/FLAGSHIP_CASE_SELECTION.md).

---

## 4. Science Freeze + Phase 2C + Phase 3A/3B/3C Execution Summary (Completed `2026-10-24`)

### 4.1 Part 0 — Science Freeze (`COMPLETE`)
- Reconciled and froze `Combined Radar Change = abs(Delta_HH) + abs(Delta_HV)` (`L1` sum of absolute dB changes, labeled `dB composite`) across [`SCIENCE_CONTRACT.md`](file:///D:/NASA/SAR2Action/SCIENCE_CONTRACT.md), [`EVIDENCE_SCHEMA.md`](file:///D:/NASA/SAR2Action/EVIDENCE_SCHEMA.md), [`sar/change/delta.py`](file:///D:/NASA/SAR2Action/sar/change/delta.py), [`backend/app/schemas/evidence.py`](file:///D:/NASA/SAR2Action/backend/app/schemas/evidence.py), [`docs/science/CHANGE_ENGINE_VALIDATION.md`](file:///D:/NASA/SAR2Action/docs/science/CHANGE_ENGINE_VALIDATION.md), and all unit tests.
- Enforced mandatory disclaimer everywhere: `"Custom visualization metric — not a hazard score, fire probability, damage score, or official burn-severity index."`

### 4.2 Part 1 — Phase 2C & Phase 3C Final Flagship Case Lock & Validation (`COMPLETE`)
- **External Event Context:** Documented September 2026 Ogan Komering Ilir (OKI) peatland fire escalation window with full source-level provenance (`SRC-BMKG-01`, `SRC-BMKG-02`, `SRC-BNPB-01`, `SRC-BNPB-02`, `SRC-ANTARA-01`, `SRC-BPBD-01`) in [`docs/science/FLAGSHIP_EVENT_CONTEXT.md`](file:///D:/NASA/SAR2Action/docs/science/FLAGSHIP_EVENT_CONTEXT.md), strictly separated from NISAR change math.
- **Flagship Lock (Revised in Phase 3C):** Compared `F1` (`T119_F090 DESCENDING`, `2026-09-02 → 2026-09-14`) vs `F2` (`T010_F176 ASCENDING`, `2026-09-06 → 2026-09-18`) in [`docs/science/FLAGSHIP_LOCK.md`](file:///D:/NASA/SAR2Action/docs/science/FLAGSHIP_LOCK.md); set `rfi_comparison_status = UNRELIABLE_METADATA` per `isce-framework/isce3#294` and corrected filename token interpretation (`_N_F_J_` = Near Real-Time / Full / JPL; `_F_F_J_` = Forecast / Full / JPL); locked **Candidate F2 (`T010_F176 ASCENDING`, `2026-09-06 → 2026-09-18`)** as **PRIMARY FLAGSHIP PAIR** and **Candidate F1 (`T119_F090 DESCENDING`)** as **BACKUP FLAGSHIP PAIR** based on tight temporal bracketing of mid-September OKI fire escalation (`~2026-09-10` BMKG and `~2026-09-17` BNPB records), `100.0%` OKI illumination, and dawn (`05:40 WIB`) pass stability.
- **2-Granule Download & Gate A.2 Product Validation:** Downloaded `030_010_A_176` (`5,930,745,856` bytes) and `031_010_A_176` (`5,934,940,160` bytes; `11.0507 GiB` total), verified `COMPARABLE` status (`EPSG:32748`, `32,616 × 33,480`), and executed windowed Change Engine validation over `AOI-OKI-01..04` (`E-FLAGSHIP-OKI-001..004`) in [`docs/science/FLAGSHIP_CHANGE_VALIDATION.md`](file:///D:/NASA/SAR2Action/docs/science/FLAGSHIP_CHANGE_VALIDATION.md).

### 4.3 Part 2 & Part 3 — Phase 3A FastAPI Evidence API & Phase 3B Radar Reveal Frontend (`COMPLETE`)
- Implemented deterministic FastAPI service (`backend/app/main.py`, `backend/app/services/science_service.py`, `backend/app/services/layer_renderer.py`, `backend/app/schemas/api.py`) and React + TypeScript + MapLibre GL JS 2D frontend (`frontend/src/App.tsx`, `frontend/src/components/RadarMapCanvas.tsx`).
- Verified all **50 backend/science `pytest` tests** and **5 frontend `vitest` tests** (`55/55` total passing).

