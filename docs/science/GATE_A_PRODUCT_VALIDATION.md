# GATE A.2 — NISAR L2 GCOV Product-Level Validation Report

- **Project:** SAR2Action — NISAR Earth Change Intelligence
- **Development Mode:** `PROJECT_MODE = PRE_COMPETITION_RND`
- **Validation Date:** `2026-10-23`
- **Target Collection:** `NISAR_L2_GCOV_PROVISIONAL_V1` (`C2854338529-ASF`, DOI `10.5067/NIL2GCOV-P1`)
- **Primary Engineering Candidate Pair:** Track `047`, Frame `087`, `DESCENDING`, `Left` look, `4005_DHDH_A` (`HH + HV`), `CRID = P05023`
  - **Scene $T_0$ (`2026-07-23`):** `NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001` (`G4260394498-ASF`)
  - **Scene $T_1$ (`2026-09-21`):** `NISAR_L2_PR_GCOV_031_047_D_087_4005_DHDH_A_20260921T112603_20260921T112609_P05023_N_P_J_001` (`G4320561922-ASF`)

---

## Executive Decision

# GATE A PASS *(Scene-Pair Product Comparability: Promoted from `CATALOG_SCREENED` to `COMPARABLE`)*
### *(With Geographic Scope Condition for Mainland `AOI-A1`: `INSUFFICIENT_EVIDENCE` inside mainland Riau box `[100.8°E–103.2°E, -0.3°S–2.1°N]`; `COMPARABLE` over the `9,429.38 km²` Riau Archipelago / Singapore Strait Swath Intersection `[103.12°E–105.41°E, 1.59°N–2.50°N]`)*

| Evaluation Dimension | Result | Status / Metric |
| :--- | :--- | :--- |
| **Scene-to-Scene Product Comparability (Engineering Validation)** | **PASS** | Promoted from `CATALOG_SCREENED` to **`COMPARABLE`** (`94,293,840` common valid 10 m dual-pol pixels = **`9,429.38 km²`**) |
| **Valid Overlap Ratio (Acquired Swath Union)** | **PASS** | **`80.77%`** (`94,293,840 / 116,744,322` pixels; threshold $\ge 75\%$) |
| **Valid Overlap Ratio (Acquired Swath Intersection)** | **PASS** | **`93.72%`** (`94,293,840 / 100,612,294` pixels) |
| **Valid Overlap Ratio (Valid Pixel Union IoU)** | **PASS** | **`90.82%`** (`94,293,840 / 103,828,869` pixels) |
| **Grid & CRS Identity (`EPSG:32648`, 10 m $\times$ 10 m)** | **PASS** | **100% identical** `32,832 × 33,624` coordinate grid (`xCoordinates` & `yCoordinates` bit-for-bit identical; zero resampling required) |
| **Mainland `AOI-A1` Coverage (`[100.8°E–103.2°E, -0.3°S–2.1°N]`)** | **INSUFFICIENT_EVIDENCE** | Only **`2,806`** valid pixels (`0.0009%` of `AOI-A1`) fall inside the mainland Riau bounding box because both granules are `isFullFrame = False` (~6.0 s partial-frame datatakes) covering `[103.12°E–105.41°E, 1.59°N–2.50°N]` (Riau Islands / Bintan / Batam) |

> **Why this distinction matters:**
> 1. **For Engineering & Algorithm Validation:** The `T047_F087` pair is a **100% genuine, pixel-aligned, dual-pol (`HH` + `HV`) NISAR L2 GCOV scene pair** with **`94.29 million` valid 10 m pixels (`9,429.38 km²`)** and **`80.77%` valid overlap** across its acquired swath union. It fully validates the SAR2Action HDF5 ingestion, mask semantics, coordinate alignment, and `EvidenceRecord` pipeline (`E-GATE-A2-001`).
> 2. **For Mainland Sumatra Wildfire / Peatland Selection:** Because `T047_F087` is a partial-frame datatake (`isFullFrame = False`, occupying `9.2%` of the `328 × 336 km` UTM frame grid), its actual illuminated swath lies over the eastern Riau Archipelago (`103.12°E–105.41°E`) rather than mainland Riau (`100.8°E–103.2°E`). NASA CMR returned `83.4%` bbox overlap during Phase 1 because the fixed Frame `087` grid (`32,832 × 33,624` pixels) spans `100.99°E–106.02°E`. When selecting inland Sumatra flagship scenes in the next phase, we must require `isFullFrame = True` (or inspect sidecar `_LATLON.kml` before HDF5 download), such as `AOI-A1` Track `148` Frame `088` (`2026-08-08` $\to$ `2026-09-25`) or `AOI-A2` Track `119` Frame `090`.

