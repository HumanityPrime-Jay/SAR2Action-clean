# Phase 2A — Deterministic Change Engine Scientific Validation Report

- **Project:** SAR2Action — NISAR Earth Change Intelligence
- **Development Mode:** `PROJECT_MODE = PRE_COMPETITION_RND`
- **Date:** `2026-10-23`
- **Engine Package:** [`sar/change/`](../../sar/change/) (`reader.py`, `windows.py`, `masks.py`, `radiometry.py`, `delta.py`, `statistics.py`)
- **Algorithm Version:** `sar2action-change-engine-v1.0.0`

> **Mandatory Scope Statement:**  
> **The `T047_F087` engineering pair (`2026-07-23` $\to$ `2026-09-21`) demonstrates and validates the deterministic SAR2Action processing pipeline on real NISAR L-band Level-2 GCOV granules, but it is NOT the final wildfire flagship case** (because its ~6.0 s partial-frame swath covers the Riau Archipelago / Singapore Strait rather than mainland Sumatra). Flagship case discovery is conducted independently in Phase 2B ([`docs/science/FLAGSHIP_CASE_SELECTION.md`](./FLAGSHIP_CASE_SELECTION.md)).

---

## 1. Governing Equations & Official Mask Rule

### 1.1 Official Valid Pixel Rule (`Phase 2A.2`)
From Gate A.2 product validation of NISAR Level-2 GCOV (`/science/LSAR/GCOV/grids/frequencyA/mask`), pixels can contain finite positive `HHHH` and `HVHV` float32 values even when `mask == 0` (which marks covariance estimates where at least one radar sample in the averaging set was partially focused or invalid).

Therefore, for any epoch $t \in \{T_0, T_1\}$ and polarization $p \in \{\text{HH}, \text{HV}, \text{VV}, \text{VH}\}$, a pixel $(r, c)$ is scientifically valid if and only if:

$$\text{valid}(t, p) = \bigl(0 < \text{mask}(t) < 255\bigr) \;\land\; \text{isfinite}\!\bigl(P(t, p)\bigr) \;\land\; \bigl(P(t, p) > 0\bigr)$$

where:
- `0 < mask < 255`: Valid fully-focused GCOV sample in subswath `1..254`.
- `mask == 0`: Invalid / partially-focused radar sample $\rightarrow$ **strictly excluded (`NaN`)**.
- `mask == 255` (`_FillValue`): Outside radar acquisition extent $\rightarrow$ **strictly excluded (`NaN`)**.

For multi-temporal comparison between $T_0$ and $T_1$:
- **Per-channel common validity:** $\text{valid}_{\text{common}}(p) = \text{valid}(T_0, p) \land \text{valid}(T_1, p)$
- **Dual-polarization common validity:** $\text{valid}_{\text{common}}(\text{HH}, \text{HV}) = \text{valid}_{\text{common}}(\text{HH}) \land \text{valid}_{\text{common}}(\text{HV})$
- **Anti-coercion invariant:** Invalid or masked pixels are propagated strictly as `NaN` (`float32`) and are **never** interpreted as `0.0 dB` ("no change").

### 1.2 Radiometric & Multi-Temporal Change Equations (`Phase 2A.3`)
For every valid pixel:

1. **Single-Epoch Gamma-Naught Backscatter in Decibels:**
   $$B(t, p) = 10 \log_{10}\!\bigl(P(t, p)\bigr) \quad [\text{dB}]$$
2. **Signed Multi-Temporal Backscatter Change (Preserving Sign):**
   $$\Delta_{\text{HH}} = B(T_1, \text{HH}) - B(T_0, \text{HH}) \quad [\text{dB}]$$
   $$\Delta_{\text{HV}} = B(T_1, \text{HV}) - B(T_0, \text{HV}) \quad [\text{dB}]$$
3. **Sign-Agnostic Change Magnitude:**
   $$\text{Magnitude}_{\text{HH}} = |\Delta_{\text{HH}}| \quad [\text{dB}], \qquad \text{Magnitude}_{\text{HV}} = |\Delta_{\text{HV}}| \quad [\text{dB}]$$
