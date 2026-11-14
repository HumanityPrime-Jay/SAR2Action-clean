# PHASE 3C — Demo Performance & Cache Resilience Report (`DEMO_PERFORMANCE.md`)

**Date:** 2026-10-24  
**Development Mode:** `PROJECT_MODE = PRE_COMPETITION_RND`  
**Benchmark Script:** [`scripts/run_demo_performance_benchmark.py`](file:///D:/NASA/SAR2Action/scripts/run_demo_performance_benchmark.py)  
**Raw JSON Output:** [`data/processed/phase3c_performance_benchmark.json`](file:///D:/NASA/SAR2Action/data/processed/phase3c_performance_benchmark.json)  

---

## 1. Executive Summary

To guarantee responsive, uninterrupted live demonstrations under both `DEMO_MODE = LIVE` and `DEMO_MODE = CACHED_REAL_DATA`, the deterministic vertical slice (`FastAPI` + `sar/change/` + RGBA PNG renderer) was benchmarked across all seven required operations:

1. **Preset AOI Load (`AOI-OKI-04`, `3,148,830` valid 10 m pixels):** **`15.42 ms`** median (`37.93 ms` slowest) via persisted real-NISAR cache (`analysis_store.json` + `fingerprint_store.json`).
2. **Cached Layer Load (`GET /api/layers/{layer_id}` + `GET /api/layers/{layer_id}/image.png`):** **`113.39 ms`** median (`113.66 ms` slowest).
3. **Evidence Record Retrieval (`GET /api/evidence/{evidence_id}`):** **`94.33 ms`** median (`120.02 ms` slowest).
4. **Custom `5 km × 5 km` AOI (`247,506` valid 10 m pixels):** **`1.722 s`** cold live HDF5 slice + 10 RGBA PNG renders (`32.33 MiB` peak Python memory); **`21.14 ms`** on warm cache hit.
5. **Custom `10 km × 10 km` AOI (`996,004` valid 10 m pixels):** **`3.513 s`** cold live HDF5 slice + 10 RGBA PNG renders (`108.58 MiB` peak Python memory); **`14.90 ms`** on warm cache hit.
6. **Custom `30 km × 30 km` AOI (`8,979,002` valid 10 m pixels):** **`11.338 s`** cold live HDF5 slice + 10 RGBA PNG renders (`967.52 MiB` peak Python memory); **`18.40 ms`** on warm cache hit.

---

## 2. Quantitative Benchmark Table

| Operation | Valid 10 m Pixels / Area | Cache State | Iterations | Median Runtime | Slowest Runtime | Peak Traced Python Alloc (`MiB`) | Full-Frame Equivalent RAM Avoided |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Preset AOI Load (`AOI-OKI-04`, `POST /api/radar-fingerprint`)** | `3,148,830` px (`314.88 km²`) | **Cache Hit (`True`)** | 5 | **`15.42 ms` (`0.015 s`)** | `37.93 ms` (`0.038 s`) | `0.63 MiB` | `26.44 GiB` (`>99.99%` avoided) |
| **2. Cached Layer Load (`GET /api/layers/{id}` + `/image.png`)** | `E-FLAGSHIP-OKI-004_delta_hv` (`568.5 KB` PNG) | **Cache Hit (`True`)** | 5 | **`113.39 ms` (`0.113 s`)** | `113.66 ms` (`0.114 s`) | `5.19 MiB` | `26.44 GiB` |
| **3. Evidence Retrieval (`GET /api/evidence/E-FLAGSHIP-OKI-004`)** | `3,148,830` px (`314.88 km²`) | **Cache Hit (`True`)** | 5 | **`94.33 ms` (`0.094 s`)** | `120.02 ms` (`0.120 s`) | `4.26 MiB` | `26.44 GiB` |
| **4a. Custom `5 km × 5 km` AOI (Cold Live HDF5 + 10 PNGs)** | `247,506` px (`24.75 km²`) | **Cold Miss (`False`)** | 3 | **`1,722.19 ms` (`1.722 s`)** | `1,722.94 ms` (`1.723 s`) | `32.33 MiB` | `26.44 GiB` (`99.88%` reduction) |
| **4b. Custom `5 km × 5 km` AOI (Warm Repeat)** | `247,506` px (`24.75 km²`) | **Cache Hit (`True`)** | 3 | **`21.14 ms` (`0.021 s`)** | `22.33 ms` (`0.022 s`) | `0.23 MiB` | `26.44 GiB` |
| **5a. Custom `10 km × 10 km` AOI (Cold Live HDF5 + 10 PNGs)** | `996,004` px (`99.60 km²`) | **Cold Miss (`False`)** | 3 | **`3,512.55 ms` (`3.513 s`)** | `3,541.86 ms` (`3.542 s`) | `108.58 MiB` | `26.44 GiB` (`99.60%` reduction) |
| **5b. Custom `10 km × 10 km` AOI (Warm Repeat)** | `996,004` px (`99.60 km²`) | **Cache Hit (`True`)** | 3 | **`14.90 ms` (`0.015 s`)** | `15.22 ms` (`0.015 s`) | `0.23 MiB` | `26.44 GiB` |
| **6a. Custom `30 km × 30 km` AOI (Cold Live HDF5 + 10 PNGs)** | `8,979,002` px (`897.90 km²`) | **Cold Miss (`False`)** | 2 | **`11,338.49 ms` (`11.338 s`)** | `11,358.90 ms` (`11.359 s`) | `967.52 MiB` | `26.44 GiB` (`96.43%` reduction) |
| **6b. Custom `30 km × 30 km` AOI (Warm Repeat)** | `8,979,002` px (`897.90 km²`) | **Cache Hit (`True`)** | 3 | **`18.40 ms` (`0.018 s`)** | `20.00 ms` (`0.020 s`) | `0.23 MiB` | `26.44 GiB` |

---

## 3. Demo Fallback Architecture (`DEMO_MODE = LIVE | CACHED_REAL_DATA`)

Per Phase 3C Item 10, `ScienceService` (`backend/app/services/science_service.py`) supports two explicit runtime modes, configurable via environment variable `SAR2ACTION_DEMO_MODE` or `POST /api/demo-mode`:

1. **`DEMO_MODE = LIVE` (Default):**
   - Preset AOIs (`AOI-OKI-01` through `AOI-OKI-04`, `AOI-ENG-01`, `AOI-ENG-02`) and previously queried custom AOIs return immediately (`~15–21 ms`) from the persisted real-NISAR cache (`data/cache/analysis_store.json`, `data/cache/fingerprint_store.json`, `data/cache/evidence_store.json`, `data/cache/layer_store.json`, `data/cache/layer_pngs/*.png`) with `cache_hit = True`.
   - New custom AOIs slice the local NISAR L2 GCOV HDF5 granules (`data/raw/scenes/*.h5`) using `[512, 512]` chunk-aligned windowed reads, compute all 10 raster layers, persist them to disk, and return `cache_hit = False`.
2. **`DEMO_MODE = CACHED_REAL_DATA` (Offline / Demo-Safe Mode):**
   - Serves exclusively from pre-generated real NISAR-derived raster overlays (`data/cache/layer_pngs/*.png`), `EvidenceRecord`s (`evidence_store.json`), `RadarFingerprintResponse`s (`fingerprint_store.json`), and `AnalyzeChangeResponse`s (`analysis_store.json`) without requiring live HDF5 file access during a presentation.
   - **Strict Anti-Fabrication Guarantee:** `CACHED_REAL_DATA` never synthesizes or mocks data; every pixel, percentile, and `EvidenceRecord` was deterministically computed from real NASA Earthdata NISAR L2 GCOV granules (`T010_F176` and `T047_F087`). If an un-cached custom AOI is requested while local HDF5 granules are offline in `CACHED_REAL_DATA` mode, the API refuses honestly with `HTTP 422 CACHED_AOI_NOT_FOUND`.