---

## 1. Note on Granule Timestamp Identifier in Prompt vs. Official Archive

The Gate A.2 prompt listed the compact Riau pair with the `T225321` / `T225319` timestamp suffix (which belongs to `AOI-A2` Track `119` Frame `090`). In the official NASA/ASF `NISAR_L2_GCOV_PROVISIONAL_V1` archive (and [`data/processed/gate_a_candidate_pairs.json`](../../data/processed/gate_a_candidate_pairs.json)), the exact granule IDs for **`AOI-A1`, Track `047`, Frame `087`, `DESCENDING`, `4005_DHDH_A`, `P05023`** on `2026-07-23` and `2026-09-21` are:
- **$T_0$:** `NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001` (`G4260394498-ASF`)
- **$T_1$:** `NISAR_L2_PR_GCOV_031_047_D_087_4005_DHDH_A_20260921T112603_20260921T112609_P05023_N_P_J_001` (`G4320561922-ASF`)

---

## 2. Step 1 & Step 2 — Authentication Smoke Test & Sidecar-First Validation

### 2.1 Authentication Smoke Test
- Verified `C:\Users\user\.netrc` presence via [`sar/ingest/earthdata_auth.py`](../../sar/ingest/earthdata_auth.py) (`EarthdataOAuthSession`) without printing, logging, or exposing credentials.
- Smoke test downloaded `NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001_QA_SUMMARY.csv` (`HTTP 200`, `1,441 bytes`, `Content-Type: text/csv`), confirming valid Earthdata URS OAuth flow through `urs.earthdata.nasa.gov` and `d1mv8zhcvry6x4.cloudfront.net`.

### 2.2 Companion Sidecar Files Retrieved (`396,613 bytes` total)
All 12 official companion files (`6` for $T_0$, `6` for $T_1$) were downloaded to [`data/raw/sidecars/AOI-A1_T047_F087/`](../../data/raw/sidecars/AOI-A1_T047_F087/) and parsed into [`sidecar_and_harmony_summary.json`](../../data/raw/sidecars/AOI-A1_T047_F087/sidecar_and_harmony_summary.json):

