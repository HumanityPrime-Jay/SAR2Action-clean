# Gate A Result

> **Date:** 2026-10-23  
> **Project Mode:** `PROJECT_MODE = PRE_COMPETITION_RND`  
> **Official Target Collection:** `NISAR_L2_GCOV_PROVISIONAL_V1` (NASA Earthdata CMR / ASF DAAC)  
> **Catalog Discovery Output:** [`data/scenes/scene_manifest.csv`](../../data/scenes/scene_manifest.csv) and [`data/scenes/scene_manifest.json`](../../data/scenes/scene_manifest.json) (630 real NISAR L-band Level-2 GCOV granules indexed; 0 synthetic/fabricated records)  
> **Overall Gate A Status:** **`CONDITIONAL` (`CATALOG_SCREENED` — Ready for Authenticated HDF5 Grid/Mask Inspection)**

---

## Candidate A — Indonesia (Sumatra Peatland & Forest Corridors)

### Status
**`CONDITIONAL` (`CATALOG_SCREENED` — High-Quality Repeat-Pass Stacks Confirmed in Catalog)**

### Evidence
- **Scenes Found in `NISAR_L2_GCOV_PROVISIONAL_V1`:** **206 real scenes** across two Sumatra AOIs:
  - **`AOI-A1` (Riau / Central Sumatra `[100.80, -0.30, 103.20, 2.10]`):** **140 scenes** across 15 repeat-pass `(track_frame, orbit, polarization)` stacks (`72 CATALOG_SCREENED` pairs, `194` total viable pairs).
  - **`AOI-A2` (South Sumatra / Ogan Komering Ilir `[104.50, -3.80, 106.20, -2.30]`):** **66 scenes** across 8 repeat-pass stacks (`72 CATALOG_SCREENED` pairs, `72` total viable pairs).
- **Acquisition Dates:**
  - `AOI-A1`: Continuous 12-day repeat-pass coverage from `2026-06-16` through `2026-10-15` (10–11 repeat-pass acquisitions per track/frame).
  - `AOI-A2`: Continuous 12-day repeat-pass coverage from `2026-06-21` through `2026-10-20` (9 repeat-pass acquisitions per track/frame, spanning peak dry/fire season in South Sumatra).
- **Product / Maturity / CRID / PGE Version:**
  - Collection: `NISAR_L2_GCOV_PROVISIONAL_V1`
  - Maturity: `PROVISIONAL`
  - CRID: `P05023` (uniform across the top repeat-pass pairs)
  - PGE Version: `R05.02.3` (`PRODUCT_VERSION = 1.0.11`, `ISCE3 0.25.16`)
- **Polarizations:**
  - Dual-polarization `HH` + `HV` (`DHDH`, `FREQUENCY_A_POLARIZATION = ['HH', 'HV']`, `40 MHz` main science band + `5 MHz` secondary band, mode `4005`).
- **Geometry:**
  - `AOI-A2` top stack `T119_F090`: `DESCENDING` pass, `LEFT` antenna look direction, exact repeat track (`119`) and frame (`090`).
  - `AOI-A1` top stacks: `T148_F088` (`DESCENDING`, `LEFT` look, full frame) and `T047_F087` (`DESCENDING`, `LEFT` look, compact partial frame averaging `1.03 GB`/granule).
- **Overlap:**
  - `AOI-A2` pair `AOI-A2_P767` (`2026-07-04` vs `2026-10-20`): **100.0% AOI overlap**, **99.6% pair footprint intersection**.
  - `AOI-A1` pair `AOI-A1_P7189` (`2026-08-23` vs `2026-09-04`): **83.4% AOI overlap**, **99.5% pair footprint intersection**.
- **Known Issues / Caveats:**
  - Catalog metadata does not expose the internal HDF5 pixel `xCoordinateSpacing`/`yCoordinateSpacing` or valid-pixel ratio after radar shadow/layover masking; therefore `validate_scene_pair` classifies catalog-only validation as `CONDITIONAL` (`science_status = "LIMITED"`) until the HDF5 `/science/LSAR/GCOV/grids/frequencyA/mask` dataset is inspected.

