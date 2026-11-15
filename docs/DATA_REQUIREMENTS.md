# SAR2Action Data Requirements & Reproducibility Guide

This document defines the data architecture, verification provenance, and reproduction requirements for **SAR2Action**.

To ensure that the Git repository remains lightweight (<25 MB demo overhead), **large raw satellite HDF5 archives (~3 GB+) are excluded from version control via `.gitignore`**, while self-contained, reproducible analytical assets, precomputed raster layers, and verified vector polygons are versioned directly in-tree.

---

## 1. Data Tiers & Repository Boundaries

| Tier | Category | Storage Policy | Total Size | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1** | **Verified Demo Assets & Schemas** | **Committed in Git** | **~17.1 MB** | GeoJSON boundaries, precomputed difference rasters (`.tif`), high-resolution transparent overlay PNGs, tabular CSV indices, statutory relief schedules, and manifests. Enables full offline API execution, GIS computation, and all 100 backend/agent tests without raw downloads. |
| **Tier 2** | **Raw Satellite Level-1/Level-2 Data** | **Gitignored (`*.h5`, `*.hdf5`)** | **~3.07 GB** | Raw dual-pol NISAR Level-2 GCOV HDF5 granules and raw Sentinel-1/Sentinel-2 L2A scene archives. Used strictly by offline processing pipelines to generate Tier 1 assets. |

---

## 2. Tier 1: In-Tree Verified Datasets (Committed)

All Tier 1 assets are located in the repository root and are immediately accessible by `TaiwanAgroService`, `AgentOrchestrator`, and `PolygonEditor`:

### A. TW-01: Sentinel-1D RTC Agricultural Radar Change
- **Directory**: `tw01/taiwan-agricultural-demo-v1/`
- **Key Files**:
  - `manifest.json`: Dataset metadata, orbit details, beam modes, and processing parameters (`DBBB702DF3C4E4859AF783BEA519A8FFFDFF5A6F7FFC9D492EE95CF7A7C84707`)
  - `candidate-parcels.geojson`: 181 candidate agricultural parcels flagged for radar backscatter anomalies (`7516D5032D168B9BDD3427746BCC3E914EA7CF456C9E4D6FB3547E6C8253EF26`)
  - `farmland.geojson`: 4,863 baseline cadastral farmland polygons in Yunlin Taixi/Dongshi
  - `delta_vh_db.tif` / `delta_vv_db.tif`: Calibrated dual-pol RTC change rasters (VH/VV dB)
  - `delta_vh_overlay.png` / `delta_vv_overlay.png`: RGBA transparent overlays for WebGIS

### B. TW-03: NISAR L-band Level-2 GCOV Case Evidence
- **Directory**: `tw03/nisar-demo-v1/`
- **Key Files**:
  - `manifest.json`: NISAR product IDs, CRID, cycle numbers, orbit track 076 (`A6F30ADD75B6A9C224548E72934979FB731E8543DC5F81BD41A20E01BC366780`)
  - `evidence.json`: Claim-to-Evidence record linking radar backscatter distribution shifts to spatial pixels (`742031E4A1EB5D6FC28DE3ACC31E49BE2B58BB914B8A222194191D61EC296C13`)
  - `statistics.json`: Covariance distribution metrics (mean, variance, skewness, kurtosis) across HH/HV channels (`F7814923EF516B9FE386E18204C48651819FCD35B9C28AF3ADABE5121B16E425`)
  - `delta_hh_db.tif` / `delta_hv_db.tif`: GeoTIFF differential backscatter rasters
  - `delta_hh.png` / `delta_hv.png`: MapLibre GL JS georeferenced RGBA overlays