4. **Optional Dual-Polarization Visualization Metric (`Combined Radar Change`):**
   Computed **only** when both `HH` and `HV` exist and are valid in both scenes:
   $$\text{Combined\_Radar\_Change} = |\Delta_{\text{HH}}| + |\Delta_{\text{HV}}| \quad [\text{dB}]$$
   Always accompanied by the mandatory disclaimer:
   > `Custom visualization metric — not a hazard score, fire probability, damage score, or official burn-severity index.`

---

## 2. Actual Engineering Scenes & HDF5 Dataset Paths

| Attribute | Scene $T_0$ | Scene $T_1$ |
| :--- | :--- | :--- |
| **Granule ID** | `NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001` | `NISAR_L2_PR_GCOV_031_047_D_087_4005_DHDH_A_20260921T112603_20260921T112609_P05023_N_P_J_001` |
| **Acquisition UTC** | `2026-07-23T11:26:05.000000000Z` | `2026-09-21T11:26:03.000000000Z` |
| **Track / Frame / Orbit / Look** | Track `047`, Frame `087`, `Descending`, `Left` | Track `047`, Frame `087`, `Descending`, `Left` |
| **CRID / Product Version** | `P05023` / `1.0.11` (`PROVISIONAL`) | `P05023` / `1.0.11` (`PROVISIONAL`) |
| **CRS & Full Frame Grid** | `EPSG:32648` (`32,832 × 33,624` at `10.0 m × -10.0 m`) | `EPSG:32648` (`32,832 × 33,624` at `10.0 m × -10.0 m`) |
| **HH Power Dataset Path** | `/science/LSAR/GCOV/grids/frequencyA/HHHH` | `/science/LSAR/GCOV/grids/frequencyA/HHHH` |
| **HV Power Dataset Path** | `/science/LSAR/GCOV/grids/frequencyA/HVHV` | `/science/LSAR/GCOV/grids/frequencyA/HVHV` |
| **Validity Mask Dataset Path** | `/science/LSAR/GCOV/grids/frequencyA/mask` | `/science/LSAR/GCOV/grids/frequencyA/mask` |
| **Number of Looks Path** | `/science/LSAR/GCOV/grids/frequencyA/numberOfLooks` | `/science/LSAR/GCOV/grids/frequencyA/numberOfLooks` |

---

## 3. Validation AOIs, Pixel Counts & Output Statistics

Two real validation windows were processed via [`scripts/run_phase2a_change_engine_validation.py`](../../scripts/run_phase2a_change_engine_validation.py) and persisted to [`data/processed/phase2a_change_engine_results.json`](../../data/processed/phase2a_change_engine_results.json) and [`data/cache/evidence_store.json`](../../data/cache/evidence_store.json):

### 3.1 Validation Window 1: `AOI-ENG-01` (`E-PHASE2A-ENG-001` — Interior Full-Valid Swath Window)
- **WGS84 Bounding Box:** `[104.20°E, 1.90°N, 104.35°E, 2.05°N]`
- **UTM Grid Window Indices:** `rows = [25723:27382]` (`1,659` rows), `cols = [13382:15052]` (`1,670` cols)
- **Total Pixels Processed:** **`2,770,530` pixels** (`277.053 km²` = `27,705.3 ha`)
- **Common Valid Pixels (`HH` & `HV`):** **`2,770,530` pixels (`100.00%` valid coverage, `0.00%` missing)**
- **Quality Status:** **`COMPARABLE`**