### Reason
Indonesia (`AOI-A2` South Sumatra and `AOI-A1` Riau) has **abundant, real, uniform-CRID (`P05023`), dual-polarization (`HH+HV`), 40 MHz (`4005`) 12-day repeat-pass NISAR L2 GCOV observations** spanning June–October 2026. It satisfies all catalog-level Gate A criteria while aligning with the flagship narrative (*When Fire Becomes Hard to See*).

---

## Candidate B — California (2026 Wildfire-Related Corridors)

### Status
**`CONDITIONAL` (`CATALOG_SCREENED` — Deepest Repeat-Pass Archive & Highest Comparability Score)**

### Evidence
- **Scenes Found in `NISAR_L2_GCOV_PROVISIONAL_V1`:** **297 real scenes** across two California AOIs:
  - **`AOI-B1` (Northern California Forest & Foothill Corridor `[-122.50, 39.60, -121.10, 40.80]`):** **159 scenes** across 9 repeat-pass stacks (`415 CATALOG_SCREENED` pairs, `2,000` viable pairs).
  - **`AOI-B2` (Southern California Transverse Ranges Corridor `[-119.10, 34.00, -117.40, 34.90]`):** **138 scenes** across 9 repeat-pass stacks (`625 CATALOG_SCREENED` pairs, `2,498` viable pairs).
- **Acquisition Dates:**
  - Continuous 12-day repeat-pass time series from **`2025-11-01` through `2026-10-21`** (up to **29 repeat-pass scenes** in a single track/frame stack `T042_F069` in `AOI-B1`, and **26 scenes** in `T034_F019` in `AOI-B2`).
- **Product / Maturity / CRID / PGE Version:**
  - Collection: `NISAR_L2_GCOV_PROVISIONAL_V1`
  - Maturity: `PROVISIONAL`
  - CRID: `P05023`
  - PGE Version: `R05.02.3` (`PRODUCT_VERSION = 1.0.11`)
- **Polarizations:**
  - Dual-polarization `HH` + `HV` (`DHDH`, `4005` mode: 40 MHz `frequencyA` + 5 MHz `frequencyB`).
- **Geometry:**
  - Exact repeat-pass stacks in both `ASCENDING` (`T034_F022`, `T135_F021`, `T034_F019`, `T106_F019`) and `DESCENDING` (`T042_F069`, `T143_F068`, `T013_F071`, `T013_F072`), `LEFT` antenna look direction.
- **Overlap:**
  - `AOI-B2` pair `AOI-B2_P105` (`T013_F071`, `2025-11-23` vs `2026-08-14`): **99.9% AOI overlap**, **99.9% pair intersection**, score **`99.98 / 100`**.
  - `AOI-B1` pair `AOI-B1_P10085` (`T143_F068`, `2026-06-24` vs `2026-07-06`): **99.9% AOI overlap**, **99.0% pair intersection**, score **`99.94 / 100`**.
- **Known Issues / Caveats:**
  - Steep topography in the Transverse Ranges (`AOI-B2`) and Northern California canyons (`AOI-B1`) can increase radar shadow/layover pixels in the GCOV `mask`, which must be quantified from the HDF5 `mask` layer before declaring `COMPARABLE`.

### Reason
California offers the deepest temporal baseline (11+ months, 25–29 repeat passes per track/frame) and near-100% spatial overlap in `NISAR_L2_GCOV_PROVISIONAL_V1`, making it an outstanding primary or backup wildfire-context case.

---

## Candidate C — Fallback (Lower Mississippi Alluvial Valley & Atchafalaya Basin)

### Status
**`CONDITIONAL` (`CATALOG_SCREENED` — High-SNR Flat-Terrain Wetland & Agricultural Surface Change)**