### C. TW-08A: Sentinel-2 L2A Multitemporal Optical QA
- **Directory**: `tw08/sentinel2-demo-v1/` and `tw08/sentinel2-qa-v2/`
- **Key Files**:
  - `sentinel2-demo-v1/manifest.json`: Optical acquisition dates (2026/10/11, 10/16, 10/26, 11/05) and band specifications (`1D2DFEC69A4BD41625A99297EFC7B8379D556CE42EFFE481E31C603353768563`)
  - `candidate_181_multitemporal_metrics.csv`: Real per-parcel NDVI, NDRE, and LSWI metrics across all four dates (`5CA68C41BB50D37C8E76000625FC1CEE8C948E88A115E9A0C750B540C80F6FBD`)
  - `sentinel2-qa-v2/qa_v2_manifest.json`: Scene Classification Layer (SCL) validation manifest (`4BC8A537BFF9632032FA0070D07DE7DD4597458C4A1AB32D3B9077C4FA05C112`)
  - `candidate_181_quality_and_scl_v2.csv`: SCL=4/5/6 validation, cloud/water pixel masking, and quality gate evaluations (`3D81C6FCB13A08A64150C4A27CB0EE0AD4D871F882F189FB5F9D98634325815F`)

### D. TW-07.2: Statutory Agricultural Relief Schedule Catalog
- **Directory**: `backend/data/`
- **Key Files**:
  - `tw_relief_schedules_1150629.json`: Official Ministry of Agriculture (MOA) Disaster Relief Cash Schedule II (`C5243549B4E55A3F076F093EEB259D080322F0596B2DEF65A09400B64958D2EB`)
  - `tw_yunlin_announcements_11510.json`: Yunlin County statutory relief announcements for Typhoon Gaemi / Chambi recovery (`31B3703B9D91E5D63589C83E1F7D7086BFD00233820B99DA0F52BDC8F551670A`)

---

## 3. Tier 2: Raw Satellite Products & Reproducibility Pipeline

When reproducing the Tier 1 assets from original space agency granules, the following raw products are required:

### A. Raw NISAR L-band Level-2 GCOV (HDF5)
- **Archive Location**: `tw03/inputs/` (Gitignored)
- **Product Specifications**:
  - **Pre-event Granule**: `NISAR_L2_PR_GCOV_032_061_D_076_2005_DHDH_A_20261004T103752_20261004T103826_P05023_N_F_J_001.h5`
    - **Size**: 1,535,115,264 bytes (~1.43 GiB)
    - **SHA-256**: `A35DB56BA9AF78F88F845342638E21BAB4E3E5EA693CA000F2F0E7A9E60D0DED`
    - **Acquisition Timestamp**: `2026-10-04T10:37:52Z` (Cycle 032, Track 076)
  - **Post-event Granule**: `NISAR_L2_PR_GCOV_033_061_D_076_2005_DHDH_A_20261016T103752_20261016T103826_P05023_N_F_J_001.h5`
    - **Size**: 1,535,115,264 bytes (~1.43 GiB)
    - **SHA-256**: `07B429E7E3681ACBECF63581F89863CC7274A2FC3AD26F90E9F70FEA19EB1849`
    - **Acquisition Timestamp**: `2026-10-16T10:37:52Z` (Cycle 033, Track 076)
- **Pipeline Script**:
  ```bash
  python tw03/build_demo.py
  ```

### B. Raw Sentinel-1D Radiometric Terrain Corrected (RTC)
- **Pipeline Scripts**:
  ```bash
  python tw01/download_rtc.py
  python tw01/build_demo.py
  python tw01/verify_demo.py
  ```
- **Provider**: Alaska Satellite Facility (ASF) DAAC / Copernicus Open Access Hub.

### C. Raw Sentinel-2 L2A Multitemporal Surface Reflectance
- **Pipeline Scripts**:
  ```bash
  python tw08/download_s2_aoi.py
  python tw08/build_tw08a.py
  python tw08/build_tw08a_qa_v2.py
  ```
- **Provider**: Microsoft Planetary Computer STAC / Earth Search STAC.
- **Acquisitions**: 2026/10/11, 2026/10/16, 2026/10/26, 2026/11/05.

---

## 4. Verification & Testing

The repository is fully verified against the in-tree Tier 1 assets:

```bash
# Backend pytest suite (100 passed, 25 skipped, 0 failed)
pytest tests/backend/ tests/agent/ -v

# Specific TW-05 Agent, Statutory Relief, and GIS tests (27 passed)
pytest tests/backend/test_gis_api.py tests/backend/test_tw05_agro_api.py tests/agent/test_tw05_gemini_agent.py -v

# Frontend Vitest suite (31 passed across 5 test files)
cd frontend && npm test
```
