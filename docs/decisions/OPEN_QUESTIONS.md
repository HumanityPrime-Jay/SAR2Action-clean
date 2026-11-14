# Open Scientific & Engineering Questions (`OPEN_QUESTIONS.md`)

> **Policy:** When a scientific assumption or external constraint is uncertain, we do not guess. We record it here, define how we will verify it empirically, and establish a safe default.

---

## OQ-001 — Public Archive Coverage of Repeat-Pass NISAR L2 GCOV Across Candidate AOIs (Gate A)
- **Status:** OPEN (First executable task in Phase 1 / Gate A)
- **Question:** Among Candidate Case A (Indonesia Sumatra/Kalimantan peatland/wildfire landscapes), Candidate Case B (2026 California wildfire-related regions), and Candidate Case C (alternative strong surface-change region), which AOI currently has $\ge 2$ publicly accessible, repeat-pass, same-orbit NISAR L-band Level-2 GCOV granules on ASF DAAC / NASA Earthdata CMR as of 2026-10-23?
- **Verification Method:** Run ASF / NASA CMR catalog query (`NISAR_L2_GCOV` / `GCOV`) across the candidate bounding boxes and inspect actual HDF5 metadata (`CRID`, `orbitPassDirection`, `lookDirection`, `listOfPolarizations`, valid pixel overlap).
- **Safe Default:** Do not hardcode Indonesia into the codebase. Select the primary demo case strictly via **Gate A** (*Science quality > story preference*).

---

## OQ-002 — NISAR GCOV Split-Spectrum Frequency Groups (`frequencyA` vs. `frequencyB`)
- **Status:** OPEN (Verify upon inspecting Gate A HDF5 granules)
- **Question:** NISAR L-band GCOV granules store primary science grids under `/science/LSAR/GCOV/grids/frequencyA` (typically 20 MHz or 40 MHz bandwidth) and optionally secondary grids under `/science/LSAR/GCOV/grids/frequencyB` (typically 5 MHz bandwidth) with different spatial resolutions.
- **Verification Method:** Inspect `/science/LSAR/GCOV/grids/frequencyA/xCoordinateSpacing` and `listOfPolarizations` in the target Gate A granules.
- **Safe Default:** Lock the default GCOV reader and `validate_scene_pair` to `frequencyA` and require both $T_0$ and $T_1$ to use the exact same frequency group (`frequency_group == "frequencyA"`).

---

## OQ-003 — GCOV `mask` Bit/Category Encoding Across CRID Versions
- **Status:** OPEN (Verify upon inspecting Gate A HDF5 granules)
- **Question:** In NISAR Level-2 GCOV HDF5 files, the `/science/LSAR/GCOV/grids/frequencyA/mask` dataset encodes valid data, radar shadow, layover, sub-swath fill, and water/no-data flags. Exact integer flag values can vary slightly between simulated/sample CRIDs and commissioned science CRIDs.
- **Verification Method:** Read the HDF5 dataset attributes (`valid_min`, `valid_max`, `_FillValue`, `flag_values`, `flag_meanings`, `description`) directly from the downloaded HDF5 files during Gate A inspection before hardcoding bitmask filters.
- **Safe Default:** Always combine the HDF5 `mask` metadata inspection with explicit numerical domain checks: `np.isfinite(power) & (power > 0) & (power != fill_value)`.

---

## OQ-004 — 2026-10-28 Official Challenge Statement Rules on External Context Layers
- **Status:** OPEN until 2026-10-28 challenge statement release
- **Question:** Will the final NASA Space Apps 2026 (*Dancing with the SARs*) statement encourage contextual overlays (e.g., known historical wildfire perimeters, administrative place names) or require a strictly NISAR-only visualization?
- **Verification Method:** Review the official challenge rules on 2026-10-28 when switching to `PROJECT_MODE = COMPETITION_BUILD`.
- **Safe Default:** Keep all quantitative calculations 100% NISAR-native, and isolate any external reference layer behind a single configuration flag (`ENABLE_EXTERNAL_CONTEXT=true|false`) with clear UI separation (`Context` vs. `NISAR-derived evidence`).