| Metric | `HH` Channel (`E-PHASE2A-ENG-001`) | `HV` Channel (`E-PHASE2A-ENG-001`) | `Combined Radar Change` ($|\Delta\text{HH}| + |\Delta\text{HV}|$) |
| :--- | ---: | ---: | ---: |
| **Valid Pixel Count** | `2,770,530` | `2,770,530` | `2,770,530` |
| **Valid Area** | `277.053 km²` (`27,705.3 ha`) | `277.053 km²` (`27,705.3 ha`) | `277.053 km²` |
| **Missing / Invalid Fraction** | `0.0000` (`0.00%`) | `0.0000` (`0.00%`) | `0.0000` (`0.00%`) |
| **Median $T_0$ (dB)** | `-18.8799 dB` (mean `-18.9268 dB`) | `-25.4486 dB` (mean `-25.5117 dB`) | — |
| **Median $T_1$ (dB)** | `-19.1900 dB` (mean `-19.2443 dB`) | `-25.1786 dB` (mean `-25.2439 dB`) | — |
| **Median Signed $\Delta$ (dB)** | **`-0.3151 dB`** | **`+0.2688 dB`** | — |
| **Mean Signed $\Delta$ (dB)** | **`-0.3176 dB`** | **`+0.2678 dB`** | — |
| **Signed $\Delta$ Percentiles (`p10 / p25 / p50 / p75 / p90`)** | `-4.0254 / -2.2651 / -0.3151 / +1.6323 / +3.3893 dB` | `-3.1885 / -1.5478 / +0.2688 / +2.0850 / +3.7222 dB` | `1.6090 / 2.6691 / 4.1694 / 5.9580 / 7.7748 dB` |
| **Median Absolute Change $|\Delta|$ (dB)** | **`1.9607 dB`** (mean `2.3230 dB`) | **`1.8261 dB`** (mean `2.1642 dB`) | **`4.1694 dB`** (mean `4.4871 dB`) |
| **Positive-Change Fraction ($\Delta > 0$)** | `45.66%` (`0.456557`) | `53.97%` (`0.539675`) | — |
| **Negative-Change Fraction ($\Delta < 0$)** | `54.34%` (`0.543437`) | `46.03%` (`0.460318`) | — |
| **`numberOfLooks` Metadata ($T_0$ / $T_1$ median)** | `4.7397` / `4.7398` looks | `4.7397` / `4.7398` looks | Observation metadata only |

### 3.2 Validation Window 2: `AOI-ENG-02` (`E-PHASE2A-ENG-002` — Swath-Edge Window Demonstrating `mask == 0` Rejection)
- **WGS84 Bounding Box:** `[103.12°E, 2.08°N, 103.30°E, 2.25°N]`
- **UTM Grid Window Indices:** `rows = [23501:25384]` (`1,883` rows), `cols = [1370:3375]` (`2,005` cols)
- **Total Pixels in Window:** **`3,775,415` pixels** (`377.54 km²`)
- **Real `mask == 0` Rejection in Action:**
  - In $T_0$, **`1,365,558` pixels** inside `AOI-ENG-02` had `mask == 0` *yet contained finite positive `HHHH` and `HVHV` values*, and were **rejected (`NaN`)** by the official mask rule!
  - In $T_1$, **`1,587,393` pixels** inside `AOI-ENG-02` had `mask == 0` *yet contained finite positive `HHHH` and `HVHV` values*, and were **rejected (`NaN`)**!
  - Additionally, `597,178` pixels ($T_0$) and `291,009` pixels ($T_1$) had `mask == 255` (outside acquisition extent).
- **Common Valid Pixels (`HH` & `HV`):** **`1,812,679` pixels (`181.2679 km²` = `18,126.79 ha`, `coverage_ratio = 48.01%`, `missing_invalid_fraction = 51.99%`)**
- **Quality Status:** **`LIMITED`** (automatically downgraded from `COMPARABLE` because `coverage_ratio = 0.4801 < 0.50`, with `"partial_valid_coverage"` added to `limitations`).
- **Key Radiometric Metrics (`AOI-ENG-02`):**
  - `HH`: Median $T_0 = -6.4784\text{ dB}$, Median $T_1 = -5.9537\text{ dB}$, Median $\Delta\text{HH} = +0.5204\text{ dB}$ (mean $+0.5256\text{ dB}$), Median $|\Delta\text{HH}| = 2.0988\text{ dB}$, positive fraction `56.75%`, negative fraction `43.24%`.
  - `HV`: Median $T_0 = -14.3066\text{ dB}$, Median $T_1 = -13.7903\text{ dB}$, Median $\Delta\text{HV} = +0.5132\text{ dB}$ (mean $+0.5134\text{ dB}$), Median $|\Delta\text{HV}| = 2.0943\text{ dB}$, positive fraction `56.68%`, negative fraction `43.32%`.