### Evidence
- **Scenes Found in `NISAR_L2_GCOV_PROVISIONAL_V1`:** **127 real scenes** in `AOI-C1` (`[-92.00, 29.50, -90.50, 31.50]`) across 10 repeat-pass stacks (`90 CATALOG_SCREENED` pairs, `630` viable pairs).
- **Acquisition Dates:**
  - Continuous 12-day repeat-pass coverage from `2025-11-17` through `2026-10-19` (27 scenes in `T105_F018_ASCENDING_HH;HV` and 22 scenes in `T084_F072_DESCENDING_HH;HV`).
- **Product / Maturity / CRID / PGE Version:**
  - Collection: `NISAR_L2_GCOV_PROVISIONAL_V1`, Maturity: `PROVISIONAL`, CRID: `P05023`, PGE Version: `R05.02.3`.
- **Polarizations:**
  - Dual-polarization `HH` + `HV` (`DHDH`, `4005` mode).
- **Geometry:**
  - Both `ASCENDING` (`T105_F017`, `T105_F018`) and `DESCENDING` (`T084_F072`, `T084_F073`), `LEFT` look direction.
- **Overlap:**
  - Top pair `AOI-C1_P4545` (`T105_F017`, `2026-07-03` vs `2026-08-20`): **83.2% AOI overlap**, **99.8% pair footprint intersection**, score **`93.26 / 100`**.
- **Known Issues / Caveats:**
  - Non-wildfire context (hydrological inundation / wetland vegetation / agricultural transition), but virtually zero topographic layover/shadow due to flat alluvial terrain.

### Reason
Provides a rock-solid scientific fallback with strong L-band `HH` (double-bounce inundation) and `HV` (crop/canopy volume) backscatter changes and minimal topographic masking.

---

# Pair Ranking

All candidate pairs below are ranked by `screen_candidate_pairs()` expected scientific comparability score (`[0–100]`), repeat-pass geometry consistency, polarization completeness (`HH+HV`), CRID uniformity (`P05023`), and data transfer efficiency:

| Rank | Pair ID | Candidate / AOI | Granule $T_0$ $\rightarrow$ Granule $T_1$ | $\Delta t$ | Track / Frame / Orbit | Pols | Score | Pair Overlap | Est. Pair Size |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | **`AOI-A2_P767`** | **Case A (`AOI-A2` South Sumatra)** | `NISAR_L2_PR_GCOV_024_119_D_090_4005_DHDH_A_20260704T111858_20260704T111932_P05023_N_F_J_001` $\rightarrow$ `NISAR_L2_PR_GCOV_033_119_D_090_4005_DHDH_A_20261020T111855_20261020T111930_P05023_N_F_J_001` | `108 d` (or `12 d` step `029`$\rightarrow$`030`) | `T119_F090` (`DESC`, `LEFT`) | `HH, HV` | **`100.00`** | `99.6%` (`100%` AOI) | `11.20 GB` (`8.46 GB` on `T018_F090`) |
| **2** | **`AOI-B1_P10085`** | **Case B (`AOI-B1` Northern CA)** | `NISAR_L2_PR_GCOV_023_143_D_068_4005_DHDH_A_20260624T030354_20260624T030429_P05023_N_F_J_001` $\rightarrow$ `NISAR_L2_PR_GCOV_024_143_D_068_4005_DHDH_A_20260706T030353_20260706T030428_P05023_N_F_J_001` | `12 d` (or summer span) | `T143_F068` (`DESC`, `LEFT`) | `HH, HV` | **`99.94`** | `99.0%` (`99.9%` AOI) | `13.70 GB` |
| **3** | **`AOI-B2_P105`** | **Case B (`AOI-B2` Southern CA)** | `NISAR_L2_PR_GCOV_006_013_D_071_4005_DHDH_A_20251123T024035_20251123T024113_P05023_N_F_J_001` $\rightarrow$ `NISAR_L2_PR_GCOV_028_013_D_071_4005_DHDH_A_20260814T024034_20260814T024111_P05023_N_F_J_001` | `264 d` (or `12 d` steps) | `T013_F071` (`DESC`, `LEFT`) | `HH, HV` | **`99.98`** | `99.9%` (`99.9%` AOI) | `13.57 GB` |
| **4** | **`AOI-A1_P7189`** | **Case A (`AOI-A1` Riau Sumatra)** | `NISAR_L2_PR_GCOV_028_148_D_088_4005_DHDH_A_20260823T113427_20260823T113502_P05023_N_F_J_001` $\rightarrow$ `NISAR_L2_PR_GCOV_029_148_D_088_4005_DHDH_A_20260904T113427_20260904T113502_P05023_N_F_J_001` | `12 d` | `T148_F088` (`DESC`, `LEFT`) | `HH, HV` | **`93.36`** | `99.5%` (`83.4%` AOI) | `11.51 GB` (`2.06 GB` on `T047_F087`) |
| **5** | **`AOI-C1_P4545`** | **Case C (`AOI-C1` Lower Mississippi)** | `NISAR_L2_PR_GCOV_024_105_A_017_4005_DHDH_A_20260703T111905_20260703T111940_P05023_N_F_J_001` $\rightarrow$ `NISAR_L2_PR_GCOV_028_105_A_017_4005_DHDH_A_20260820T111903_20260820T111938_P05023_N_F_J_001` | `48 d` | `T105_F017` (`ASC`, `LEFT`) | `HH, HV` | **`93.26`** | `99.8%` (`83.2%` AOI) | `12.27 GB` |

