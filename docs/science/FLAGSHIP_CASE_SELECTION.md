# Phase 2B — Flagship Case Selection Report (`FLAGSHIP_CASE_SELECTION.md`)

**Date:** `2026-10-23`  
**Project Mode:** `PRE_COMPETITION_RND`  
**Collection:** `NISAR_L2_GCOV_PROVISIONAL_V1` (`C3904538873-ASF`)  
**Discovery Artifact:** [`data/processed/phase2b_flagship_discovery.json`](file:///D:/NASA/SAR2Action/data/processed/phase2b_flagship_discovery.json)  
**Sidecar Archive:** `data/raw/sidecars/phase2b_flagship/` (`_LATLON.kml`, `_QA_SUMMARY.csv`, `_QA_STATS.h5` — **0 full HDF5 granules downloaded during Phase 2B**)

> [!NOTE]
> **Phase 3C Hardening Note (`2026-10-24`):**  
> Per [`docs/science/FLAGSHIP_LOCK.md`](./FLAGSHIP_LOCK.md) and official issue `isce-framework/isce3#294`, raw `rfiLikelihood` scalars in `_QA_STATS.h5` exceed `[0,1]` and are marked **`rfi_comparison_status = UNRELIABLE_METADATA`** (treated strictly as QA context, not a flagship ranking criterion). In addition, `Cycle 031` on `T010_F176` (`2026-09-18`) has granule ID suffix `_P05023_F_F_J_001` (`orbit/pointing fidelity = Forecast (F)`, `coverage = Full (F)`, `SDS = JPL (J)`).

---

## Executive Summary

Following the Gate A.2 discovery that `T047_F087` (`_N_P_J_`, partial frame) only illuminated the Riau Archipelago / Singapore Strait (`0.0%` mainland Riau overlap despite nominal frame intersection), Phase 2B codified **Rule 7 (Actual Swath Illumination Verification)** in [`SCIENCE_CONTRACT.md`](file:///D:/NASA/SAR2Action/SCIENCE_CONTRACT.md) and [`sar/validation/pair_validator.py`](file:///D:/NASA/SAR2Action/sar/validation/pair_validator.py) and inspected all repeat-pass stacks over **South Sumatra (`AOI-A2` — Ogan Komering Ilir / OKI Peatland Corridor)**, **Mainland Riau (`AOI-A1`)**, and **Northern California (`AOI-B1`)** using official metadata and sidecars (`_LATLON.kml`, `_QA_SUMMARY.csv`, `_QA_STATS.h5`).

### Key Findings
1. **`AOI-A2` (Ogan Komering Ilir / OKI Peatland Corridor, South Sumatra) Has Two Independent 100%-Illuminated Full-Frame Stacks:**
   - **Primary Descending Stack `T119_F090` (`DESCENDING`, `LEFT` look, `4005_DHDH_A`, `HH+HV`, `CRID = P05023`):** All **9 scenes (`2026-06-22` to `2026-10-20`)** are **full-frame (`isFullFrame = True`, `_N_F_J_`, ~35 s datatake, `5.52–5.68 GB`/scene)** with actual illuminated swath `[103.89°E–106.59°E, -4.40°S–-1.73°S]` (`~59,780–61,488 km²`), delivering **`100.0%` actual illuminated coverage of both `AOI-A2` (`[104.50°E, -3.80°S, 106.20°E, -2.30°S]`) and the OKI core peatland corridor (`[104.80°E, -3.60°S, 106.00°E, -2.60°S]`)**.
   - **Low-RFI Companion Ascending Stack `T010_F176` (`ASCENDING`, `LEFT` look, `4005_DHDH_A`, `HH+HV`, `CRID = P05023`):** All **9 scenes (`2026-06-26` to `2026-10-12`)** are also **full-frame (`isFullFrame = True`, `_N_F_J_`, `5.37–5.53 GB`/scene)** with actual illuminated swath `[104.21°E–106.91°E, -4.43°S–-1.79°S]`, delivering **`99.91%` coverage of `AOI-A2` and `100.0%` coverage of the OKI core peatland corridor** with **substantially lower L-band Radio Frequency Interference (RFI)** (`1.12%–4.89%` in key September pairs vs. `12.6%–15.6%` in `T119_F090`).
2. **Rule 7 Eliminated Three False-Positive Stacks in `AOI-A2`:**
   - `T018_F090` (`DESCENDING`): Full-frame (`4.21–4.32 GB`), but its actual illuminated polygon (`[105.98°E–108.67°E]`) covers Bangka Island and the Karimata Strait — **`0.0%` overlap with the OKI core peatland corridor** (`3.55%` edge overlap with wide `AOI-A2`).
   - `T111_F176` (`ASCENDING`): Illuminated swath (`[102.12°E–104.83°E]`) covers Bengkulu / western South Sumatra — **`0.0%` overlap with the OKI core peatland corridor**.
   - `T119_F089` (`DESCENDING`): Illuminated swath (`[-2.42°S–+0.35°N]`) lies north over Jambi — **`0.0%` overlap with the OKI core peatland corridor**.
3. **12-Day & 24-Day Peak Dry-Season Temporal Sequences Replace the 108-Day Span:**
   - Instead of the 108-day pair (`2026-07-04 → 2026-10-20`), which mixes multi-month agricultural cycles, water-table recession, and seasonal transitions, both `T119_F090` and `T010_F176` provide **6 consecutive unbroken 12-day repeat-pass acquisitions** from late August through mid-October (`2026-08-21 → 2026-09-02 → 2026-09-14 → 2026-09-26 → 2026-10-08 → 2026-10-20` on `T119_F090`, and `2026-08-25 → 2026-09-06 → 2026-09-18 → 2026-09-30 → 2026-10-12` on `T010_F176`), directly bracketing the peak South Sumatra dry/peat-fire window.

---

## South Sumatra Timeline (`AOI-A2` — Ogan Komering Ilir Peatland Corridor)

### 1. Primary Descending Stack: Track `119`, Frame `090` (`T119_F090`)
- **Geometry:** `DESCENDING` | **Look Direction:** `LEFT` | **Mode:** `4005_DHDH_A` (`20 MHz` + `5 MHz` split-spectrum)
- **Polarization:** `HH + HV` | **Product Maturity:** `Provisional` | **CRID:** `P05023` (homogeneous across all 9 scenes)
- **Actual Illuminated Swath (`_LATLON.kml` & 40-vertex `boundingPolygon`):** `[103.89°E–106.59°E, -4.40°S–-1.73°S]` (`~59,780–61,488 km²`)
- **Target Overlap:** **`100.0%` of `AOI-A2`** (`[104.50, -3.80, 106.20, -2.30]`) and **`100.0%` of OKI Core Peatland (`[104.80, -3.60, 106.00, -2.60]`)**

| Cycle | Date (`UTC`) | $\Delta t$ | Scene ID | Frame Status | Size (`GB`) | Swath BBox (`[W, S, E, N]`) | OKI Core Overlap | `_QA_STATS.h5` Mean `HHHH` / `HVHV` (`dB`) | `_QA_SUMMARY` Notes |
| :---: | :--- | :---: | :--- | :---: | :---: | :--- | :---: | :---: | :--- |
| `023` | `2026-06-22` | — | `NISAR_L2_PR_GCOV_023_119_D_090_4005_DHDH_A_20260622T111859_20260622T111933_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.54` | `[103.90, -4.40, 106.59, -1.74]` | **`100.0%` (`PASS`)** | `-7.41` / `-13.49` | `PASS` (RFI `11.16%`) |
| `024` | `2026-07-04` | `+12 d` | `NISAR_L2_PR_GCOV_024_119_D_090_4005_DHDH_A_20260704T111858_20260704T111932_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.53` | `[103.90, -4.40, 106.59, -1.74]` | **`100.0%` (`PASS`)** | `-7.65` / `-13.68` | `PASS` (RFI `11.14%`) |
| `025` | `2026-07-16` | `+12 d` | `NISAR_L2_PR_GCOV_025_119_D_090_4005_DHDH_A_20260716T111857_20260716T111932_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.68` | `[103.89, -4.40, 106.59, -1.73]` | **`100.0%` (`PASS`)** | `-7.76` / `-14.05` | `PASS` (RFI `14.12%`) |
| `028` | `2026-08-21` | `+36 d`* | `NISAR_L2_PR_GCOV_028_119_D_090_4005_DHDH_A_20260821T111855_20260821T111930_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.68` | `[103.89, -4.40, 106.59, -1.73]` | **`100.0%` (`PASS`)** | `-7.96` / `-13.63` | `PASS` (RFI `15.61%`) |
| `029` | `2026-09-02` | `+12 d` | `NISAR_L2_PR_GCOV_029_119_D_090_4005_DHDH_A_20260902T111855_20260902T111930_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.68` | `[103.89, -4.40, 106.59, -1.73]` | **`100.0%` (`PASS`)** | `-8.02` / `-13.79` | `PASS` (RFI `12.64%`) |
| `030` | `2026-09-14` | `+12 d` | `NISAR_L2_PR_GCOV_030_119_D_090_4005_DHDH_A_20260914T111855_20260914T111929_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.52` | `[103.90, -4.40, 106.59, -1.74]` | **`100.0%` (`PASS`)** | `-8.03` / `-14.14` | `PASS` (RFI `12.61%`) |
| `031` | `2026-09-26` | `+12 d` | `NISAR_L2_PR_GCOV_031_119_D_090_4005_DHDH_A_20260926T111855_20260926T111929_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.52` | `[103.90, -4.40, 106.59, -1.74]` | **`100.0%` (`PASS`)** | `-8.05` / `-13.59` | `PASS` (RFI `14.13%`) |
| `032` | `2026-10-08` | `+12 d` | `NISAR_L2_PR_GCOV_032_119_D_090_4005_DHDH_A_20261008T111855_20261008T111929_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.52` | `[103.90, -4.40, 106.59, -1.74]` | **`100.0%` (`PASS`)** | `-8.11` / `-13.92` | `PASS` (RFI `17.16%`) |
| `033` | `2026-10-20` | `+12 d` | `NISAR_L2_PR_GCOV_033_119_D_090_4005_DHDH_A_20261020T111855_20261020T111930_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.67` | `[103.89, -4.40, 106.59, -1.73]` | **`100.0%` (`PASS`)** | `-8.14` / `-14.03` | `PASS` (RFI `15.65%`) |

*\*Note: Cycles `026` (`2026-07-28`) and `027` (`2026-08-09`) are absent across South Sumatra stacks in the ASF archive. From `2026-08-21` (`Cycle 028`) through `2026-10-20` (`Cycle 033`), the 12-day repeat cadence is 100% unbroken.*

---

### 2. Low-RFI Companion Ascending Stack: Track `010`, Frame `176` (`T010_F176`)
- **Geometry:** `ASCENDING` | **Look Direction:** `LEFT` | **Mode:** `4005_DHDH_A` | **Polarization:** `HH + HV` | **CRID:** `P05023`
- **Actual Illuminated Swath:** `[104.21°E–106.91°E, -4.43°S–-1.79°S]` (`~58,150–59,830 km²`)
- **Target Overlap:** **`99.91%` of `AOI-A2`** and **`100.0%` of OKI Core Peatland (`[104.80, -3.60, 106.00, -2.60]`)**

| Cycle | Date (`UTC`) | $\Delta t$ | Scene ID | Frame Status | Size (`GB`) | OKI Core Overlap | `_QA_STATS.h5` Mean `HHHH` / `HVHV` (`dB`) | `_QA_SUMMARY` Notes |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| `024` | `2026-06-26` | — | `NISAR_L2_PR_GCOV_024_010_A_176_4005_DHDH_A_20260626T224604_20260626T224637_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.37` | **`100.0%` (`PASS`)** | `-7.67` / `-14.28` | `PASS` (**0 QA warnings**) |
| `025` | `2026-07-08` | `+12 d` | `NISAR_L2_PR_GCOV_025_010_A_176_4005_DHDH_A_20260708T224603_20260708T224638_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.53` | **`100.0%` (`PASS`)** | `-7.84` / `-14.51` | `PASS` (RFI `2.28%`) |
| `026` | `2026-07-20` | `+12 d` | `NISAR_L2_PR_GCOV_026_010_A_176_4005_DHDH_A_20260720T224603_20260720T224637_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.52` | **`100.0%` (`PASS`)** | `-7.81` / `-14.51` | `PASS` (**0 QA warnings**) |
| `028` | `2026-08-13` | `+24 d` | `NISAR_L2_PR_GCOV_028_010_A_176_4005_DHDH_A_20260813T224601_20260813T224635_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.37` | **`100.0%` (`PASS`)** | `-8.02` / `-14.66` | `PASS` (RFI `3.82%`) |
| `029` | `2026-08-25` | `+12 d` | `NISAR_L2_PR_GCOV_029_010_A_176_4005_DHDH_A_20260825T224600_20260825T224635_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.53` | **`100.0%` (`PASS`)** | `-8.05` / `-14.69` | `PASS` (RFI `1.14%`) |
| `030` | `2026-09-06` | `+12 d` | `NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224600_20260906T224635_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.53` | **`100.0%` (`PASS`)** | `-8.05` / `-14.73` | `PASS` (RFI `1.12%`) |
| `031` | `2026-09-18` | `+12 d` | `NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224600_20260918T224635_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.52` | **`100.0%` (`PASS`)** | `-8.31` / `-14.87` | `PASS` (RFI `4.89%`) |
| `032` | `2026-09-30` | `+12 d` | `NISAR_L2_PR_GCOV_032_010_A_176_4005_DHDH_A_20260930T224600_20260930T224634_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.37` | **`100.0%` (`PASS`)** | `-7.62` / `-14.26` | `PASS` (RFI `1.53%`) |
| `033` | `2026-10-12` | `+12 d` | `NISAR_L2_PR_GCOV_033_010_A_176_4005_DHDH_A_20261012T224600_20261012T224634_P05023_N_F_J_001` | **Full (`_N_F_J_`)** | `5.37` | **`100.0%` (`PASS`)** | `-8.02` / `-14.48` | `PASS` (RFI `3.46%`) |

---

## Actual Illumination Validation (Rule 7 Screening Across All `AOI-A2` Stacks)

Applying the Phase 2B.1 actual-illumination rule (`isFullFrame` + 40-vertex `boundingPolygon` + `_LATLON.kml` verification against both the wide `AOI-A2` box and the core OKI peatland corridor `[104.80°E, -3.60°S, 106.00°E, -2.60°S]`) separated true mainland peatland stacks from edge-intersecting neighbors:

| Stack (`Track_Frame`) | Orbit | Scenes | `isFullFrame` | Actual Illuminated Swath BBox | Wide `AOI-A2` Overlap | OKI Core Peatland Overlap | Rule 7 Verdict |
| :--- | :---: | :---: | :---: | :--- | :---: | :---: | :--- |
| **`T119_F090`** | `DESCENDING` | `9` | `True` (`9/9`) | `[103.89°E, -4.40°S, 106.59°E, -1.73°S]` | **`100.00%`** | **`100.00%`** | **APPROVED (`PASS`) — Primary Descending Stack** |
| **`T010_F176`** | `ASCENDING` | `9` | `True` (`9/9`) | `[104.21°E, -4.43°S, 106.91°E, -1.79°S]` | **`99.91%`** | **`100.00%`** | **APPROVED (`PASS`) — Low-RFI Companion Stack** |
| `T018_F090` | `DESCENDING` | `9` | `True` (`9/9`) | `[105.98°E, -4.38°S, 108.67°E, -1.74°S]` | `3.55%` | **`0.00%`** | **REJECTED** — Covers Bangka Island / Karimata Strait (`0%` OKI peatland) |
| `T111_F176` | `ASCENDING` | `9` | `True` (`9/9`) | `[102.12°E, -4.44°S, 104.83°E, -1.79°S]` | `8.18%` | **`0.00%`** | **REJECTED** — Covers Bengkulu / western highlands (`0%` OKI peatland) |
| `T119_F089` | `DESCENDING` | `8` | `7 Full / 1 Partial` | `[104.32°E, -2.42°S, 107.01°E, +0.35°N]` | `0.45%` | **`0.00%`** | **REJECTED** — Covers Jambi province north of OKI (`0%` OKI peatland) |

> [!IMPORTANT]
> Without Rule 7 (Actual Swath Illumination Verification), `T018_F090` (`~4.25 GB`/scene) appeared in Phase 1 Gate A.1 as a promising smaller-file alternative for `AOI-A2`. Polygon-level illumination screening proved that `T018_F090` only touches the eastern coastal fringe of `AOI-A2` (`3.55%`) and misses `100%` of the Ogan Komering Ilir peatland interior. Both `T119_F090` and `T010_F176` cover `100.0%` of the OKI core peatland corridor.

---

## Candidate Temporal Sequences (Ranked)

### Why the 108-Day Span (`2026-07-04 → 2026-10-20`) Is Down-Ranked
A 108-day baseline across tropical Sumatra mixes:
1. Mid-year agricultural harvesting and replanting cycles across canal-drained plantations;
2. Progressive dry-season water-table drawdown in peat domes (July $\to$ September) followed by early October wet-season transition;
3. Multiple distinct fire/burn events and early post-fire herbaceous regrowth.

To isolate acute surface/canopy backscatter transitions while preserving before-and-after verification, **12-day (`1` repeat cycle) and 24-day (`2` repeat cycles) sequences** during the late-August to mid-September peak dry-season window are scientifically superior.

### Ranked Candidate Sequences

| Rank | Stack | Sequence Type | Dates (`T-1 → T0 → T+1` or `T0 → T1`) | Step(s) | Total Size | Radiometric Signature (`_QA_STATS.h5` Scene-Wide Mean) | Scientific Assessment |
| :---: | :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **1 (Primary 3-Scene Sequence)** | `AOI-A2` `T119_F090` (`DESCENDING`) | `T-1 → T0 → T+1` | `2026-08-21 → 2026-09-02 → 2026-09-14` (`Cycles 028 → 029 → 030`) | `12 d` + `12 d` (`24 d` span) | `16.88 GB` (`3` scenes) | `HH`: `-7.96 → -8.02 → -8.03 dB`<br>`HV`: `-13.63 → -13.79 → -14.14 dB` (`-0.51 dB` scene-wide HV drop across 24 d) | **Best Descending 3-Scene Sequence:** Captures peak dry-season cross-pol (`HV`) volume-scattering drop across `100%` of OKI peatlands at exact 12-day intervals. (Can also shift 1 cycle to `2026-09-02 → 2026-09-14 → 2026-09-26`, `16.72 GB`, where `HV` drops `-0.35 dB` then rebounds `+0.55 dB`). |
| **2 (Low-RFI Companion 3-Scene Sequence)** | `AOI-A2` `T010_F176` (`ASCENDING`) | `T-1 → T0 → T+1` | `2026-08-25 → 2026-09-06 → 2026-09-18` (`Cycles 029 → 030 → 031`) | `12 d` + `12 d` (`24 d` span) | `16.58 GB` (`3` scenes) | `HH`: `-8.05 → -8.05 → -8.31 dB` (`-0.26 dB` drop in second 12 d step)<br>`HV`: `-14.69 → -14.73 → -14.87 dB` (`-0.18 dB` drop) | **Best Low-RFI 3-Scene Sequence:** `100%` OKI core coverage with only `1.12%–4.89%` RFI likelihood and a sharp `-0.26 dB` scene-wide `HH` and `-0.14 dB` `HV` shift between `2026-09-06` and `2026-09-18`. |
| **3 (Secondary Mainland Riau 3-Scene Sequence)** | `AOI-A1` `T148_F088` (`DESCENDING`) | `T-1 → T0 → T+1` | `2026-08-11 → 2026-08-23 → 2026-09-04` (`Cycles 027 → 028 → 029`) | `12 d` + `12 d` (`24 d` span) | `16.95 GB` (`3` scenes) | `HH`: `-6.94 → -7.08 → -7.13 dB`<br>`HV`: `-12.56 → -12.71 → -12.75 dB` | **Verified Mainland Riau Full-Frame Stack:** `100.0%` coverage of mainland Riau core (`[101.20°E–102.80°E, 0.20°N–1.80°N]`), replacing the Archipelago-only `T047_F087` stack if a central Sumatra case is desired. |
| **4 (Down-Ranked Seasonal Span)** | `AOI-A2` `T119_F090` (`DESCENDING`) | `T0 → T1` (Long Span) | `2026-07-04 → 2026-10-20` (`Cycles 024 → 033`) | `108 d` | `11.20 GB` (`2` scenes) | `HH`: `-7.65 → -8.14 dB` (`-0.49 dB`)<br>`HV`: `-13.68 → -14.03 dB` (`-0.35 dB`) | **Down-Ranked:** Large cumulative shift, but 108-day interval confounds event attribution with seasonal hydrology and agricultural cycles. |

---

## Recommended Flagship Sequence (`T-1 → T0 → T+1`)

### Primary Recommendation: `AOI-A2` (Ogan Komering Ilir Peatland Corridor, South Sumatra) — Stack `T119_F090` (`DESCENDING`)
- **Why selected:**
  1. Directly matches the proposal's flagship `AOI-A2` (`Track 119, Frame 090`) in South Sumatra's Ogan Komering Ilir (OKI) peatland corridor.
  2. Verified `100.0%` actual SAR swath illumination across both `AOI-A2` and the OKI core peatland corridor in all scenes (`_N_F_J_` full frames).
  3. Exact 12-day repeat intervals (`2026-08-21 → 2026-09-02 → 2026-09-14`, or `2026-09-02 → 2026-09-14 → 2026-09-26`) with identical `CRID = P05023`, `DESCENDING` orbit, `LEFT` look, and `4005_DHDH_A` (`HH+HV`) polarization.
- **3-Scene Event-Bracketing Triplet (`~16.88 GB` total):**
  - **`T-1` (`2026-08-21`, Pre-Shift Dry-Season Baseline):**  
    `NISAR_L2_PR_GCOV_028_119_D_090_4005_DHDH_A_20260821T111855_20260821T111930_P05023_N_F_J_001` (`5.68 GB`)
  - **`T0` (`2026-09-02`, `+12 d`, Early September Transition):**  
    `NISAR_L2_PR_GCOV_029_119_D_090_4005_DHDH_A_20260902T111855_20260902T111930_P05023_N_F_J_001` (`5.68 GB`)
  - **`T+1` (`2026-09-14`, `+12 d`, Peak Dry-Season Observation — Scene-Wide Mean `HV` Drop to `-14.14 dB`):**  
    `NISAR_L2_PR_GCOV_030_119_D_090_4005_DHDH_A_20260914T111855_20260914T111929_P05023_N_F_J_001` (`5.52 GB`)
  - *(Optional `T+2` Follow-Up `2026-09-26`, `+12 d`: `NISAR_L2_PR_GCOV_031_119_D_090_4005_DHDH_A_20260926T111855_20260926T111929_P05023_N_F_J_001`, `5.52 GB`)*

---

## Recommended Minimal Demo Pair (`2` Scenes Only — Lowest Transfer Cost)

If bandwidth or storage budgets favor downloading **only 2 scenes (`~11.05–11.20 GB`)** before evaluating whether a 3rd scene is needed:

### Option M1 (Primary Stack `T119_F090`, `DESCENDING`, 12-Day or 24-Day Pair, `11.20 GB`):
- **12-Day Pair (`2026-09-02 → 2026-09-14`, `11.20 GB`):**
  - `T0`: `NISAR_L2_PR_GCOV_029_119_D_090_4005_DHDH_A_20260902T111855_20260902T111930_P05023_N_F_J_001` (`5.68 GB`)
  - `T1`: `NISAR_L2_PR_GCOV_030_119_D_090_4005_DHDH_A_20260914T111855_20260914T111929_P05023_N_F_J_001` (`5.52 GB`)
  - *Why:* Captures the steepest 12-day cross-polarization (`HV`) decrease (`-13.79 dB → -14.14 dB`, $\Delta = -0.35\text{ dB}$ across the entire `60,000 km²` frame) during peak September dry-season conditions.
- *(Alternative 24-Day Pair on `T119_F090`, `2026-08-21 → 2026-09-14`, `11.20 GB`: `028_119_D_090` $\to$ `030_119_D_090`, capturing the full `-0.51 dB` `HV` and `-0.07 dB` `HH` shift across 24 days using only 2 granules).*

### Option M2 (Low-RFI Companion Stack `T010_F176`, `ASCENDING`, 12-Day Pair, `11.05 GB`):
- **12-Day Pair (`2026-09-06 → 2026-09-18`, `11.05 GB`):**
  - `T0`: `NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224600_20260906T224635_P05023_N_F_J_001` (`5.53 GB`, RFI `1.12%`)
  - `T1`: `NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224600_20260918T224635_P05023_N_F_J_001` (`5.52 GB`, RFI `4.89%`)
  - *Why:* Covers `100.0%` of the exact same OKI core peatland corridor (`2026-09-06 → 2026-09-18`), shows a strong `-0.26 dB` scene-wide `HH` drop and `-0.14 dB` `HV` drop over 12 days, and has ~3–10× lower RFI than `T119_F090`.

---

## Backup Cases

### Backup Case 1: `AOI-B1` — Northern California Wildfire Corridor (`T143_F068`, `DESCENDING`)
- **Geometry:** `DESCENDING` | **Look Direction:** `LEFT` | **Mode:** `2005_DHDH_A` (`HH+HV`) | **CRID:** `P05023`
- **Actual Illuminated Swath:** `[124.22°W–121.05°W, 39.21°N–41.93°N]` (`~62,150 km²`, covering **`100.0%` of `AOI-B1`** across the Shasta-Trinity / Mendocino / Northern Sacramento Valley corridor).
- **12-Day Event-Bracketing Triplet (`2026-08-23 → 2026-09-04 → 2026-09-16`, `~11.96 GB` total across 3 scenes — smaller `~3.93–4.10 GB` granules!):**
  - `T-1` (`2026-08-23`): `NISAR_L2_PR_GCOV_028_143_D_068_2005_DHDH_A_20260823T020829_20260823T020903_P05023_N_F_J_001` (`3.93 GB`, `HH = -6.94 dB`, `HV = -12.42 dB`)
  - `T0` (`2026-09-04`, `+12 d`): `NISAR_L2_PR_GCOV_029_143_D_068_2005_DHDH_A_20260904T020828_20260904T020903_P05023_N_F_J_001` (`4.10 GB`, `HH = -4.87 dB`, `HV = -10.91 dB` — **a `+2.07 dB HH` / `+1.50 dB HV` radiometric jump**)
  - `T+1` (`2026-09-16`, `+12 d`): `NISAR_L2_PR_GCOV_030_143_D_068_2005_DHDH_A_20260916T020828_20260916T020902_P05023_N_F_J_001` (`3.93 GB`, `HH = -6.76 dB`, `HV = -12.52 dB`)
- **Role:** Ready as an immediate North American wildfire/land-disturbance backup if tropical L-band peatland signatures in `AOI-A2` prove spatially diffuse or RFI-impacted.

### Backup Case 2: `AOI-A1` — Mainland Riau Peatland Corridor (`T148_F088`, `DESCENDING`)
- **Geometry:** `DESCENDING` | **Look Direction:** `LEFT` | **Mode:** `4005_DHDH_A` (`HH+HV`) | **CRID:** `P05023`
- **Actual Illuminated Swath:** `[100.38°E–103.05°E, -0.37°S–+2.28°N]` (`~60,035 km²`, covering **`100.0%` of the Mainland Riau core `[101.20°E–102.80°E, 0.20°N–1.80°N]`** — Bengkalis, Siak, Pelalawan, and Rokan Hilir).
- **12-Day Triplet (`2026-08-11 → 2026-08-23 → 2026-09-04`):** `027_148_D_088` (`5.60 GB`) $\to$ `028_148_D_088` (`5.75 GB`) $\to$ `029_148_D_088` (`5.60 GB`).

---

## External Context (`Phase 2B.4` — Strictly Modular Contextual Layer)

In strict compliance with [`SCIENCE_CONTRACT.md`](file:///D:/NASA/SAR2Action/SCIENCE_CONTRACT.md) and Section `2B.4`:
1. **No Wildfire Classifier or Automatic Cause Attribution:** The `sar/change/` engine computes pure L-band radar backscatter changes ($\Delta\text{HH}$, $\Delta\text{HV}$, $|\Delta\text{HH}|$, $|\Delta\text{HV}|$, and `Combined Radar Change`) from NISAR GCOV observations. It does **not** label pixels as "burned" or "fire".
2. **Modular External Context:** When a flagship pair (`T119_F090` or `T010_F176`) is promoted for full download, optional external context layers (such as NASA FIRMS VIIRS/MODIS active thermal anomalies within the `2026-08-21 → 2026-09-18` window over Ogan Komering Ilir `[104.80°E–106.00°E, -3.60°S–-2.60°S]`, optical smoke/cloud cover context, or known peat-canal hydrology polygons) will be attached solely via the `external_context` array of `EvidenceRecord` (`ContextAttachment`) to help human analysts locate candidate AOI windows and interpret co-located radar changes with explicit uncertainty.

---

## Remaining Risks

1. **Large Full-Frame Granule Size (`~5.52–5.68 GB` per scene in Sumatra):**
   - Unlike the partial-frame `T047_F087` engineering scenes (`~1.03 GB` each), full-frame Sumatra granules are `~5.5 GB` each (`~11.05–11.20 GB` for a minimal 2-scene pair, `~16.6–16.9 GB` for a 3-scene triplet).
   - **Mitigation:** Start by downloading the **2-scene Minimal Demo Pair (`~11.05–11.20 GB`)** first, run the Phase 2A windowed change engine (`sar/change/`) on targeted OKI peatland sub-windows (`~2.5 s` runtime, `<100 MiB` array memory), and only download the 3rd scene (`T-1` or `T+1`) after verifying strong localized $\Delta\text{HH}$ / $\Delta\text{HV}$ signatures.
2. **Moderate L-Band RFI in Descending `T119_F090` (`11.1%–17.2%` RFI likelihood in `_QA_SUMMARY.csv`):**
   - **Mitigation:** If localized RFI bands degrade the OKI target window in `T119_F090`, switch immediately to the validated low-RFI Ascending companion stack **`T010_F176` (`2026-09-06 → 2026-09-18`, RFI `1.12%–4.89%`)**, which covers `100.0%` of the exact same OKI core peatland corridor.
3. **Provisional Maturity (`NISAR_L2_GCOV_PROVISIONAL_V1`, `CRID = P05023`):**
   - **Mitigation:** Every `EvidenceRecord` generated by `sar/change/` automatically includes `Provisional NISAR L2 GCOV product (CRID P05023); calibration and geolocation are not yet at final operational maturity` in its `limitations` list.
