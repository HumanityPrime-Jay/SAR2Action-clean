# SAR2Action — Evidence & Provenance Schema Specification

> **Schema Version:** `evidence-schema-v1.0`  
> **Code Implementation:** [`backend/app/schemas/evidence.py`](backend/app/schemas/evidence.py)  
> **Core Principle:** *One claim → One evidence trail.* Every quantitative output from any scientific module or API endpoint is encapsulated in a strongly-typed Pydantic v2 model and persisted with a unique `evidence_id`.

---

## 1. Enumerations & Scientific Guardrail Types

### 1.1 `ScienceQualityStatus`
Represents the mandatory Unknown-Aware epistemic state:
- `OBSERVED`: Single-scene valid radar observation.
- `COMPARABLE`: Multi-temporal pair passed all compatibility checks with sufficient valid pixel coverage ($\ge 0.50$).
- `LIMITED`: Multi-temporal pair is comparable with documented caveats (e.g., partial valid coverage $0.10 \le r < 0.50$, single-pol only, or minor CRID difference).
- `INSUFFICIENT_EVIDENCE`: Pair incompatible or valid pixel coverage $< 0.10$. Quantitative change claims are blocked.

### 1.2 `PolarizationChannel`
- `HH` (`HHHH` diagonal covariance term)
- `HV` (`HVHV` diagonal covariance term)
- `VV` (`VVVV` diagonal covariance term)
- `VH` (`VHVH` diagonal covariance term)

### 1.3 `EvidenceType`
- `scene_observation`: Single-epoch GCOV inspection.
- `pair_validation`: Output of `validate_scene_pair(scene_a, scene_b, aoi)`.
- `radar_change_map`: Full-AOI radiometric difference raster & summary.
- `radar_fingerprint`: Point, polygon, or ROI quantitative backscatter breakdown.

### 1.4 `StandardLimitationCode`
Standardized limitation tags automatically attached to evidence records:
- `cause_not_determined` (*Always present on radar change records unless independently validated*)
- `not_burn_severity_or_fire_damage`
- `single_scene_pair_no_temporal_persistence`
- `hv_polarization_unavailable`
- `hh_polarization_unavailable`
- `partial_valid_coverage`
- `crid_version_difference`
- `grid_resampled_to_reference`

---

## 2. Scene Pair Compatibility Schema (`ScenePairValidationResult`)

Returned by `validate_scene_pair(scene_a, scene_b, aoi)`:

```json
{
  "compatible": true,
  "reasons": [],
  "warnings": [
    "HV polarization available in both scenes; valid pixel overlap is 88.4%."
  ],
  "valid_overlap_ratio": 0.884,
  "spatial_overlap_ratio": 0.992,
  "available_polarizations": ["HH", "HV"],
  "scene_ids": [
    "NISAR_L2_PR_GCOV_001_005_A_012_2000_DHDH_A_20260801T112000_20260801T112035_P01101_F_N_J_001",
    "NISAR_L2_PR_GCOV_001_005_A_012_2000_DHDH_A_20260813T112002_20260813T112037_P01101_F_N_J_001"
  ],
  "t0_utc": "2026-08-01T11:20:00Z",
  "t1_utc": "2026-08-13T11:20:02Z",
  "frequency_band": "L",
  "frequency_group": "frequencyA",
  "same_orbit_pass": true,
  "same_look_direction": true,
  "crs_compatible": true,
  "grid_aligned": true,
  "science_status": "COMPARABLE"
}
```

### Schema Invariants
- If `compatible == false`, `science_status` **must** be `"INSUFFICIENT_EVIDENCE"` and `reasons` **must** be non-empty.
- If `science_status == "INSUFFICIENT_EVIDENCE"`, `compatible` **must** be `false`.

---

## 3. Core Evidence Object (`EvidenceRecord`)

Every quantitative result produces an `EvidenceRecord`:

```json
{
  "evidence_id": "E-0001",
  "evidence_type": "radar_fingerprint",
  "scene_ids": [
    "NISAR_L2_PR_GCOV_..._20260801",
    "NISAR_L2_PR_GCOV_..._20260813"
  ],
  "roi_id": "ROI-01",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[102.1, -0.5], [102.2, -0.5], [102.2, -0.4], [102.1, -0.4], [102.1, -0.5]]]
  },
  "polarizations": ["HH", "HV"],
  "t0_db": {
    "HH": { "mean": -7.42, "median": -7.35, "std": 1.18, "min": -12.10, "max": -3.20, "p10": -8.95, "p90": -5.90 },
    "HV": { "mean": -13.15, "median": -13.10, "std": 1.05, "min": -17.40, "max": -9.80, "p10": -14.50, "p90": -11.80 }
  },
  "t1_db": {
    "HH": { "mean": -8.90, "median": -8.82, "std": 1.32, "min": -14.00, "max": -4.10, "p10": -10.60, "p90": -7.20 },
    "HV": { "mean": -16.25, "median": -16.20, "std": 1.24, "min": -21.00, "max": -11.90, "p10": -17.85, "p90": -14.65 }
  },
  "delta_db": {
    "HH": { "mean": -1.48, "median": -1.45, "std": 0.94, "min": -5.20, "max": 1.80, "p10": -2.70, "p90": -0.25 },
    "HV": { "mean": -3.10, "median": -3.08, "std": 0.88, "min": -6.40, "max": 0.50, "p10": -4.25, "p90": -1.95 }
  },
  "magnitude_db": {
    "HH": { "mean": 1.62, "median": 1.51, "std": 0.67, "min": 0.01, "max": 5.20, "p10": 0.65, "p90": 2.75 },
    "HV": { "mean": 3.12, "median": 3.09, "std": 0.81, "min": 0.05, "max": 6.40, "p10": 2.00, "p90": 4.25 }
  },
  "combined_change_db": {
    "metric_name": "Combined Radar Change",
    "disclaimer": "Custom visualization metric — not a hazard score, fire probability, damage score, or official burn-severity index.",
    "stats": { "mean": 4.74, "median": 4.62, "std": 1.15, "min": 0.12, "max": 11.10, "p10": 3.10, "p90": 6.45 }
  },
  "summary_statistics": {
    "total_pixel_count": 16000,
    "valid_pixel_count": 14144,
    "missing_pixel_count": 1856
  },
  "valid_pixel_count": 14144,
  "coverage_ratio": 0.884,
  "missing_data_ratio": 0.116,
  "quality_status": "COMPARABLE",
  "algorithm_version": "change-v1.0.0",
  "processing_metadata": {
    "t0_acquisition_utc": "2026-08-01T11:20:00Z",
    "t1_acquisition_utc": "2026-08-13T11:20:02Z",
    "product_type": "NISAR_L2_GCOV",
    "frequency_band": "L",
    "frequency_group": "frequencyA",
    "orbit_pass_direction": "Ascending",
    "look_direction": "Right",
    "t0_crid": "P01101",
    "t1_crid": "P01101",
    "crs_epsg": 32748,
    "pixel_spacing_m": [20.0, 20.0],
    "computed_at_utc": "2026-10-23T12:00:00Z"
  },
  "limitations": [
    "cause_not_determined",
    "not_burn_severity_or_fire_damage",
    "single_scene_pair_no_temporal_persistence"
  ]
}
```

---

## 4. Radar Fingerprint Schema (`RadarFingerprint`)

Directly powers Experience 2 (**Radar Fingerprint**) with explicit null-safety when a polarization is unavailable:

- `fingerprint_id`: Unique ID
- `evidence_id`: Linked `EvidenceRecord` ID (`E-xxxx`)
- `roi_id`: Selected point/polygon identifier
- `t0_acquisition_utc` / `t1_acquisition_utc`
- `available_polarizations`: e.g. `["HH"]` or `["HH", "HV"]`
- `hh`: `Optional[PolarizationChangeBreakdown]` (`t0_mean_db`, `t1_mean_db`, `delta_mean_db`, `magnitude_mean_db`)
- `hv`: `Optional[PolarizationChangeBreakdown]` (`null` when HV is absent — never fabricated!)
- `combined_radar_change_db`: `Optional[float]` (`null` when either HH or HV is absent)
- `valid_pixel_count`: `int`
- `valid_coverage_ratio`: `float`
- `missing_data_ratio`: `float`
- `pair_compatibility`: `ScenePairValidationResult`
- `quality_status`: `ScienceQualityStatus`
- `what_we_observed`: `list[str]`
- `possible_interpretations`: `list[str]`
- `what_we_do_not_know`: `list[str]`

---

## 5. Claim-to-Pixel & Five-Scene Evidence Story Schema (`EvidenceStory`)

Powers Experience 3 (**Evidence Story**) and the **Single-Orchestrator AI Investigator**:

- Every `EvidenceClaim` within a scene contains:
  - `claim_id`: Unique statement ID (`C-001`)
  - `statement`: Human-readable quantitative statement (e.g., `"Mean HV backscatter changed by -3.10 dB across 14,144 valid comparable pixels."`)
  - `evidence_ids`: Non-empty list of backing `evidence_id`s (`["E-0001"]`)
  - `target_roi_id`: AOI/ROI to zoom to when clicked
  - `target_polarization`: Layer polarization to activate on click
  - `target_layer_mode`: Map mode to display (`t0`, `t1`, `swipe`, `delta`, `magnitude`, `combined`, `uncertainty_mask`)
- Every `EvidenceStory` enforces the 5 canonical scenes:
  1. `Scene 1: Before` (`scene_key = "before"`)
  2. `Scene 2: The Shift` (`scene_key = "the_shift"`)
  3. `Scene 3: Investigate` (`scene_key = "investigate"`)
  4. `Scene 4: What We Know / What We Don't Know` (`scene_key = "what_we_know"`)
  5. `Scene 5: Evidence Story` (`scene_key = "evidence_story"`)