### Why These Pairs Rank Highest
1. **Identical Orbit & Frame Geometry (`STACK_ID` match):** Both scenes in each ranked pair come from the exact same relative orbit track, frame, pass direction, and antenna look direction (`LEFT`), eliminating cross-track incidence angle biases.
2. **Dual-Polarization `HH + HV` at 40 MHz Bandwidth (`4005_DHDH`):** Provides both co-polarized (`HHHH`) and cross-polarized (`HVHV`) diagonal terms at NISAR's highest standard L-band science bandwidth (`frequencyA = 40 MHz`).
3. **Uniform Processing Lineage (`CRID = P05023`, `PGEVersion = R05.02.3`):** Avoids radiometric offsets between different software builds.

---

# Recommended Primary Case

**Candidate A — Indonesia (`AOI-A2` South Sumatra / Ogan Komering Ilir Peatland Corridor, or `AOI-A1` Riau Sumatra)**
- **Why:** Prior to running Gate A, our main risk (`R-01`) was that Indonesia might lack repeat-pass NISAR L2 GCOV data in `NISAR_L2_GCOV_PROVISIONAL_V1`. Gate A disproved that concern: Sumatra has **206 real `PROVISIONAL` dual-pol (`HH+HV`) scenes** with uniform `P05023` CRID and `100.0` comparability score over `AOI-A2` (and a lightweight `1.03 GB`/granule partial-frame stack `T047_F087` over `AOI-A1` for rapid R&D iteration). This lets us unite **top-tier science comparability** with our **preferred flagship narrative** (*When Fire Becomes Hard to See*).

---

# Recommended Backup Case

**Candidate B — California (`AOI-B1` Northern California Forest & Foothill Corridor, Stack `T143_F068` or `T034_F022`)**
- **Why:** Has 27–29 repeat-pass scenes per track/frame (`score = 99.94`), 99.9% overlap, uniform `P05023` CRID, and abundant independent contextual documentation if needed.

---

# Known Scientific Limitations

1. **`CATALOG_SCREENED` $\neq$ `COMPARABLE`:** Current pair validation is `CONDITIONAL` (`science_status = "LIMITED"`) because actual HDF5 pixel coordinate grids (`xCoordinates`, `yCoordinates`, `epsg`) and validity masks (`/science/LSAR/GCOV/grids/frequencyA/mask`) have not yet been opened.
2. **Provisional Product Maturity (`NISAR_L2_GCOV_PROVISIONAL_V1`):** Calibration and radiometric terrain correction are provisional (`CRID = P05023`); residual radiometric uncertainty must be disclosed in `EvidenceRecord.limitations`.
3. **Causal Non-Equivalence (`CHANGE != CAUSE`):** Even inside Sumatra peatland corridors (`AOI-A1`/`AOI-A2`) or California wildfire corridors (`AOI-B1`/`AOI-B2`), radar backscatter change ($\Delta\text{HH}, \Delta\text{HV}$) reflects physical changes in canopy volume, surface roughness, or dielectric moisture — it does **not** by itself prove wildfire occurrence, burn severity, or underground peat smoldering.

