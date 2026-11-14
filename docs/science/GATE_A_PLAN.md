# Gate A — NISAR L-Band GCOV Candidate AOI & Scene Discovery Plan

> **Objective:** Identify at least three candidate AOIs and determine whether each has $\ge 2$ scientifically comparable NISAR L-band Level-2 GCOV observations before committing the flagship case.  
> **Selection Rule:** **Science quality first** (*Science quality > story preference*).

---

## 1. Candidate AOI Hierarchy

### Candidate Case A — Indonesia Wildfire / Peatland Landscape (Preferred Narrative)
- **Target Region:** Riau / Jambi / South Sumatra or Central Kalimantan peat-fire-prone landscapes, Indonesia.
- **Initial Search Bounding Boxes (WGS84 `[min_lon, min_lat, max_lon, max_lat]`):**
  - `AOI-A1 (Riau, Sumatra)`: `[101.20, 0.20, 102.80, 1.80]`
  - `AOI-A2 (South Sumatra / Ogan Komering Ilir)`: `[104.80, -3.60, 106.00, -2.60]`
  - `AOI-A3 (Central Kalimantan / Pulang Pisau)`: `[113.60, -3.10, 114.60, -2.00]`
- **Physical Scattering Interest:** L-band ($\lambda \approx 24\text{ cm}$) penetrates smoke and cloud cover, interacting with woody canopy volume (`HV`) and surface/trunk-ground scattering (`HH`).
- **Key Risk:** Repeat-pass NISAR L-band GCOV public archive density over equatorial Southeast Asia in 2026 must be verified empirically.

### Candidate Case B — 2026 California Wildfire-Related Region (High Data & Reference Density)
- **Target Region:** California wildfire-affected landscapes (e.g., Northern/Central/Southern California foothills and forested corridors with strong NASA/JPL NISAR calibration/validation and science coverage).
- **Initial Search Bounding Boxes (WGS84 `[min_lon, min_lat, max_lon, max_lat]`):**
  - `AOI-B1 (Northern California / Park-Shasta-Trinity corridor)`: `[-122.40, 39.70, -121.20, 40.70]`
  - `AOI-B2 (Southern California / Transverse Ranges)`: `[-118.90, 34.10, -117.60, 34.80]`
- **Physical Scattering Interest:** Well-characterized L-band repeat-pass acquisitions over chaparral and montane forest regimes.

### Candidate Case C — High-Signal Fallback Earth-Change Region (Science-First Guarantee)
- **Target Region:** Any region with verified, high-SNR, repeat-pass NISAR L-band Level-2 GCOV coverage exhibiting strong, unambiguous surface backscatter change (e.g., Mississippi/Amazon/Pantanal wetland inundation shift, agricultural harvest/tillage transition in North America, or forest disturbance).
- **Purpose:** Guarantees that even if wildfire AOIs have limited public repeat-pass GCOV pairs, **SAR2Action** demonstrates 100% real, scientifically valid NISAR L2 GCOV change analysis.

---

## 2. Mandatory Scene Manifest Fields

Every evaluated granule and candidate pair will be recorded in `data/scenes/scene_manifest.json` with the following fields:

| Field | Description | Example |
| :--- | :--- | :--- |
| `aoi_id` | Candidate AOI identifier | `"AOI-A1"` / `"AOI-B1"` / `"AOI-C1"` |
| `case_tier` | Case priority tier | `"Case A"` / `"Case B"` / `"Case C"` |
| `scene_id` | Full NISAR granule / product identifier | `"NISAR_L2_PR_GCOV_..."` |
| `product_type` | Product level & short name | `"NISAR_L2_GCOV"` |
| `acquisition_start_utc` | ISO-8601 start UTC | `"2026-08-01T11:20:00Z"` |
| `acquisition_end_utc` | ISO-8601 stop UTC | `"2026-08-01T11:20:35Z"` |
| `orbit_number` | Absolute orbit number | `1240` |
| `track_frame` | Relative track / frame number | `"T012_F2000"` |
| `orbit_pass_direction` | Pass direction | `"Ascending"` or `"Descending"` |
| `look_direction` | Antenna look direction | `"Right"` or `"Left"` |
| `frequency_group` | Primary HDF5 grid frequency group | `"frequencyA"` |
| `available_polarizations` | Diagonal covariance terms present | `["HH", "HV"]` (`HHHH`, `HVHV`) |
| `product_maturity` | Product maturity level | `"Provisional"` / `"Validated"` |
| `crid` | Composite Release Identifier | `"P01101"` |
| `crs_epsg` | Projected coordinate system EPSG | `32748` |
| `grid_spacing_m` | `[dx, dy]` pixel spacing in meters | `[20.0, 20.0]` |
| `spatial_coverage_ratio` | Footprint overlap with AOI `[0.0, 1.0]` | `0.98` |
| `quality_notes` | Known data quality / mask issues | `"Sub-swath edge mask on western 3% of frame"` |
| `pair_compatibility_status` | Output of `validate_scene_pair` | `"COMPARABLE"` / `"LIMITED"` / `"INSUFFICIENT_EVIDENCE"` |
| `rejection_reason` | Explicit reason if rejected | `null` or `"Opposite orbit pass direction"` |

---

## 3. Gate A Execution Procedure & Actual SAR Illumination Rule

> **Mandatory Gate A.2 Discovery Rule:**  
> **CMR bounding-box overlap is NOT sufficient evidence of actual SAR illumination.**  
> Because NISAR Level-2 GCOV granules allocate the fixed ~`328 × 336 km` UTM frame grid even for short partial-frame datatakes (`isFullFrame = False`, e.g. `_N_P_J_` partial frame tokens), a granule's frame bounding box can overlap a target AOI while the actual illuminated radar swath covers only a small corner of the frame.
>
> **Before approving future flagship scenes:**
> 1. Inspect `isFullFrame` (`FULL_FRAME` attribute in CMR / `_N_F_J_` vs `_N_P_J_` granule coverage indicator / `/science/LSAR/identification/isFullFrame`).
> 2. Prefer `isFullFrame = True` scenes.
> 3. If a scene is a partial frame (`isFullFrame = False`), retrieve and inspect its companion `_LATLON.kml` (or `/science/LSAR/identification/boundingPolygon`) to extract the actual illuminated footprint polygon before downloading the multi-GB HDF5 file.
> 4. Require actual illuminated overlap with the intended target AOI, not merely frame-grid bounding box intersection.

1. **Query Catalogs (`scripts/discover_nisar_gcov.py`)**:
   - Query NASA CMR (`https://cmr.earthdata.nasa.gov/search/granules.json`) and ASF Search API (`asf_search`) for `NISAR` L-band Level-2 `GCOV` granules intersecting `AOI-A*`, `AOI-B*`, and `AOI-C*`.
2. **Group by Repeat-Pass Geometry & Check Full/Partial Frame Illumination**:
   - Group returned granules by `(aoi_id, track_frame, orbit_pass_direction, look_direction)`.
   - Filter for groups containing $\ge 2$ distinct acquisition dates ($T_0 < T_1$).
   - Verify `is_full_frame` and inspect `_LATLON.kml` companion sidecars to confirm actual illuminated footprint overlap with the target AOI.
3. **Inspect HDF5 Metadata & Valid Overlap**:
   - Inspect `/science/LSAR/identification` and `/science/LSAR/GCOV/grids/frequencyA` to verify `listOfPolarizations`, `xCoordinateSpacing`, `yCoordinateSpacing`, `epsg`, and `mask` (`0 < mask < 255`).
4. **Run `validate_scene_pair` & Populate `data/scenes/scene_manifest.json`**:
   - Rank candidate AOIs by `pair_compatibility_status` (`COMPARABLE` > `LIMITED`), actual illuminated AOI overlap, and event-bracketing temporal sequence (`PRE-EVENT → EVENT/POST-EVENT → FOLLOW-UP`).
   - Select the highest-scoring scientifically valid case.