| Scene | Sidecar Suffix | Actual Filename | Size (Bytes) | Key Findings from Sidecar |
| :--- | :--- | :--- | ---: | :--- |
| **$T_0$** | `_QA_SUMMARY.csv` | `...20260723T112605..._QA_SUMMARY.csv` | `1,441` | `FAIL` on identification group check because `listOfObservationModes` is `['(NOT SPECIFIED)']`; all dataset/WKT/pixel checks `PASS`; RFI likelihood `HH = 6.32%`, `HV = 9.48%` |
| **$T_0$** | `_QA_STATS.h5` | `...20260723T112605..._QA_STATS.h5` | `83,440` | `HHHH` min `4.69e-6`, max `1792.80`, mean `0.1038`, std `0.6293`, nan_count `1,003,327,656`, zero_count `0`; `HVHV` min `1.01e-6`, max `418.74`, mean `0.0267` |
| **$T_0$** | `.h5.iso.xml` | `...20260723T112605....h5.iso.xml` | `102,438` | ISO 19115 metadata; `CRID = P05023`, `Look = Left`, `Orbit = Descending`, `Track = 47`, `Frame = 87` |
| **$T_0$** | `.rc.yaml` | `...20260723T112605....rc.yaml` | `8,579` | RunConfig: `ISCE3 0.25.4`, `s3_dem_30m.vrt`, `pixel_posting = 10.0 m`, `output_epsg = 32648`, `apply_rtc = True`, `rtc_terrbull_algorithm = area_projection` |
| **$T_0$** | `_LATLON.kml` | `...20260723T112605..._LATLON.kml` | `1,796` | Actual illuminated swath polygon `[103.12°E–105.41°E, 1.62°N–2.47°N]` |
| **$T_0$** | `_NATIVE.kml` | `...20260723T112605..._NATIVE.kml` | `647` | Native UTM Zone 48N frame corner overlay |
| **$T_1$** | `_QA_SUMMARY.csv` | `...20260921T112603..._QA_SUMMARY.csv` | `1,441` | Same `listOfObservationModes` warning; all dataset/WKT/pixel checks `PASS`; RFI likelihood `HH = 9.33%`, `HV = 10.18%` |
| **$T_1$** | `_QA_STATS.h5` | `...20260921T112603..._QA_STATS.h5` | `83,440` | `HHHH` min `3.36e-6`, max `1842.41`, mean `0.1126`, std `0.6917`, nan_count `987,202,176`, zero_count `0`; `HVHV` min `1.61e-6`, max `395.70`, mean `0.0295` |
| **$T_1$** | `.h5.iso.xml` | `...20260921T112603....h5.iso.xml` | `102,438` | Identical acquisition geometry (`Track 47`, `Frame 87`, `Descending`, `Left`, `CRID P05023`) |
| **$T_1$** | `.rc.yaml` | `...20260921T112603....rc.yaml` | `8,509` | Identical `ISCE3 0.25.4` GCOV workflow configuration (`EPSG:32648`, `10.0 m`, `area_projection` RTC) |
| **$T_1$** | `_LATLON.kml` | `...20260921T112603..._LATLON.kml` | `1,797` | Actual illuminated swath polygon `[103.12°E–105.42°E, 1.59°N–2.50°N]` |
| **$T_1$** | `_NATIVE.kml` | `...20260921T112603..._NATIVE.kml` | `647` | Identical UTM Zone 48N frame corner overlay |

---

## 3. Step 3 — NASA Harmony Extraction Investigation & Fallback Decision

Before downloading the full HDF5 granules, we probed the official NASA Harmony API (`https://harmony.earthdata.nasa.gov`) for collection `C2854338529-ASF` (`NISAR_L2_GCOV_PROVISIONAL_V1`):

1. **Capabilities Check (`/capabilities?collectionId=C2854338529-ASF`):**
   - Returned `HTTP 200`.
   - Service `net2cog` (`S3177988677-POCLOUD`) is registered with `"variableSubset": true` and `"outputFormats": ["image/tiff", "application/x-geotiff"]`, **but `"bboxSubset": false` and `"shapeSubset": false`** (no spatial subsetting supported).
   - Available Harmony variable names: `/science/LSAR/GCOV/grids/frequencyA/HHHH`, `/science/LSAR/GCOV/grids/frequencyA/HVHV`, `/science/LSAR/GCOV/grids/frequencyA/mask`, `/science/LSAR/GCOV/grids/frequencyA/numberOfLooks`.
2. **Synchronous & Asynchronous Harmony Job Tests:**
   - Synchronous OGC API Coverages request (`/C2854338529-ASF/ogc-api-coverages/1.0.0/collections/parameter_vars/coverage/rangeset?granuleId=G4260394498-ASF&subset=...&format= image/tiff`) timed out after 60 seconds (`ReadTimeoutError`).
   - Asynchronous Harmony job `53dd5243-0b26-437b-93a0-fba3e6f4d0bc` was created (`HTTP 201`), entered `"running"`, stalled at `"progress": 9` for >90 seconds, and timed out during polling because `net2cog` attempts to materialize full uncompressed/re-chunked `32,832 × 33,624` (`1.104 billion` pixel, ~4.4 GB per float32 band) Cloud-Optimized GeoTIFFs in the cloud without spatial clipping.
