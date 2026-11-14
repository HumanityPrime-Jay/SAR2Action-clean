# PHASE 2C.6, 2C.7 & PHASE 3C — Flagship Product-Level Validation & Change Engine Validation Report

**Date:** 2026-10-24 (Updated in Phase 3C Science & Demo Hardening)  
**Development Mode:** `PROJECT_MODE = PRE_COMPETITION_RND`  
**Case ID:** `case-flagship-oki-f2`  
**Locked Primary Flagship Pair:** Candidate F2 — `T010_F176 ASCENDING` (`2026-09-06 → 2026-09-18`)  
**Product-Level Gate A.2 Status:** **`COMPARABLE` (`PASS`)**  
**Frozen Combined Metric Formula:** $\text{Combined Radar Change} = |\Delta_{\text{HH}}| + |\Delta_{\text{HV}}|$ (`unit = dB composite`, custom change magnitude / sum of absolute dB changes)  
**RFI Comparison Status:** `rfi_comparison_status = UNRELIABLE_METADATA` (`isce-framework/isce3#294`)  

---

## 1. Executive Summary

Following the Phase 2C/3C Flagship Lock ([`docs/science/FLAGSHIP_LOCK.md`](file:///D:/NASA/SAR2Action/docs/science/FLAGSHIP_LOCK.md)) and External Event Context review ([`docs/science/FLAGSHIP_EVENT_CONTEXT.md`](file:///D:/NASA/SAR2Action/docs/science/FLAGSHIP_EVENT_CONTEXT.md)), the two locked NISAR L-band Level-2 GCOV granules for **Candidate F2 (`T010_F176 ASCENDING`, `2026-09-06 → 2026-09-18`)** were downloaded from NASA Earthdata / ASF (`11.0507 GiB` total) and subjected to:

1. **Step 1.6 — Gate A.2 Product-Level Validation:** Direct HDF5 inspection of `/science/LSAR/identification`, `/science/LSAR/GCOV/metadata/processingInformation`, `/science/LSAR/GCOV/metadata/orbit`, and `/science/LSAR/GCOV/grids/frequencyA` (`HHHH`, `HVHV`, `mask`, `numberOfLooks`, `xCoordinates`, `yCoordinates`, `projection`) confirmed exact `EPSG:32748` (`UTM Zone 48S`) `10.0 m × -10.0 m` grid alignment across all `32,616 × 33,480` (`1,091,983,680`) pixels. Candidate F2 is promoted from `CATALOG_SCREENED` to **`COMPARABLE`**.
2. **Step 1.7 & Phase 3C — Flagship AOI Change Engine Validation (Including Predefined External-Context AOI):** The deterministic Change Engine (`sar/change/`) was executed across four Ogan Komering Ilir (OKI) peatland windows:
   - **`AOI-OKI-01`, `AOI-OKI-02`, `AOI-OKI-03`** (`selection_method = PREDEFINED_GEOGRAPHIC_AOI`, `selection_time = PRE_ANALYSIS`)
   - **`AOI-OKI-04` (`[105.08, -2.92, 105.24, -2.76]`) — Padang Sugihan Peatland Reserve & Buffer Corridor** (`selection_method = PREDEFINED_EXTERNAL_CONTEXT`, `selection_time = PRE_ANALYSIS`), predefined from external ANTARA/Polda Sumsel/BPBD and BMKG event reports on *Suaka Margasatwa Padang Sugihan* **before** inspecting its radar-change statistics.
   Together, the four preset OKI AOIs total **16,042,517 common valid 10 m pixels (`1,604.25 km²` / `160,425.17 ha`)**, achieving **`100.00%` valid comparable coverage** in every window and exporting 44 georeferenced QA GeoTIFFs (`data/processed/phase2c_flagship/`), 40 RGBA PNG web overlays (`data/cache/layer_pngs/`), and 4 immutable `EvidenceRecord`s (`E-FLAGSHIP-OKI-001` through `E-FLAGSHIP-OKI-004`) in `data/cache/evidence_store.json`.

---

## 2. Step 1.6 — Gate A.2 Product-Level HDF5 Validation (`T010_F176 ASCENDING`)

### 2.1 Downloaded Granule Inventory, Orbit/Coverage Suffix Semantics, & Disk Budget

Per official NISAR GCOV granule naming convention (`..._CRID_OrbitFidelity_Coverage_SDSLocation_Counter`), the three single-letter tokens following `P05023` are:
1. **Orbit / Radar-Pointing Fidelity:** `P = Precise`, `M = Medium`, `N = Near Real-Time`, `F = Forecast`
2. **Coverage Indicator:** `F = Full`, `P = Partial`
3. **SDS Production Location:** `J = JPL`

*(Note: Internally, both HDF5 granules record `/science/LSAR/GCOV/metadata/orbit/orbitType = MOE` [Medium Orbit Ephemeris] and achieve exact 0.000 m `EPSG:32748` grid alignment.)*

| Role | Granule ID | Local HDF5 Path | Exact Size (Bytes) | Size (GiB) | Acquisition Window (UTC) | CRID / Version | Filename Suffix Semantics (`_Orbit_Coverage_SDS_`) |
| :--- | :--- | :--- | :---: | :---: | :--- | :---: | :--- |
| **`T0`** | `NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001` | `data/raw/scenes/NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001.h5` | `5,930,745,856` | `5.5234 GiB` | `2026-09-06T22:40:25Z` – `22:41:00.999Z` | `P05023` / `1.0.11` | `_N_F_J_` (`N = Near Real-Time`, `F = Full`, `J = JPL`; internal HDF5 `orbitType = MOE`) |
| **`T1`** | `NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001` | `data/raw/scenes/NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001.h5` | `5,934,940,160` | `5.5273 GiB` | `2026-09-18T22:40:25Z` – `22:41:00.999Z` | `P05023` / `1.0.11` | `_F_F_J_` (`F = Forecast`, `F = Full`, `J = JPL`; internal HDF5 `orbitType = MOE`) |
| **Total** | **2 Full-Frame Granules** | `D:\NASA\SAR2Action\data\raw\scenes\` | **`11,865,686,016`** | **`11.0507 GiB`** | **12.00-day exact repeat pass** | **`P05023`** | **Free disk after download: `75.34 GiB`** |

### 2.2 Product-Level Compatibility Verification Matrix

| Check Category | HDF5 Dataset / Path | `T0` (`2026-09-06`) | `T1` (`2026-09-18`) | Gate A.2 Result |
| :--- | :--- | :--- | :--- | :---: |
| **Frequency Band & Group** | `/science/LSAR/GCOV/grids/frequencyA` | L-band (`frequencyA`, 40 MHz) | L-band (`frequencyA`, 40 MHz) | **PASS** |
| **Polarizations** | `listOfPolarizations` | `['HH', 'HV']` (`HHHH`, `HVHV`) | `['HH', 'HV']` (`HHHH`, `HVHV`) | **PASS** |
| **Orbit Pass & Look** | `orbitPassDirection` / `lookDirection` | `Ascending` / `Left` | `Ascending` / `Left` | **PASS** |
| **Track & Frame** | `trackNumber` / `frameNumber` | Track `10`, Frame `176` | Track `10`, Frame `176` | **PASS** |
| **Projection (CRS)** | `projection` | `EPSG:32748` (WGS 84 / UTM zone 48S) | `EPSG:32748` (WGS 84 / UTM zone 48S) | **PASS** |
| **Grid Dimensions** | `HHHH.shape` (`height × width`) | `32,616 × 33,480` (`1,091,983,680` px) | `32,616 × 33,480` (`1,091,983,680` px) | **PASS** |
| **Pixel Spacing** | `xCoordinateSpacing`, `yCoordinateSpacing` | `(10.0 m, -10.0 m)` | `(10.0 m, -10.0 m)` | **PASS** |
| **Coordinate Vectors** | `xCoordinates[0..-1]`, `yCoordinates[0..-1]` | `X: [388085.0 .. 722875.0]`, `Y: [9822235.0 .. 9496085.0]` | Exact 0.000 m offset (`verify_grids_compatible` = True) | **PASS** |
| **HDF5 Chunking** | `HHHH.chunks`, `HVHV.chunks`, `mask.chunks` | `[512, 512]`, `gzip` (`float32` / `uint8`) | `[512, 512]`, `gzip` (`float32` / `uint8`) | **PASS** |
| **RFI QA Metadata** | `/science/LSAR/GCOV/metadata/processingInformation/parameters/rfiMitigationApplied` | `False` (`rfiLikelihood` violates `[0,1]` per `isce3#294`) | `False` (`rfiLikelihood` violates `[0,1]` per `isce3#294`) | **`UNRELIABLE_METADATA` (QA context only)** |
| **Overall Decision** | `sar.validation` + `sar.change.windows` | — | — | **`COMPARABLE` (`PASS`)** |

---

## 3. Step 1.7 & Phase 3C — Flagship AOI Change Engine Validation (`Ogan Komering Ilir`)

Four preset AOIs within the Ogan Komering Ilir (OKI) peatland fire-response corridor (documented in [`docs/science/FLAGSHIP_EVENT_CONTEXT.md`](file:///D:/NASA/SAR2Action/docs/science/FLAGSHIP_EVENT_CONTEXT.md)) were analyzed using `sar/change/` (`algorithm_version = sar2action-phase2a-change-v1.0.0`):

1. **`AOI-OKI-01` (`E-FLAGSHIP-OKI-001`) — Tulung Selapan / Cengal Peatland Transition:**
   - **Selection Provenance:** `selection_method = PREDEFINED_GEOGRAPHIC_AOI`, `selection_time = PRE_ANALYSIS`
   - **Bounding Box (WGS84):** `[105.28°E, -3.28°S, 105.48°E, -3.08°S]`
   - **Grid Window (`EPSG:32748`):** `2,213 rows × 2,224 cols` (`4,921,712` pixels = `492.1712 km²` / `49,217.12 ha`)
   - **RAM Footprint:** `122.04 MiB` windowed vs `26.44 GiB` full-frame equivalent (**99.55% memory reduction**)
   - **Compute Runtime:** `6.170 s`
2. **`AOI-OKI-02` (`E-FLAGSHIP-OKI-002`) — Pangkalan Lampam / Pedamaran Peatland Belt:**
   - **Selection Provenance:** `selection_method = PREDEFINED_GEOGRAPHIC_AOI`, `selection_time = PRE_ANALYSIS`
   - **Bounding Box (WGS84):** `[104.98°E, -3.32°S, 105.16°E, -3.14°S]`
   - **Grid Window (`EPSG:32748`):** `1,991 rows × 2,001 cols` (`3,983,991` pixels = `398.3991 km²` / `39,839.91 ha`)
   - **RAM Footprint:** `98.79 MiB` windowed vs `26.44 GiB` full-frame equivalent (**99.63% memory reduction**)
   - **Compute Runtime:** `4.069 s`
3. **`AOI-OKI-03` (`E-FLAGSHIP-OKI-003`) — Eastern Cengal Coastal Peat Corridor:**
   - **Selection Provenance:** `selection_method = PREDEFINED_GEOGRAPHIC_AOI`, `selection_time = PRE_ANALYSIS`
   - **Bounding Box (WGS84):** `[105.55°E, -3.42°S, 105.73°E, -3.24°S]`
   - **Grid Window (`EPSG:32748`):** `1,992 rows × 2,002 cols` (`3,987,984` pixels = `398.7984 km²` / `39,879.84 ha`)
   - **RAM Footprint:** `98.88 MiB` windowed vs `26.44 GiB` full-frame equivalent (**99.63% memory reduction**)
   - **Compute Runtime:** `4.365 s`
4. **`AOI-OKI-04` (`E-FLAGSHIP-OKI-004`) — Padang Sugihan Peatland Reserve & Buffer Corridor (Predefined External-Context AOI):**
   - **Selection Provenance:** `selection_method = PREDEFINED_EXTERNAL_CONTEXT`, `selection_time = PRE_ANALYSIS`
   - **Selection Basis:** Predefined from external ANTARA/Polda Sumsel/BPBD and BMKG event reports on *Suaka Margasatwa Padang Sugihan* ([`docs/science/FLAGSHIP_EVENT_CONTEXT.md`](file:///D:/NASA/SAR2Action/docs/science/FLAGSHIP_EVENT_CONTEXT.md) Section 4.1) **before** inspecting radar-change statistics in this window.
   - **Bounding Box (WGS84):** `[105.08°E, -2.92°S, 105.24°E, -2.76°S]`
   - **Grid Window (`EPSG:32748`):** `1,770 rows × 1,779 cols` (`3,148,830` pixels = `314.8830 km²` / `31,488.30 ha`)
   - **RAM Footprint:** `78.08 MiB` windowed vs `26.44 GiB` full-frame equivalent (**99.71% memory reduction**)
   - **Compute Runtime:** `3.421 s`

### 3.1 Multi-Temporal Mask & Coverage Diagnostics

All four OKI peatland AOIs lie well within the interior of the full-frame `T010_F176` swath (`32,616 × 33,480`), yielding **100.00% valid common pixel coverage** under the strict official validity rule `(mask > 0) & (mask < 255) & np.isfinite(power) & (power > 0)`:

| AOI ID | Evidence ID | Selection Method | Total AOI Pixels | `T0` `mask == 0/255` | `T1` `mask == 0/255` | Common Valid Pixels (`HH ∩ HV`) | Valid Area (`km²` / `ha`) | Valid Coverage % | Quality Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`AOI-OKI-01`** | `E-FLAGSHIP-OKI-001` | `PREDEFINED_GEOGRAPHIC_AOI` | `4,921,712` | `0 / 0` | `0 / 0` | **`4,921,712`** | `492.17 km²` / `49,217.1 ha` | **`100.00%`** | **`COMPARABLE`** |
| **`AOI-OKI-02`** | `E-FLAGSHIP-OKI-002` | `PREDEFINED_GEOGRAPHIC_AOI` | `3,983,991` | `0 / 0` | `0 / 0` | **`3,983,991`** | `398.40 km²` / `39,839.9 ha` | **`100.00%`** | **`COMPARABLE`** |
| **`AOI-OKI-03`** | `E-FLAGSHIP-OKI-003` | `PREDEFINED_GEOGRAPHIC_AOI` | `3,987,984` | `0 / 0` | `0 / 0` | **`3,987,984`** | `398.80 km²` / `39,879.8 ha` | **`100.00%`** | **`COMPARABLE`** |
| **`AOI-OKI-04`** | `E-FLAGSHIP-OKI-004` | `PREDEFINED_EXTERNAL_CONTEXT` | `3,148,830` | `0 / 0` | `0 / 0` | **`3,148,830`** | `314.88 km²` / `31,488.3 ha` | **`100.00%`** | **`COMPARABLE`** |

### 3.2 Quantitative Backscatter & Change Distribution Summary (`2026-09-06 → 2026-09-18`)

| AOI ID (`Evidence ID`) | Pol | `T0` Median / Mean (dB) | `T1` Median / Mean (dB) | Signed $\Delta$ Median / Mean (dB) | Signed $\Delta$ `[p10, p90]` (dB) | $|\Delta|$ Median / Mean / `p90` (dB) | Pos / Neg Change Fraction | Combined Radar Change $|\Delta_{\text{HH}}| + |\Delta_{\text{HV}}|$ Median / Mean / `p90` (`dB composite`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`AOI-OKI-01`** (`E-FLAGSHIP-OKI-001`) | **HH** | `-7.1350` / `-7.1723` | `-7.2917` / `-7.3266` | **`-0.1640`** / `-0.1543` | `[-3.3027, +3.0066]` | `1.6336` / `1.9742` / `4.1145` | `47.26%` / `52.74%` | **Median: `3.7096 dB composite`**<br>Mean: `4.0372 dB composite`<br>`p90`: `7.0765 dB composite` |
| **`AOI-OKI-01`** (`E-FLAGSHIP-OKI-001`) | **HV** | `-12.8864` / `-13.0720` | `-13.0245` / `-13.2054` | **`-0.1343`** / `-0.1334` | `[-3.4363, +3.1684]` | `1.7212` / `2.0630` / `4.2806` | `47.89%` / `52.11%` | *(Same dual-pol layer)* |
| **`AOI-OKI-02`** (`E-FLAGSHIP-OKI-002`) | **HH** | `-8.1798` / `-8.6021` | `-8.3643` / `-8.7847` | **`-0.2082`** / `-0.1826` | `[-3.1820, +2.8314]` | `1.5534` / `1.8920` / `3.9508` | `46.34%` / `53.66%` | **Median: `3.5846 dB composite`**<br>Mean: `3.9150 dB composite`<br>`p90`: `6.8770 dB composite` |
| **`AOI-OKI-02`** (`E-FLAGSHIP-OKI-002`) | **HV** | `-14.8494` / `-15.0978` | `-15.0269` / `-15.2685` | **`-0.1703`** / `-0.1707` | `[-3.4044, +3.0621]` | `1.6866` / `2.0230` / `4.1988` | `47.24%` / `52.75%` | *(Same dual-pol layer)* |
| **`AOI-OKI-03`** (`E-FLAGSHIP-OKI-003`) | **HH** | `-8.3218` / `-8.3617` | `-8.5570` / `-8.5952` | **`-0.2393`** / `-0.2335` | `[-3.4944, +3.0323]` | `1.6970` / `2.0447` / `4.2553` | `46.17%` / `53.83%` | **Median: `3.8507 dB composite`**<br>Mean: `4.1739 dB composite`<br>`p90`: `7.2897 dB composite` |
| **`AOI-OKI-03`** (`E-FLAGSHIP-OKI-003`) | **HV** | `-14.0499` / `-14.1621` | `-14.2620` / `-14.3669` | **`-0.2042`** / `-0.2048` | `[-3.6089, +3.1976]` | `1.7845` / `2.1292` / `4.4090` | `46.90%` / `53.10%` | *(Same dual-pol layer)* |
| **`AOI-OKI-04`** (`E-FLAGSHIP-OKI-004`) | **HH** | `-8.2689` / `-8.3201` | `-8.4719` / `-8.5255` | **`-0.2128`** / `-0.2053` | `[-3.5025, +3.1037]` | `1.7207` / `2.0693` / `4.3034` | `46.64%` / `53.36%` | **Median: `3.8693 dB composite`**<br>Mean: `4.2059 dB composite`<br>`p90`: `7.3623 dB composite` |
| **`AOI-OKI-04`** (`E-FLAGSHIP-OKI-004`) | **HV** | `-14.6442` / `-14.7100` | `-14.8626` / `-14.9231` | **`-0.2056`** / `-0.2130` | `[-3.6299, +3.1979]` | `1.7834` / `2.1366` / `4.4329` | `46.88%` / `53.12%` | *(Same dual-pol layer)* |

### 3.3 Exploratory Post-Hoc `2 km × 2 km` Sub-Patches (`EXPLORATORY_POST_HOC_RADAR_CHANGE`)

> **Mandatory Methodological Provenance (`EXPLORATORY_POST_HOC`):**  
> The `2 km × 2 km` (`200 × 200` pixels = `40,000` valid 10 m pixels = `400 ha`) windows listed below were identified by scanning each AOI after computing the radar change raster (`selection_method = EXPLORATORY_POST_HOC_RADAR_CHANGE`, `selection_time = POST_HOC_INSPECTION`). They are reported strictly as **exploratory post-hoc radar change observations** illustrating localized variance within each AOI — **never as confirmatory wildfire evidence**.

- **`AOI-OKI-01` Exploratory Sub-Patch (`row_offset=0, col_offset=300`, `EXPLORATORY_POST_HOC_RADAR_CHANGE`):** `median ΔHH = +0.9339 dB` (`p10 = -2.9916 dB`, `p90 = +5.1075 dB`), `median ΔHV = +0.0088 dB` (`p10 = -4.0442 dB`, `p90 = +4.0820 dB`), `median Combined Radar Change = 4.7431 dB composite` (`p90 = 9.1153 dB composite`).
- **`AOI-OKI-02` Exploratory Sub-Patch (`row_offset=1400, col_offset=700`, `EXPLORATORY_POST_HOC_RADAR_CHANGE`):** `median ΔHV = -0.5299 dB` (`p10 = -4.0383 dB`), `median ΔHH = -0.1176 dB` (`p10 = -3.5381 dB`), `median Combined Radar Change = 4.1579 dB composite` (`p90 = 7.9160 dB composite`).
- **`AOI-OKI-03` Exploratory Sub-Patch (`row_offset=1100, col_offset=900`, `EXPLORATORY_POST_HOC_RADAR_CHANGE`):** `median ΔHV = -0.3766 dB` (`p10 = -4.1084 dB`), `median ΔHH = -0.1091 dB` (`p10 = -3.6721 dB`), `median Combined Radar Change = 4.1856 dB composite` (`p90 = 7.9873 dB composite`).
- **`AOI-OKI-04` Exploratory Sub-Patch (`row_offset=600, col_offset=700`, `EXPLORATORY_POST_HOC_RADAR_CHANGE`):** `median ΔHV = -1.0358 dB` (`p10 = -4.9454 dB`), `median ΔHH = -0.6323 dB` (`p10 = -4.4118 dB`), `median Combined Radar Change = 4.6203 dB composite` (`p90 = 8.7188 dB composite`).

---

## 4. Scientific Interpretation & Mandatory Epistemic Boundaries

### 4.1 What We Observed (`OBSERVED` / `COMPARABLE`)
- Across all four Ogan Komering Ilir peatland sub-AOIs (`1,604.25 km²` total valid area), including the externally predefined *Padang Sugihan* corridor (`AOI-OKI-04`), regional median L-band backscatter shifted slightly negative over the 12-day dry-season escalation interval (`2026-09-06 → 2026-09-18`):
  - Regional signed `median ΔHH` ranges from **`-0.1640 dB` to `-0.2393 dB`** (`-0.2128 dB` in `AOI-OKI-04`; `52.7%` to `53.8%` negative-change pixels).
  - Regional signed `median ΔHV` ranges from **`-0.1343 dB` to `-0.2056 dB`** (`-0.2056 dB` in `AOI-OKI-04`; `52.1%` to `53.1%` negative-change pixels).
  - Pixel-level change magnitude (`|ΔHH|` median `1.55–1.72 dB`, `|ΔHV|` median `1.69–1.78 dB`; Combined Radar Change median `3.58–3.87 dB composite`, `p90 = 6.88–7.36 dB composite`) reflects pixel-scale backscatter reorganization plus residual speckle variance across ~18–20 effective looks.

### 4.2 What May Explain It (`POSSIBLE INTERPRETATION`)
- **Peatland Water-Table Drawdown & Surface Drying:** A regional negative shift of `-0.16 to -0.24 dB` in `HH` and `-0.13 to -0.21 dB` in `HV` over 12 days of peak dry-season conditions in OKI is physically consistent with reductions in near-surface dielectric permittivity as drained peat soils and surface vegetation lose moisture.
- **Localized Canopy / Scrub Loss or Clearing:** Localized negative tails (`ΔHV < -3.4 dB` at `p10`, and exploratory post-hoc `2 km × 2 km` median `ΔHV = -0.53 dB` to `-1.04 dB`) are consistent with localized loss of L-band volume scatterers (scrub, secondary regrowth, or plantation vegetation) from fire scar clearing, agricultural activity, or biomass disturbance.
- **Localized Double-Bounce or Bare-Surface Exposure:** Localized positive tails (`ΔHH > +3.0 dB` at `p90`, and exploratory post-hoc `2 km × 2 km` median `ΔHH = +0.93 dB` in `AOI-OKI-01`) are consistent with increased surface roughness, canal/water-table management, or enhanced trunk-ground/stump double-bounce after understory removal.

### 4.3 What We Do Not Know (`EPISTEMIC LIMITATIONS`)
- **Cause Not Determined (`cause_not_determined`):** L-band radar backscatter change measures changes in physical scattering geometry and dielectric properties ($\gamma^0$), **not** active thermal combustion or fire occurrence.
- **Not a Burn-Severity Index (`not_burn_severity_or_fire_damage`):** `Combined Radar Change = abs(Delta_HH) + abs(Delta_HV)` (`unit = dB composite`) carries the mandatory disclaimer: *"Custom visualization metric — not a hazard score, fire probability, damage score, or official burn-severity index."*
- **Provisional Calibration (`provisional_product_maturity`) & Unreliable RFI Scalar (`rfi_likelihood_unreliable_metadata_isce3_294`):** Both granules belong to `NISAR_L2_GCOV_PROVISIONAL_V1` (`CRID = P05023`, `productVersion = 1.0.11`). Raw `rfiLikelihood` values in `_QA_STATS.h5` exceed `[0,1]` per `isce-framework/isce3#294` while `rfiMitigationApplied = False`, and are treated strictly as QA context.

---

## 5. Exported QA GeoTIFFs & Persisted Evidence Records

All 44 Flagship GeoTIFFs are stored in [`D:\NASA\SAR2Action\data\processed\phase2c_flagship\`](file:///D:/NASA/SAR2Action/data/processed/phase2c_flagship/) (`EPSG:32748`, `float32` with `nodata=NaN` for dB layers; `uint8` with `nodata=255` for validity masks):

- `AOI-OKI-01_{t0_hh_db,t1_hh_db,delta_hh_db,magnitude_hh_db,t0_hv_db,t1_hv_db,delta_hv_db,magnitude_hv_db,combined_radar_change_db,common_valid_mask,missing_invalid_mask}.tif` $\rightarrow$ `E-FLAGSHIP-OKI-001` (`PREDEFINED_GEOGRAPHIC_AOI`)
- `AOI-OKI-02_{t0_hh_db,t1_hh_db,delta_hh_db,magnitude_hh_db,t0_hv_db,t1_hv_db,delta_hv_db,magnitude_hv_db,combined_radar_change_db,common_valid_mask,missing_invalid_mask}.tif` $\rightarrow$ `E-FLAGSHIP-OKI-002` (`PREDEFINED_GEOGRAPHIC_AOI`)
- `AOI-OKI-03_{t0_hh_db,t1_hh_db,delta_hh_db,magnitude_hh_db,t0_hv_db,t1_hv_db,delta_hv_db,magnitude_hv_db,combined_radar_change_db,common_valid_mask,missing_invalid_mask}.tif` $\rightarrow$ `E-FLAGSHIP-OKI-003` (`PREDEFINED_GEOGRAPHIC_AOI`)
- `AOI-OKI-04_{t0_hh_db,t1_hh_db,delta_hh_db,magnitude_hh_db,t0_hv_db,t1_hv_db,delta_hv_db,magnitude_hv_db,combined_radar_change_db,common_valid_mask,missing_invalid_mask}.tif` $\rightarrow$ `E-FLAGSHIP-OKI-004` (`PREDEFINED_EXTERNAL_CONTEXT`)