---

# Data Download Requirement

## Authentication & Streaming Probe Result
- **Authentication Status:** **`EARTHDATA_AUTH_REQUIRED`**
  - Unauthenticated HTTP `GET`/`Range` probes to `https://nisar.asf.earthdatacloud.nasa.gov/...` redirect (`HTTP 303`) to NASA Earthdata Login (`urs.earthdata.nasa.gov`) and return `HTTP 401 Unauthorized` when no local `.netrc` or bearer token is present.
  - Once NASA Earthdata Login is configured locally (outside the repo in `C:\Users\user\_netrc` or `C:\Users\user\.netrc` or via `EARTHDATA_TOKEN`), ASF Earthdata Cloud (`cloudfront.net` / S3 presigned URLs) supports both:
    1. **Lightweight Companion QA Inspection First (< 2 MB total):** Every granule provides `_QA_SUMMARY.csv` (~1.4 KB), `_QA_STATS.h5` (~73 KB), `.h5.iso.xml` (~117 KB), and `_LATLON.png` (~3.3 MB) alongside the main `.h5` file.
    2. **HTTP Byte-Range Slicing / Full Granule Download** of the chosen 2-scene primary pair.

## Pre-Download Mandatory Report (Per Phase 1 Rule 2)

| Attribute | Primary R&D Fast-Validation Pair (`AOI-A1` Compact Frame) | Primary Full-Frame Pair (`AOI-A2` South Sumatra) | Backup Full-Frame Pair (`AOI-B1` Northern California) |
| :--- | :--- | :--- | :--- |
| **Candidate AOI** | `Case_A` / `AOI-A1` (Riau, Sumatra) | `Case_A` / `AOI-A2` (Ogan Komering Ilir, South Sumatra) | `Case_B` / `AOI-B1` (Northern California) |
| **Scene $T_0$ ID** | `NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T225321_20260723T225330_P05023_N_P_J_001` | `NISAR_L2_PR_GCOV_024_018_D_090_4005_DHDH_A_20260709T111035_20260709T111104_P05023_N_F_J_001` | `NISAR_L2_PR_GCOV_023_143_D_068_4005_DHDH_A_20260624T030354_20260624T030429_P05023_N_F_J_001` |
| **Scene $T_1$ ID** | `NISAR_L2_PR_GCOV_031_047_D_087_4005_DHDH_A_20260921T225319_20260921T225328_P05023_N_P_J_001` | `NISAR_L2_PR_GCOV_032_018_D_090_4005_DHDH_A_20261013T111031_20261013T111100_P05023_N_F_J_001` | `NISAR_L2_PR_GCOV_024_143_D_068_4005_DHDH_A_20260706T030353_20260706T030428_P05023_N_F_J_001` |
| **Acquisition Dates** | `2026-07-23` $\rightarrow$ `2026-09-21` (`60 d`) | `2026-07-09` $\rightarrow$ `2026-10-13` (`96 d`) | `2026-06-24` $\rightarrow$ `2026-07-06` (`12 d`) |
| **Expected Number of Files** | `2` HDF5 granules (plus `2` `_QA_STATS.h5` / `_QA_SUMMARY.csv` sidecars) | `2` HDF5 granules | `2` HDF5 granules |
| **Approximate File Size** | **`~2.06 GB` total** (`~1.03 GB` each) | **`~8.46 GB` total** (`~4.23 GB` each) | **`~13.70 GB` total** (`~6.85 GB` each) |
| **Available Local Disk (`D:\`)** | **`89.47 GB` free** (of `953.87 GB` total) | **`89.47 GB` free** | **`89.47 GB` free** |
| **Reason Required** | Fastest HDF5 grid/mask verification on real Sumatra dual-pol GCOV data | Full-frame Sumatra peatland change computation & hero experience | Backup case if Sumatra pair shows excessive masking or weak surface change |