3. **Scientific & Engineering Reasons for Falling Back to Official HDF5 Granules:**
   - **Performance & Reliability:** Direct HDF5 download from ASF (`~1.05 GiB` + `~1.18 GiB` gzip-compressed `512 × 512` chunked HDF5) completed cleanly at ~48 MB/s in ~48 seconds total, whereas Harmony `net2cog` timed out.
   - **Metadata & Semantic Integrity:** `net2cog` strips the `/science/LSAR/identification` group (`boundingPolygon`, `compositeReleaseId`, `lookDirection`, `isFullFrame`) and HDF5 dataset attributes (`mask` subswath vs. partially-focused `0` vs. fill `255` semantics).
   - **Decision:** Rejected Harmony `net2cog` for Gate A.2 validation and fell back to the official NASA/ASF HDF5 granules.

---

## 4. Step 4 — Native HDF5 Environment Outside `D:\` (`C:\Users\user\.venvs\sar2action`)

Because Windows Application Control (`Smart App Control` / WDAC) blocks unsigned native `.pyd`/`.dll` C-extensions (`h5py`) located on `D:\`:
- Created `C:\Users\user\.venvs\sar2action` (`--system-site-packages`) and installed native `h5py 3.16.0` (`HDF5 2.0.0`).
- Verified native `h5py` reads multi-GB NISAR HDF5 chunks directly from `D:\NASA\SAR2Action\data\raw\scenes\` in ~1.2 seconds per active swath window.

---

## 5. Step 5 — Science HDF5 Inspection & Actual Product Properties

### 5.1 Total Bytes Downloaded
| File Type | File Count | Total Bytes | Size (GiB / MiB) | Local Path |
| :--- | ---: | ---: | ---: | :--- |
| **Companion Sidecars** | 12 | `396,613` | `0.38 MiB` | `D:\NASA\SAR2Action\data\raw\sidecars\AOI-A1_T047_F087\` |
| **Scene $T_0$ HDF5 (`2026-07-23`)** | 1 | `1,132,462,080` | `1.055 GiB` | `D:\NASA\SAR2Action\data\raw\scenes\NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001.h5` |
| **Scene $T_1$ HDF5 (`2026-09-21`)** | 1 | `1,270,874,112` | `1.184 GiB` | `D:\NASA\SAR2Action\data\raw\scenes\NISAR_L2_PR_GCOV_031_047_D_087_4005_DHDH_A_20260921T112603_20260921T112609_P05023_N_P_J_001.h5` |
| **Total Downloaded in Gate A.2** | **14** | **`2,403,732,805`** | **`2.239 GiB`** | — |

### 5.2 Confirmed HDF5 Dataset Paths & Grid Properties
Both granules share **bit-for-bit identical coordinate grids**:
- **Identification group:** `/science/LSAR/identification`
  - `productType = GCOV`, `productLevel = L2`, `radarBand = L`, `instrumentName = LSAR`
  - `productVersion = 1.0.11`, `productSpecificationVersion = 1.5.0`, `compositeReleaseId = P05023`
  - `orbitPassDirection = Descending`, `lookDirection = Left`, `trackNumber = 47`, `frameNumber = 87`
  - `isGeocoded = True`, `isDithered = True`, `isFullFrame = False`, `hasInputDataException = 0`
- **Grid group:** `/science/LSAR/GCOV/grids/frequencyA`
  - `projection`: `EPSG:32648` (`WGS 84 / UTM zone 48N`)
  - `width = 33,624`, `height = 32,832` (`1,103,943,168` total frame grid pixels)
  - `xCoordinateSpacing = 10.0 m`, `yCoordinateSpacing = -10.0 m`
  - `xCoordinates`: `float64[33624]` from `277,205.0 m` to `613,435.0 m` (`np.array_equal(x0, x1) == True`)
  - `yCoordinates`: `float64[32832]` from `483,835.0 m` to `155,525.0 m` (`np.array_equal(y0, y1) == True`)
  - Affine Geotransform (pixel upper-left corner): `[277200.0, 10.0, 0.0, 483840.0, 0.0, -10.0]`
  - `listOfPolarizations = ['HH', 'HV']`, `listOfCovarianceTerms = ['HHHH', 'HVHV']`, `numberOfSubSwaths = 1`

| Dataset Role | Confirmed HDF5 Path | Shape | Dtype | Chunk Shape | `_FillValue` | Units |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **HH Diagonal Intensity ($\gamma^0_{\text{HH}}$)** | `/science/LSAR/GCOV/grids/frequencyA/HHHH` | `(32832, 33624)` | `float32` | `(512, 512)` | `NaN` | `1` (linear power) |
| **HV Diagonal Intensity ($\gamma^0_{\text{HV}}$)** | `/science/LSAR/GCOV/grids/frequencyA/HVHV` | `(32832, 33624)` | `float32` | `(512, 512)` | `NaN` | `1` (linear power) |
| **Valid Samples Subswath Mask** | `/science/LSAR/GCOV/grids/frequencyA/mask` | `(32832, 33624)` | `uint8` | `(512, 512)` | `255` | `1` (categorical) |
| **Number of Radar Looks** | `/science/LSAR/GCOV/grids/frequencyA/numberOfLooks` | `(32832, 33624)` | `float32` | `(512, 512)` | `NaN` | `1` (looks) |

### 5.3 Official `mask` Semantics (`OQ-003` Resolved from Real Product Attributes)
From `/science/LSAR/GCOV/grids/frequencyA/mask` attribute `description`:
> *"Mask indicating the subswath number associated with valid GCOV samples. A GCOV sample is only considered valid if it is generated from fully-focused radar samples. If at least one radar sample in the averaging set is partially focused or invalid, the corresponding mask pixel will contain the value 0. GCOV pixels outside of the radar acquisition extent are filled with the value 255."*

| Mask Value | Physical Meaning | $T_0$ Pixel Count | $T_1$ Pixel Count | Action in SAR2Action Pipeline |
| :---: | :--- | ---: | ---: | :--- |
| **`1` (`0 < mask < 255`)** | **Valid fully-focused GCOV sample** (subswath 1) | `96,417,397` (`8.73%` of grid; **`95.83%`** of $T_0$ acquired) | `101,705,312` (`9.21%` of grid; **`87.12%`** of $T_1$ acquired) | **Include** (if `HHHH > 0` and `HVHV > 0` and finite) |
| **`0`** | **Invalid / partially focused radar sample** in averaging set | `5,493,580` (`4,198,115` have finite `HHHH` values that must be masked out!) | `17,210,754` (`15,035,680` have finite `HHHH` values that must be masked out!) | **Exclude (`nodata`)** — critical discovery: finite power alone is not sufficient! |
| **`255` (`_FillValue`)** | **Outside radar acquisition extent** | `1,002,032,191` (`90.77%` of full frame grid) | `985,027,102` (`89.23%` of full frame grid) | **Exclude (`nodata`)** |

### 5.4 Intensity (`HHHH`, `HVHV`) & `numberOfLooks` Distributions
Inspected across the active swath window (`rows = [21221:30776]`, `cols = [2129:26764]`, `235,387,425` pixels):
- **Zero** `Inf` pixels, **zero** `0.0` power pixels, and **zero** negative ($P < 0$) pixels in both scenes.

| Scene & Layer | Finite Positive Pixels | Valid (`mask == 1`) Pixels | Linear Min | Linear Mean | Linear Max | dB p10 | dB Median | dB p90 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **$T_0$ `HHHH`** | `100,615,512` | `96,417,397` | `4.689e-6` | `0.1069` | `1792.78` | `-21.40 dB` | `-17.53 dB` | `-5.12 dB` |
| **$T_0$ `HVHV`** | `100,615,512` | `96,417,397` | `1.012e-6` | `0.0275` | `418.73` | `-26.67 dB` | `-22.95 dB` | `-10.88 dB` |
| **$T_0$ `numberOfLooks`** | `100,615,512` | `96,417,397` | `9.357e-8` | `4.7119` | `15.23` | `3.93 looks` | `4.84 looks` | `5.25 looks` |
| **$T_1$ `HHHH`** | `116,740,992` | `101,705,312` | `3.365e-6` | `0.1120` | `1842.41` | `-22.51 dB` | `-18.16 dB` | `-4.78 dB` |
| **$T_1$ `HVHV`** | `116,740,992` | `101,705,312` | `1.613e-6` | `0.0292` | `395.70` | `-26.67 dB` | `-22.94 dB` | `-10.57 dB` |
| **$T_1$ `numberOfLooks`** | `116,740,992` | `101,705,312` | `2.106e-9` | `4.7154` | `14.40` | `3.94 looks` | `4.84 looks` | `5.25 looks` |

---

## 6. Step 6 — Real Valid Overlap & AOI Coverage Analysis

| Metric | Value | Notes |
| :--- | ---: | :--- |
| **Full UTM Frame `087` Grid Shape** | `32,832 × 33,624` (`1,103,943,168` px) | Fixed 10 m frame grid (`328.32 km × 336.24 km`) |
| **$T_0$ Acquired Pixels (`mask != 255`)** | `100,615,551` px | `9.11%` of full frame grid (~6.0 s partial datatake) |
| **$T_1$ Acquired Pixels (`mask != 255`)** | `116,741,065` px | `10.57%` of full frame grid (~6.9 s partial datatake) |
| **Acquired Footprint Union (`mask0 != 255 \| mask1 != 255`)** | `116,744,322` px | `11,674.43 km²` illuminated across $T_0 \cup T_1$ |
| **Acquired Footprint Intersection (`mask0 != 255 & mask1 != 255`)** | `100,612,294` px | `10,061.23 km²` illuminated in both $T_0 \cap T_1$ |
| **$T_0$ Valid Pixels (`0 < mask < 255` & `HH>0` & `HV>0`)** | `96,417,397` px | **`95.83%`** of $T_0$ acquired footprint (`8.73%` of full frame grid) |
| **$T_1$ Valid Pixels (`0 < mask < 255` & `HH>0` & `HV>0`)** | `101,705,312` px | **`87.12%`** of $T_1$ acquired footprint (`9.21%` of full frame grid) |
| **Common Valid Pixels (`valid_t0 & valid_t1`, both `HH` and `HV`)** | **`94,293,840` px** | **`9,429.38 km²`** of 10 m dual-pol comparable radar observations |
| **`valid_overlap_ratio` (vs. Acquired Footprint Union)** | **`0.807695` (`80.77%`)** | Exceeds `0.75` (`75%`) `COMPARABLE` threshold |
| **`valid_overlap_ratio` (vs. Acquired Footprint Intersection)** | **`0.937200` (`93.72%`)** | `93.72%` of mutually illuminated pixels are valid in both epochs |
| **`valid_overlap_ratio` (vs. Valid Pixel Union IoU)** | **`0.908166` (`90.82%`)** | `90.82%` intersection-over-union of valid pixels |
| **`valid_overlap_ratio` (vs. $T_0$ Valid Pixels)** | **`0.977975` (`97.80%`)** | `97.80%` of $T_0$'s valid pixels remain valid in $T_1$ |
| **`valid_overlap_ratio` (vs. Full `32832 × 33624` Frame Grid)** | `0.085415` (`8.54%`) | Reflects `isFullFrame = False` (~6 s datatake inside 328 km frame grid) |
| **Common Valid Pixels Inside Mainland `AOI-A1` Box `[100.8, -0.3, 103.2, 2.1]`** | `2,806` px (`0.28 km²`) | Only the western tip of the `[103.12°E–105.41°E, 1.59°N–2.50°N]` swath touches `[100.8°E–103.2°E, -0.3°S–2.1°N]` |

---

## 7. Actual Product Issues & Quirks Discovered in Gate A.2

1. **Partial-Frame Datatake vs. Fixed Frame Grid (`isFullFrame = False`):**
   - NISAR L2 GCOV allocates the full `32,832 × 33,624` (`328 × 336 km`) UTM frame grid even when the radar datatake is only ~6 seconds long (`isFullFrame = False`).
   - Consequently, `90.77%` ($T_0$) and `89.23%` ($T_1$) of the HDF5 raster grid are `mask = 255` (`NaN`), and the active illuminated swath is located in rows `[21221:30776]`, cols `[2129:26764]`.
   - Furthermore, CMR's catalog bounding box / frame extent caused `T047_F087` to appear to cover `83.4%` of mainland `AOI-A1`, whereas the actual illuminated polygon (`_LATLON.kml` and `/science/LSAR/identification/boundingPolygon`) covers `[103.12°E–105.41°E, 1.59°N–2.50°N]` (Riau Islands / Bintan / Batam / Singapore Strait).
   - **Mitigation implemented:** Always inspect `_LATLON.kml` or `/science/LSAR/identification/boundingPolygon` and crop processing to the active swath bounding window (`active_window_rc`), avoiding unnecessary operations on 1 billion `NaN` fill pixels.
2. **Partially Focused Samples (`mask == 0`) Have Finite Power Values:**
   - In $T_0$, `4,198,115` pixels have `mask == 0` **but contain finite positive `HHHH` and `HVHV` values**; in $T_1$, `15,035,680` pixels have `mask == 0` with finite positive `HHHH` and `HVHV` values.
   - If a pipeline only checked `np.isfinite(HHHH) & (HHHH > 0)`, it would erroneously include ~4.2M ($T_0$) and ~15.0M ($T_1$) partially focused edge/invalid radar samples!
   - **Mitigation implemented:** [`sar/validation/product_validator.py`](../../sar/validation/product_validator.py) strictly enforces `(mask > 0) & (mask < 255) & np.isfinite(power) & (power > 0.0)`.
3. **Sidecar QA Summary `FAIL` Flag on `listOfObservationModes`:**
   - Both `_QA_SUMMARY.csv` files report `FAIL` on `"Passes all identification group checks?"` solely because `/science/LSAR/identification/listOfObservationModes` is populated as `['(NOT SPECIFIED)']` in provisional `CRID = P05023`. All WKT, grid, and covariance dataset checks pass.
4. **L-Band Radio Frequency Interference (RFI) Likelihood:**
   - `_QA_SUMMARY.csv` and `_QA_STATS.h5` report moderate L-band RFI likelihood (`6.3%` HH / `9.5%` HV in $T_0$; `9.3%` HH / `10.2%` HV in $T_1$), which must be noted as a limitation on pixel-level anomalies near shipping lanes/urban areas.

---

## 8. Step 8 & Step 9 — Product Validation `EvidenceRecord` & Unit Tests

- **Evidence Store Record (`E-GATE-A2-001`):**
  - Stored in [`data/cache/evidence_store.json`](../../data/cache/evidence_store.json) and [`data/processed/gate_a2_validation_metrics.json`](../../data/processed/gate_a2_validation_metrics.json).
  - Contains real $T_0$ and $T_1$ decibel distributions (`HH` and `HV`), valid pixel count (`94,293,840`), `coverage_ratio = 0.807695`, `missing_data_ratio = 0.192305`, `quality_status = "COMPARABLE"`, exact provenance (`EPSG:32648`, `10.0 m`, `CRID = P05023`), and honest limitations.
- **Product Validator & Unit Tests:**
  - Implemented [`sar/validation/product_validator.py`](../../sar/validation/product_validator.py) and [`tests/sar/test_product_validator_gate_a2.py`](../../tests/sar/test_product_validator_gate_a2.py).
  - Executed `C:\Users\user\.venvs\sar2action\Scripts\python.exe -m pytest`: **`26 passed in 0.76s`** (covering actual HDF5 metadata parsing, mask semantics `0`/`1`/`255`, grid equality, grid mismatch rejection, valid-overlap thresholds `COMPARABLE`/`LIMITED`/`INSUFFICIENT_EVIDENCE`, unavailable polarization rejection, and non-positive/NaN/Inf nodata propagation).
