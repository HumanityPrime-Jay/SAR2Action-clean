# Phase 2C & Phase 3C — Final Flagship Case Lock (`FLAGSHIP_LOCK.md`)

**Date:** `2026-10-24` (Updated in Phase 3C Science & Demo Hardening)  
**Phase:** `Phase 2C & Phase 3C.1–3C.3 — Final Flagship Case Lock (Revised Without Unreliable RFI Ranking)`  
**Related Context:** [`docs/science/FLAGSHIP_EVENT_CONTEXT.md`](file:///D:/NASA/SAR2Action/docs/science/FLAGSHIP_EVENT_CONTEXT.md) | [`docs/science/FLAGSHIP_CHANGE_VALIDATION.md`](file:///D:/NASA/SAR2Action/docs/science/FLAGSHIP_CHANGE_VALIDATION.md)

---

## 1. Candidate Pairs Under Comparison

We evaluate the two verified full-frame (`coverage = Full`), dual-polarization (`HH + HV`), 12-day repeat-pass stacks covering **`100.00%` of the Ogan Komering Ilir (OKI) Core Peatland Corridor (`[104.80°E, -3.60°S, 106.00°E, -2.60°S]`)**:

| Attribute | **Candidate F1 (`T119_F090 DESCENDING`)** | **Candidate F2 (`T010_F176 ASCENDING`)** |
| :--- | :--- | :--- |
| **Track / Frame / Orbit / Look** | Track `119`, Frame `090`, `DESCENDING`, `LEFT` | Track `010`, Frame `176`, `ASCENDING`, `LEFT` |
| **Scene $T_0$** | `NISAR_L2_PR_GCOV_029_119_D_090_4005_DHDH_A_20260902T111855_20260902T111930_P05023_N_F_J_001` | `NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001` |
| **Scene $T_1$** | `NISAR_L2_PR_GCOV_030_119_D_090_4005_DHDH_A_20260914T111855_20260914T111929_P05023_N_F_J_001` | `NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001` |
| **Acquisition Dates (`UTC`)** | `2026-09-02T11:18:55Z` $\to$ `2026-09-14T11:18:55Z` (`12.0 d`) | `2026-09-06T22:40:25Z` $\to$ `2026-09-18T22:40:25Z` (`12.0 d`) |
| **Local Time (`WIB = UTC+7`)** | `18:18 WIB` (Evening dusk) | `05:40 WIB` (`Sept 7` $\to$ `Sept 19` pre-sunrise dawn) |
| **Native Grid (`EPSG:32748`, `10 m`)** | `X=[365040, 699840]`, `Y=[9495360, 9822240]` (`33,480 × 32,688`) | `X=[388080, 722880]`, `Y=[9496080, 9822240]` (`33,480 × 32,616`) |
| **OKI Core Peatland Illumination** | **`100.00%`** (`[104.80°E, -3.60°S, 106.00°E, -2.60°S]`) | **`100.00%`** (`[104.80°E, -3.60°S, 106.00°E, -2.60°S]`) |

---

## 2. Phase 3C Corrections to Metadata Interpretation

### 2.1 Correction 1 — RFI Metadata Status (`rfi_comparison_status = UNRELIABLE_METADATA`)

> [!WARNING]
> **Official ISCE3 / NISAR Metadata Caveat (`isce-framework/isce3#294`):**  
> In `NISAR_L2_GCOV_PROVISIONAL_V1` (`CRID = P05023`, `ISCE3 softwareVersion = 0.25.16`), the `_QA_STATS.h5` dataset `/science/LSAR/RFI/data/frequencyA/{HH,HV}/rfiLikelihood` carries the attribute description *"Value is in the interval [0,1], where 0: lowest severity, and 1: highest severity"*. However, as documented in **`isce-framework/isce3#294`**, the upstream tone-rank RFI detector can populate unnormalized Interference-to-Signal-Ratio (ISR)-like values far exceeding `1.0` (`389.36` to `723.75` in F2; `171,932.25` to `127,551,232.0` in F1), and `/science/LSAR/GCOV/metadata/processingInformation/parameters/rfiMitigationApplied` is `False` (with no RFI algorithm name or scale normalization recorded in `/science/LSAR/GCOV/metadata/processingInformation/algorithms`).
>
> **Mandatory Rule Applied:**
> - Raw `rfiLikelihood` scalars **cannot** be compared across scenes or tracks as numeric ratios (all earlier scalar ratio comparisons are **retracted and removed**).
> - Both Candidate F1 and Candidate F2 are assigned **`rfi_comparison_status = UNRELIABLE_METADATA`**.
> - Potential L-band RFI is treated strictly as **known limitation / QA context**, not a flagship-selection score.

### 2.2 Correction 2 — NISAR Granule Filename Orbit-Fidelity & Coverage Tokens

According to the official NISAR L2 GCOV granule naming convention:
`NISAR_L2_PR_GCOV_<CCC>_<RRR>_<A/D>_<FFF>_<MMMM>_<PPPP>_<O>_<Start>_<End>_<CRID>_<A>_<C>_<L>_<NNN>`

The three single-character tokens immediately following `<CRID>` (`P05023`) are:
1. **`<A>` (`orbit_pointing_fidelity_code`):**
   - `P` = **Precise**
   - `M` = **Medium**
   - `N` = **Near Real-Time**
   - `F` = **Forecast**
2. **`<C>` (`coverage_code`):**
   - `F` = **Full** (`isFullFrame = True`)
   - `P` = **Partial** (`isFullFrame = False`)
3. **`<L>` (`sds_location_code`):**
   - `J` = **JPL**

Therefore:
- `P05023_N_F_J_001` (`F1 T0`, `F1 T1`, and `F2 T0`) means: `CRID = P05023`, **`orbit/radar-pointing fidelity = Near Real-Time (N)`**, **`coverage = Full (F)`**, **`SDS location = JPL (J)`**.
- `P05023_F_F_J_001` (`F2 T1`, `2026-09-18`) means: `CRID = P05023`, **`orbit/radar-pointing fidelity = Forecast (F)`**, **`coverage = Full (F)`**, **`SDS location = JPL (J)`**.
- **`F` (`Forecast`) is NOT an upgrade over `N` (`Near Real-Time`)**; in the nominal filename latency/fidelity hierarchy (`P > M > N > F`), `Forecast` is a lower nominal tier than `Near Real-Time` (representing a mild filename metadata advantage for F1 `N → N` over F2 `N → F`, although direct inspection of F2's HDF5 `/science/LSAR/GCOV/metadata/orbit/orbitType` confirms both `030_010_A_176` and `031_010_A_176` actually used `MOE` [Medium Orbit Ephemeris] state vectors and achieved `0.000 m` geocoded grid alignment).

---

## 3. Revised 10-Criterion Decision Matrix (`Phase 3C.3` — Without RFI or Mean-Change Ranking)

We re-evaluate Candidate F1 (`T119_F090 DESCENDING`, `2026-09-02 → 2026-09-14`) and Candidate F2 (`T010_F176 ASCENDING`, `2026-09-06 → 2026-09-18`) strictly across the 10 defensible scientific and operational criteria:

| # | Defensible Criterion | **Candidate F1 (`T119_F090 DESCENDING`, `2026-09-02 → 2026-09-14`)** | **Candidate F2 (`T010_F176 ASCENDING`, `2026-09-06 → 2026-09-18`)** | Assessment |
| :-: | :--- | :--- | :--- | :---: |
| **1** | **Actual OKI Illuminated Coverage** | **`100.00%`** of OKI Core Peatland Corridor (`[104.80°E, -3.60°S, 106.00°E, -2.60°S]`) verified via `_LATLON.kml` (`isFullFrame = True`, `F` coverage token). | **`100.00%`** of OKI Core Peatland Corridor (`[104.80°E, -3.60°S, 106.00°E, -2.60°S]`) verified via `_LATLON.kml` and full HDF5 product (`isFullFrame = True`, `F` coverage token). | **Tie (`PASS`)** |
| **2** | **Same-Track / Same-Frame Compatibility** | Same Track `119`, Frame `090`, `DESCENDING`, `LEFT` look, `4005_DHDH_A` (`HH + HV`). | Same Track `010`, Frame `176`, `ASCENDING`, `LEFT` look, `4005_DHDH_A` (`HH + HV`). | **Tie (`PASS`)** |
| **3** | **12-Day Repeat Interval** | Exact `12.00-day` single orbital cycle (`Cycle 029 → Cycle 030`). | Exact `12.00-day` single orbital cycle (`Cycle 030 → Cycle 031`). | **Tie (`PASS`)** |
| **4** | **Actual Product Grid Compatibility** | `EPSG:32748`, `10 m × -10 m`, `32,688 × 33,480` (verified via `_QA_SUMMARY.csv` & `_QA_STATS.h5`). | `EPSG:32748`, `10 m × -10 m`, `32,616 × 33,480` (**verified directly on full HDF5 coordinate vectors `xCoordinates`, `yCoordinates` with `0.000 m` offset**). | **F2 Verified on Full HDF5 (`PASS`)** |
| **5** | **Valid Pixel Coverage** | `_QA_SUMMARY.csv` `PASS` (no NaN/Inf/fill anomalies inside illuminated swath). | **`100.00%` common valid pixels (`0 < mask < 255 & P > 0`) verified across `16,049,375` pixels (`1,604.94 km²`) in 4 OKI AOIs (`AOI-OKI-01..04`).** | **F2 Verified on Full HDF5 (`PASS`)** |
| **6** | **Product Maturity / CRID** | `NISAR_L2_GCOV_PROVISIONAL_V1`, `CRID = P05023`, `productVersion = 1.0.11`, `ISCE3 0.25.16`. | `NISAR_L2_GCOV_PROVISIONAL_V1`, `CRID = P05023`, `productVersion = 1.0.11`, `ISCE3 0.25.16`. | **Tie (`PROVISIONAL`)** |
| **7** | **Temporal Bracketing of Independently Documented South Sumatra / OKI Fire Activity** | `2026-09-02 → 2026-09-14`: Brackets early September (`SRC-BNPB-01`, `2026-09-05`) and the `~2026-09-10` BMKG drought/hotspot bulletin (`SRC-BMKG-01`), but **ends on `2026-09-14`**, three days **before** the documented mid-September (`~2026-09-17`) BNPB Chief / Menko Polkam emergency escalation and 12,285-personnel / 7-helicopter surge (`SRC-BNPB-02`). | **`2026-09-06 → 2026-09-18`:** Starts immediately after the `2026-09-05` BNPB baseline report (`SRC-BNPB-01`) and **directly brackets both the `~2026-09-10` BMKG hotspot/smoke advisory (`SRC-BMKG-01`) AND the `~2026-09-17` BNPB / Kemenko Polkam emergency response peak in South Sumatra & OKI (`SRC-BNPB-02`)** before `T1` (`2026-09-18T22:40Z`). | **F2 Advantage (Stronger Event Bracketing)** |
| **8** | **Acquisition Geometry & Diurnal Limitations** | `DESCENDING`, `LEFT` look; acquired at `11:18 UTC` (**`18:18 WIB` evening dusk**), after peak afternoon solar heating and convective boundary-layer activity. | `ASCENDING`, `LEFT` look; acquired at `22:40 UTC` (**`05:40 WIB` pre-sunrise dawn**), when surface dielectric conditions and atmospheric water vapor are diurnally more uniform. | **F2 Slight Advantage (Dawn Stability)** |
| **9** | **Orbit Fidelity Metadata (Described Correctly)** | Filename tokens: `T0 = N` (`Near Real-Time`), `T1 = N` (`Near Real-Time`). Uniform filename fidelity token across both scenes. | Filename tokens: `T0 = N` (`Near Real-Time`), `T1 = F` (`Forecast` — nominal lower fidelity tier in filename, **not** an upgrade). However, internal HDF5 `/science/LSAR/GCOV/metadata/orbit/orbitType` is `MOE` (Medium Orbit Ephemeris) in **both** `T0` and `T1`, and geocoded 10 m grids match with `0.000 m` offset. | **F1 Slight Filename Token Advantage (`N/N` vs `N/F`), Mitigated by Identical `MOE` Internal Orbit Type in F2** |
| **10** | **RFI Metadata (`Only if Demonstrably Comparable`)** | **`rfi_comparison_status = UNRELIABLE_METADATA`** (`freqA rfiLikelihood` exceeds `[0,1]` per `isce-framework/isce3#294`; `rfiMitigationApplied = False`). Not used for ranking. | **`rfi_comparison_status = UNRELIABLE_METADATA`** (`freqA rfiLikelihood` exceeds `[0,1]` per `isce-framework/isce3#294`; `rfiMitigationApplied = False`). Not used for ranking. | **Tie (`UNRELIABLE_METADATA` — Excluded from Ranking)** |

---

## 4. Final Flagship Decision (`Phase 3C.3`)

- **PRIMARY FLAGSHIP PAIR (CONFIRMED & LOCKED):** **Candidate F2 — `T010_F176 ASCENDING` (`2026-09-06 → 2026-09-18`)**
  - **`T0` (`2026-09-06T22:40:25Z`):** `NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001` (`Near Real-Time` filename token / `MOE` internal orbit, `Full` coverage, `JPL`)
  - **`T1` (`2026-09-18T22:40:25Z`):** `NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001` (`Forecast` filename token / `MOE` internal orbit, `Full` coverage, `JPL`)
  - **Defensible Rationale (Independent of RFI and Frame-Wide Mean Change):**
    1. **Superior Temporal Bracketing of Authoritative Event Milestones:** `2026-09-06 → 2026-09-18` spans the exact 12-day window encompassing both the `~2026-09-10` BMKG South Sumatra hotspot/smoke bulletin (`SRC-BMKG-01`) and the `~2026-09-17` BNPB / Kemenko Polkam emergency response escalation in Ogan Komering Ilir (`SRC-BNPB-02`).
    2. **100.00% Illuminated & Valid Coverage Over OKI:** Full-frame (`coverage = Full`) coverage of the entire OKI peatland corridor (`[104.80°E, -3.60°S, 106.00°E, -2.60°S]`) with `100.00%` common valid pixels verified directly on the downloaded 11.05 GiB HDF5 pair across all four OKI AOIs (`AOI-OKI-01..04`).
    3. **Diurnal Dawn Consistency:** Pre-sunrise `05:40 WIB` (`22:40 UTC`) pass timing minimizes afternoon convective and thermal surface transients.
    4. **Explicitly Documented Limitations:** `PROVISIONAL` maturity (`CRID = P05023`), `T1` filename fidelity token `F = Forecast` (with internal `orbitType = MOE`), `rfi_comparison_status = UNRELIABLE_METADATA` (`isce-framework/isce3#294`), and `CAUSE NOT DETERMINED`.
- **BACKUP FLAGSHIP PAIR:** **Candidate F1 — `T119_F090 DESCENDING` (`2026-09-02 → 2026-09-14`)**
  - **`T0` (`2026-09-02T11:18:55Z`):** `NISAR_L2_PR_GCOV_029_119_D_090_4005_DHDH_A_20260902T111855_20260902T111930_P05023_N_F_J_001`
  - **`T1` (`2026-09-14T11:18:55Z`):** `NISAR_L2_PR_GCOV_030_119_D_090_4005_DHDH_A_20260914T111855_20260914T111929_P05023_N_F_J_001`

---

## 5. Granule Download & Product-Level Verification Record (`Phase 2C.5 & 2C.6`)

| Field | Value |
| :--- | :--- |
| **Target Directory** | `D:\NASA\SAR2Action\data\raw\scenes\` |
| **File 1 ($T_0$)** | `NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001.h5` (`5,930,745,856` bytes / `5.5234 GiB`) |
| **File 2 ($T_1$)** | `NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001.h5` (`5,934,940,160` bytes / `5.5273 GiB`) |
| **Combined Pair Byte Size** | **`11,865,686,016` bytes (`11.0507 GiB`, strictly 2 granules)** |
| **Free Disk Space on `D:\`** | `86.79 GiB` pre-download $\to$ **`75.42 GiB` post-download** |
| **Gate A.2 Product Validation Status** | **`COMPARABLE` (`PASS`)** — `EPSG:32748`, `32,616 × 33,480` at `(10.0 m, -10.0 m)`, `0.000 m` grid offset |