---

## 4. Exported Validation GeoTIFF Products (`Phase 2A.5`)

For both `AOI-ENG-01` and `AOI-ENG-02`, all 11 georeferenced `EPSG:32648` 10 m GeoTIFF layers were written under [`data/processed/phase2a_validation/`](../../data/processed/phase2a_validation/):
1. `*_t0_hh_db.tif` (`float32`, `nodata = NaN`)
2. `*_t1_hh_db.tif` (`float32`, `nodata = NaN`)
3. `*_delta_hh_db.tif` (`float32`, `nodata = NaN`)
4. `*_magnitude_hh_db.tif` (`float32`, `nodata = NaN`)
5. `*_t0_hv_db.tif` (`float32`, `nodata = NaN`)
6. `*_t1_hv_db.tif` (`float32`, `nodata = NaN`)
7. `*_delta_hv_db.tif` (`float32`, `nodata = NaN`)
8. `*_magnitude_hv_db.tif` (`float32`, `nodata = NaN`)
9. `*_combined_radar_change_db.tif` (`float32`, `nodata = NaN`)
10. `*_common_valid_mask.tif` (`uint8`, `1 = valid`, `0 = invalid`)
11. `*_missing_invalid_mask.tif` (`uint8`, `1 = missing/invalid`, `0 = valid`)

---

## 5. Memory & Runtime Behavior (`Phase 2A.4`)

| Metric | Full-Frame Naive Load (`32,832 × 33,624` × 2 scenes) | Windowed Engine (`AOI-ENG-01`: `1,659 × 1,670`) | Windowed Engine (`AOI-ENG-02`: `1,883 × 2,005`) |
| :--- | ---: | ---: | ---: |
| **Pixels Read per Scene** | `1,103,943,168` px | `2,770,530` px | `3,775,415` px |
| **Raw Window Array RAM (T0 + T1)** | **`26.73 GiB`** (`28,702,522,368` B) | **`68.70 MiB`** (`72,033,780` B) | **`93.61 MiB`** (`98,160,790` B) |
| **Peak Python `tracemalloc` Memory** | Would OOM / page heavily | **`298.05 MiB`** | **`359.40 MiB`** |
| **RAM Reduction Factor** | `1.0×` | **`398.5×` smaller** | **`292.4×` smaller** |
| **End-to-End Runtime (I/O + Math + Stats)** | > 45 s | **`2.59 seconds`** | **`2.83 seconds`** |

---

## 6. Automated Unit & Regression Test Results (`Phase 2A.8`)

Executed via `C:\Users\user\.venvs\sar2action\Scripts\python.exe -m pytest -v`:
- **Total Tests Passed:** **`43 passed in 5.03s`** (`17` new Phase 2A tests in [`tests/sar/test_change_engine_phase2a.py`](../../tests/sar/test_change_engine_phase2a.py) + `26` existing Phase 0 / Phase 1 / Gate A.2 tests).
- Verified all 17 mandatory test specifications, including explicit regression tests proving that finite positive power pixels with `mask == 0` are rejected and never produce `0.0 dB` change.

---

## 7. Scientific Limitations Recorded in Every `EvidenceRecord`

1. **`cause_not_determined`**: Multi-temporal L-band radar backscatter change ($\Delta\text{HH}, \Delta\text{HV}$) measures physical shifts in surface scattering (roughness, dielectric moisture, canopy volume, or double-bounce geometry) and never by itself proves wildfire or any specific causal driver.
2. **`not_burn_severity_or_fire_damage`**: Neither $\Delta\text{HH}$, $\Delta\text{HV}$, nor `Combined Radar Change` is a calibrated burn-severity index or damage probability.
3. **`provisional_product`**: Scenes come from `NISAR_L2_GCOV_PROVISIONAL_V1` (`CRID = P05023`).
4. **Engineering Pair Scope**: `T047_F087` validates the Change Engine pipeline on real NISAR data over the Riau Archipelago, while mainland Sumatra flagship case selection is handled in Phase 2B.
