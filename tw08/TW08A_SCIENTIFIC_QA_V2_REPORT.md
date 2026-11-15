# TW-08A Scientific Quality Assurance v2 Report

**Scope & Guardrails**
- **Reference Baseline (Read-Only & Verified Unmodified)**: [`tw08/sentinel2-demo-v1/`](file:///D:/NASA/SAR2Action/tw08/sentinel2-demo-v1/manifest.json) (all 29 artifacts + SHA-256 hashes verified intact via [`verify_tw08a.py`](file:///D:/NASA/SAR2Action/tw08/verify_tw08a.py)).
- **Independent QA v2 Outputs**: Written exclusively to [`tw08/sentinel2-qa-v2/qa_v2_manifest.json`](file:///D:/NASA/SAR2Action/tw08/sentinel2-qa-v2/qa_v2_manifest.json), [`tw08/sentinel2-qa-v2/candidate_181_quality_and_scl_v2.csv`](file:///D:/NASA/SAR2Action/tw08/sentinel2-qa-v2/candidate_181_quality_and_scl_v2.csv), and [`tw08/sentinel2-qa-v2/qa_v2_sensitivity_diagnostics.png`](file:///D:/NASA/SAR2Action/tw08/sentinel2-qa-v2/qa_v2_sensitivity_diagnostics.png) by [`build_tw08a_qa_v2.py`](file:///D:/NASA/SAR2Action/tw08/build_tw08a_qa_v2.py) and verified via [`verify_tw08a_qa_v2.py`](file:///D:/NASA/SAR2Action/tw08/verify_tw08a_qa_v2.py).
- **Overall QA Gate**: **`PASS`** (`overall_qa_gate = "PASS"`).
- **Protected Assets**: `tw01/`, `tw03/`, `sar/`, TW-01 `181` SAR candidate definitions, and TW-07 relief calculations remain unmodified.

---

## Audit 1: `SCL = 4 / 5 / 6` Semantic Integrity (Vegetation vs. Bare Soil vs. Water)

Clear-sky mask classes `{4, 5, 6}` represent **unoccluded land/water surface classes** — **not** "all healthy vegetation". Treating `{4, 5, 6}` as vegetation would misclassify bare/harvested soil (`SCL=5`) and open water (`SCL=6`).

- **`2026-10-11` (`S2B_51QTG_20261011_0_L2A`, 97.57% clear)**:
  - `SCL = 4` (Vegetation): `28,691` px (20 m) / `46.99%` of clear `{4,5,6}` pixels — NDVI median `0.6504` (`p10=0.4399`, `p90=0.7984`), NDRE median `0.4847`, LSWI median `0.2700`.
  - `SCL = 5` (Not Vegetated / Bare Soil): `32,361` px (20 m) / `53.01%` of clear `{4,5,6}` pixels — NDVI median `0.2208` (`p10=0.0945`, `p90=0.4139`), NDRE median `0.1787`, LSWI median `0.0346`. Over half of clear pixels on 10/11 are non-vegetated soil/built surfaces.
  - `SCL = 6` (Water): `0` px.
- **`2026-11-05` (`S2C_51QTG_20261105_0_L2A`, 79.08% clear)**:
  - `SCL = 4` (Vegetation): `17,980` px (20 m) / `36.34%` of clear `{4,5,6}` pixels — NDVI median `0.5555` (`p10=0.4300`, `p90=0.6920`), NDRE median `0.3846`, LSWI median `0.1828`.
  - `SCL = 5` (Not Vegetated / Bare Soil): `31,494` px (20 m) / `63.65%` of clear `{4,5,6}` pixels — NDVI median `0.2278` (`p10=0.0861`, `p90=0.4191`), NDRE median `0.1810`, LSWI median `0.0203`.
  - `SCL = 6` (Water): `6` px (20 m) / `24` nested 10 m pixels (`0.012%` of clear `{4,5,6}`) — NDVI median `0.0290` (`min=-0.0069`), NDRE median `-0.1508`, LSWI median **`+0.3500`**. Water shows near-zero NDVI, strongly negative NDRE, and elevated positive LSWI, cleanly separated from healthy vegetation and never labeled vegetation.

Among the `181` TW-01 candidates, **zero** included (`n=119`) or excluded (`n=62`) parcels exceed 20% `SCL=6` water on `2026-10-11` or `2026-11-05`.

---

## Audit 2: BOA Offset, 10 m / 20 m Affine Alignment, and Finite Pixel Verification

- **STAC BOA Offset (`earthsearch:boa_offset_applied = true` on all 4 scenes)**:
  - On `2026-10-11` `SCL=4` vegetation, minimum B04 `uint16` DN is `316` -> `DN * 0.0001 = 0.0316` (physically valid); subtracting `-0.1` again would yield `-0.0684` (unphysical negative reflectance).
  - On `2026-11-05` `SCL=4` vegetation, minimum B04 DN is `337` -> `0.0337` (vs. `-0.0663` if erroneously double-shifted); on `SCL=6` water, minimum B04 DN is `895` -> `0.0895` (vs. `-0.0105`).
- **CRS & Exact Affine Alignment (`EPSG:32651`, Bounds `[222140.0, 2622180.0, 227260.0, 2627280.0]`)**:
  - All 16 10 m input bands share `shape = [510, 512]`, `transform = [10.0, 0.0, 222140.0, 0.0, -10.0, 2627280.0]`.
  - All 20 20 m input bands (`B05, B8A, B11, B12, SCL`) share `shape = [255, 256]`, `transform = [20.0, 0.0, 222140.0, 0.0, -20.0, 2627280.0]`.
  - `origin_x_offset_m = 0.0`, `origin_y_offset_m = 0.0`, `exact_2x_integer_nesting = true`.
- **v1 GeoTIFF Bounds & Finite Counts**:
  - Single-date (`ndvi`, `ndre`, `lswi`) and `2026-10-11 -> 2026-11-05` delta rasters match shapes and fall strictly within `[-1, 1]` and `[-2, 2]` (e.g. `ndvi_20261011.tif`: `244,200` finite px; `ndvi_20261105.tif`: `197,897` finite px; `delta_ndvi_20261011_20261105.tif`: `195,550` finite px; `delta_ndre`/`delta_lswi`: `48,895` finite px).

---

## Audit 3: Quality Comparison — `119` Sufficient vs. `62` Insufficient Candidates (`4,863` Farmland Summary)

- **181 TW-01 Candidate Breakdown**:
  - **Sufficient Clear-Both Dates (`10 m` & `20 m` >= 80% clear & minimum pixels on both `2026-10-11` and `2026-11-05`)**: **`119`** parcels (`119` meet both 10 m and 20 m strict gates; `0` `all_touched` fallbacks across all 181 candidates).
  - **Insufficient Optical Evidence**: **`62`** parcels:
    - Failed `2026-11-05` only: **`47`** (driven by the SW/Central cloud bank on 11/05; median excluded cloud/shadow fraction `34.84%` on 11/05 vs `0.00%` on 10/11).
    - Failed `2026-10-11` only: **`4`**.
    - Failed both dates: **`11`**.
- **Mann-Whitney Covariate Balance (`119` vs. `62`)**:
  - `clipped_area_ha`: med `0.4724` vs `0.5091` ha (`p = 0.1292`).
  - `sar_median_delta_vv_db`: med `1.3414` vs `2.5889` dB (`p = 0.1500`).
  - `sar_median_delta_vh_db`: med `3.2146` vs `3.0382` dB (`p = 0.2209`).
  - `ndvi_med_20261011`: med `0.3685` vs `0.2458` (`p = 0.0504`).
  - `centroid_easting_32651`: med `225,156.11` vs `224,175.16` m (`p = 0.0927`, reflecting the western/central 11/05 cloud corridor).
- **Full `4,863` Farmland Layer Summary**:
  - **`3,166`** parcels pass strict clear-both criteria on `10/11` & `11/05`; **`1,697`** parcels have insufficient optical evidence (`INSUFFICIENT OPTICAL EVIDENCE`).

---

## Audit 4: Spatial Autocorrelation & Selection-Bias Sensitivity (SAR–NDVI Co-Variation)

| Specification / Check | Sample (`n`) | Spearman `ρ` (`SAR ΔVH` vs `ΔNDVI`) | Interval / Significance | Notes |
|---|---:|---:|---|---|
| Baseline Strict (`>=80%` cov, `SCL {4,5,6}`) | `119` | `+0.2786` | naive `p = 0.00216` | Also `ρ_VV = +0.2293` (`p = 0.0121`) |
| KNN-5 Moran's I (`delta_ndvi_119`) | `119` | `I = -0.0461` | `perm p = 0.408` | OLS VH residual `I = -0.0153` (`p = 0.779`) |
| `1,000 m` Spatial Block Bootstrap (`28` blocks) | `119` | med `+0.2838` | `95% CI [0.0485, 0.4809]`, `p_boot = 0.016` | `ρ_VV` 95% CI `[0.0819, 0.4082]`, `p_boot = 0.000` |
| `500 m` Spatial Block Bootstrap (`63` blocks) | `119` | med `+0.2851` | `95% CI [0.0486, 0.4741]`, `p_boot = 0.016` | `ρ_VV` 95% CI `[0.0549, 0.4152]`, `p_boot = 0.015` |
| `250 m` Spatial Thinning (`200` random trials) | med `69` | med `+0.4102` | range `[0.2811, 0.5427]`, `100% p < 0.05` | `ρ_VV` med `+0.2614` (`72% p < 0.05`) |
| Relaxed Cloud Gate (`>=50%` cov, `SCL {4,5,6}`) | `135` | `+0.3002` | `p = 0.00040` | `ρ_VV = +0.2448` (`p = 0.00422`) |
| Relaxed Any Clear Pixel (`>=1 px`, `SCL {4,5,6}`) | `158` | `+0.3380` | `p = 1.40e-05` | `ρ_VV = +0.2640` (`p = 0.00080`) |
| IPW Propensity-Weighted (selection bias adj.) | `119` | `+0.3068` | weights `[0.7456, 1.5653]` | Weighted Pearson `r = +0.3844`; `ρ_VV = +0.2558` |
| Exclude Water Strictly (`SCL {4,5}`, `>=80%` cov) | `119` | `+0.2786` | `p = 0.00216` | Identical to baseline (`0` water-skewed parcels in `119`) |
| Strict Vegetation Only Both Dates (`SCL {4}`) | `19` | `+0.3175` | `p = 0.185` (`ρ_VV = -0.3053, p = 0.204`) | Removing `SCL=4 <-> SCL=5` crop/bare transitions leaves `n=19` |

**Interpretation Guardrail**: Cross-sensor positive association between TW-01 Sentinel-1D `ΔVH` and Sentinel-2 `ΔNDVI` is robust to spatial block resampling, spatial thinning, cloud-threshold relaxation, IPW selection weighting, and water exclusion. However, restricting strictly to persistent vegetation (`SCL=4`) drops sample size to `n=19`, showing that canopy-to-bare soil (`SCL=4 <-> SCL=5`) management/phenology transitions drive much of the variation. All multi-temporal metrics remain **descriptive evidence only** — **no crop type (`UNKNOWN`) and no confirmed typhoon damage (`UNKNOWN`) are inferred or passed to TW-07.2 statutory relief estimates**.
