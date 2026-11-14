# Flagship External Event Context — South Sumatra / Ogan Komering Ilir (September 2026)

**Document ID:** `FLAGSHIP_EVENT_CONTEXT.md`  
**Phase:** `Phase 2C.1 & Phase 3C.4 / 3C.6 — Authoritative Event Anchoring & Predefined AOI Registry`  
**Last Updated:** `2026-10-24`  

> [!IMPORTANT]
> **Strict Epistemic Boundary (`SCIENCE_CONTRACT.md` Rule 5):**  
> External event context documented in this file may justify **only**:
> 1. **AOI selection** (which administrative/geographic sub-regions of Ogan Komering Ilir to inspect),
> 2. **Time-window selection** (why early-to-mid September 2026 is a relevant multi-temporal comparison interval), and
> 3. **Contextual narrative** (independent situational background).
>
> External event context **may NEVER** convert a NISAR L-band radar-change pixel into:
> - confirmed fire damage,
> - burn severity,
> - underground peat fire detection, or
> - causal wildfire attribution.

---

## 1. Supported 2026 Event Window & Geographic Focus

| Field | Documented Context |
| :--- | :--- |
| **Region / Regency** | **Ogan Komering Ilir (OKI) Regency**, South Sumatra Province (*Sumatera Selatan*), Indonesia |
| **Core Peatland Corridor (`AOI-A2` Core)** | `[104.80°E, -3.60°S, 106.00°E, -2.60°S]` (`~14,800 km²` covering the eastern OKI peat domes, conservation reserves, and canal-drained wetlands) |
| **Primary Documented Sub-Districts & Reserves** | **Tulung Selapan**, **Cengal**, **Pangkalan Lampam**, **Pedamaran / Pedamaran Timur**, **Tanjung Lubuk**, and **Padang Sugihan / Suaka Margasatwa Padang Sugihan** |
| **Supported Event Escalation Window** | **Early-to-Late September 2026** (specifically escalating across **`2026-09-05` through `2026-09-30`**, with major BMKG hotspot/smoke advisories around **`2026-09-10`** and BNPB/Menko Polkam field evaluations in South Sumatra/OKI around **`2026-09-17`**) |
| **Overlap with NISAR Illumination** | **`100.00%` inside the OKI Core Peatland Corridor (`[104.80°E, -3.60°S, 106.00°E, -2.60°S]`)**, which is `100.00%` illuminated by both Candidate F2 (`T010_F176 ASCENDING`, `2026-09-06 → 2026-09-18`) and Candidate F1 (`T119_F090 DESCENDING`, `2026-09-02 → 2026-09-14`) |

---

## 2. Authoritative Source-Level Provenance Matrix (`Phase 3C.4`)

Each external source is recorded below with explicit separation between what it supports and what it does **not** support:

| Source ID | Organization | Publication Date | Observation / Event Date | Geographic Specificity | What It Supports | What It Does NOT Support | Source URL |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`SRC-BMKG-01`** | **BMKG — Stasiun Klimatologi Sumatera Selatan** (Meteorology, Climatology, and Geophysical Agency) | `~2026-09-10` (September 2026 Peak Dry-Season Bulletin) | Early–Mid September 2026 (`2026-09-01` to `2026-09-15`) | Provincial (`Sumatera Selatan`) and Regency-level hotspot concentration (`Ogan Komering Ilir`, `Musi Banyuasin`, `Banyuasin`) + southeast-to-northwest smoke transport toward Palembang | Supports that early-to-mid September 2026 was a peak dry-season drought phase in South Sumatra with surging high-confidence thermal hotspots, extreme consecutive rainless days, and visible smoke plumes originating from eastern peatland districts including OKI. | Does **not** provide 10 m pixel burn perimeters; does **not** prove that any specific NISAR L-band backscatter change pixel (`ΔHH` or `ΔHV`) was caused by fire rather than soil drying, vegetation management, or speckle. | `https://staklim-sumsel.bmkg.go.id/hotspot-sumsel-kembali-meningkat-bmkg-sampaikan-perkembangan-kondisi-iklim-di-tengah-puncak-kemarau/` |
| **`SRC-BMKG-02`** | **BMKG Pusat** (Indonesian Agency for Meteorology, Climatology, and Geophysics) | `September 2026` | September 2026 | National & South Sumatra peatland ecosystems (`Ekosistem Gambut Sumatera Selatan`) | Supports that BMKG coordinated peatland water-table/climate monitoring and Weather Modification Operations (*Operasi Modifikasi Cuaca* / OMC) to wet dried peatlands in South Sumatra during September 2026. | Does **not** provide pixel-level ground truth of burned area or underground peat combustion depth. | `https://www.bmkg.go.id/berita/utama/bmkg-dukung-penguatan-penanganan-karhutla-dan-pengelolaan-ekosistem-gambut` |
| **`SRC-BNPB-01`** | **BNPB** (National Agency for Disaster Countermeasure) | `2026-09-05` | `2026-09-01` to `2026-09-05` | Provincial & Regency level (`Sumatera Selatan`, including `Ogan Komering Ilir`) | Supports that active *karhutla* events and joint ground/aerial suppression operations were already underway in South Sumatra at the start of the `2026-09-06 → 2026-09-18` NISAR observation window (`T0 = 2026-09-06`). | Does **not** establish whether `T0` (`2026-09-06`) at any given 10 m pixel is strictly pre-fire or already affected by early-September drying/burning. | `https://www.bnpb.go.id/index.php/berita/perkembangan-situasi-dan-penanganan-karhutla-di-sejumlah-wilayah-indonesia-5-september-2026` |
| **`SRC-BNPB-02`** | **BNPB & Kemenko Polkam** (reported via *Aktual* / *JavaSatu* official press briefings in Palembang) | `~2026-09-17` | Mid-September 2026 (`2026-09-10` to `2026-09-18`) | Regency level (`Ogan Komering Ilir`, `Musi Banyuasin`, `Banyuasin`, `Muara Enim`, `Ogan Ilir`) | Supports that by mid-September 2026 (`~2026-09-17`, immediately prior to `T1 = 2026-09-18`), hotspot activity in South Sumatra (led by OKI) prompted direct field evaluation by BNPB Chief Lt. Gen. Suharyanto and Menko Polkam, deploying `12,285` joint personnel and `7` water-bombing/patrol helicopters. | Does **not** provide polygon boundaries for individual fires or validate radar dB change as burn severity. | `https://aktual.com/1-737-hotspot-karhutla-terdeteksi-di-sumsel-12-285-personel-dan-7-helikopter-dikerahkan-16-perusahaan-diselidiki/` |
| **`SRC-ANTARA-01`** | **ANTARA News / Polda Sumatera Selatan & BPBD** | `September 2026` | September 2026 | Sub-district / Reserve level: **Padang Sugihan (`Suaka Margasatwa Padang Sugihan`), Ogan Komering Ilir** | Supports that peatland fires and smoke occurred in the **Padang Sugihan** area of OKI, where `300` joint personnel were deployed to suppress peatland fires and prevent smoke transport toward Palembang. | Does **not** provide exact 10 m coordinates of individual fire fronts inside Padang Sugihan. | `https://www.antaranews.com/berita/5805659/polda-sumsel-siapkan-300-personel-padamkan-karhutla-di-padang-sugihan` |
| **`SRC-BPBD-01`** | **Pusdalops BPBD Sumatera Selatan** (reported via *Kompas Regional*) | `2026-09-30` | `2026-09-01` to `2026-09-30` | Regency & Sub-district level: **Ogan Komering Ilir (`1,375` of `3,026` hotspots)**, including `Tulung Selapan`, `Cengal`, `Pangkalan Lampam`, `Pedamaran` | Confirms that OKI accounted for the largest share of hotspots in South Sumatra (`45.4%` of provincial total on peak days) and that cumulative September 2026 hotspots in South Sumatra reached `32,789`. | Does **not** attribute any specific radar backscatter shift between `2026-09-06` and `2026-09-18` to fire without independent pixel-level validation. | `https://regional.kompas.com/read/2026/09/30/112830678/lonjakan-drastis-titik-api-hingga-3026-hotspot-terdeteksi-di-enam-wilayah` |

---

## 3. Predefined vs. Exploratory AOI Provenance Registry (`Phase 3C.5 & 3C.6`)

To prevent post-hoc "cherry-picking" bias (selecting regions with large radar changes and retrospectively claiming they prove wildfire detection), every AOI in SAR2Action carries explicit provenance metadata (`selection_method`, `selection_time`, `selection_basis`):

### 3.1 Predefined Event-Context AOI (`PREDEFINED_EXTERNAL_CONTEXT` — Defined Prior to Radar Inspection)

- **AOI ID:** **`AOI-OKI-04`** (`default_evidence_id = E-FLAGSHIP-OKI-004`)
- **Name:** `AOI-OKI-04 — Padang Sugihan Peatland Reserve & Buffer Corridor (Predefined External-Context AOI)`
- **WGS84 Bounding Box:** **`[105.08°E, -2.92°S, 105.24°E, -2.76°S]`** (`~17.8 km × 17.7 km`)
- **`selection_method`:** `"PREDEFINED_EXTERNAL_CONTEXT"`
- **`selection_time`:** `"2026-10-24T01:55:00+08:00 (PRE_ANALYSIS — recorded prior to inspecting radar change statistics)"`
- **`selection_basis`:** Defined strictly from the geographic location of the southern *Suaka Margasatwa Padang Sugihan* (Padang Sugihan Wildlife Reserve) and adjacent Sebokor/Air Sugihan peat-canal boundary in northern Ogan Komering Ilir, independently identified in `SRC-ANTARA-01` and `SRC-BMKG-01` as a September 2026 peat-fire suppression and smoke source zone. Recorded here **before** running `sar/change/` over `[105.08, -2.92, 105.24, -2.76]`.
- **Explicit Spatial Limitation:** Because `SRC-ANTARA-01` and `SRC-BMKG-01` identify the Padang Sugihan reserve/sub-district administratively rather than publishing a meter-scale burn polygon, `AOI-OKI-04` is an administrative/reserve-scale bounding box (`~315 km²`) and is **not** a ground-truth fire perimeter.

### 3.2 Predefined Sub-District Geographic AOIs (`PREDEFINED_GEOGRAPHIC_AOI`)

Defined across the three principal eastern OKI peatland sub-district corridors (`Tulung Selapan`, `Cengal`, `Pangkalan Lampam / Pedamaran`) at regular `0.18°–0.20°` (`18–22 km`) sub-district scale:

| AOI ID | Evidence ID | WGS84 Bounding Box | `selection_method` | `selection_time` | `selection_basis` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`AOI-OKI-01`** | `E-FLAGSHIP-OKI-001` | `[105.28, -3.28, 105.48, -3.08]` | `PREDEFINED_GEOGRAPHIC_AOI` | `PRE_ANALYSIS` | Regional `20 km × 20 km` sub-district window spanning the Tulung Selapan – Cengal drained peat dome corridor in OKI (`SRC-BPBD-01`). |
| **`AOI-OKI-02`** | `E-FLAGSHIP-OKI-002` | `[104.98, -3.32, 105.16, -3.14]` | `PREDEFINED_GEOGRAPHIC_AOI` | `PRE_ANALYSIS` | Regional `18 km × 18 km` sub-district window spanning the Pangkalan Lampam – Pedamaran Timur peatland belt in OKI (`SRC-BPBD-01`). |
| **`AOI-OKI-03`** | `E-FLAGSHIP-OKI-003` | `[105.55, -3.42, 105.73, -3.24]` | `PREDEFINED_GEOGRAPHIC_AOI` | `PRE_ANALYSIS` | Regional `18 km × 18 km` sub-district window spanning the eastern Cengal coastal peat corridor in OKI (`SRC-BPBD-01`). |

### 3.3 Exploratory Post-Hoc Radar-Change Sub-Patches (`EXPLORATORY_POST_HOC_RADAR_CHANGE`)

- Any localized `2 km × 2 km` (`200 × 200 px`) high-change sub-patches identified by scanning the computed change rasters inside `AOI-OKI-01..03` are strictly classified as:
  - **`selection_method`:** `"EXPLORATORY_POST_HOC_RADAR_CHANGE"`
  - **`selection_time`:** `"POST_HOC_INSPECTION"`
  - **`selection_basis`:** `"Exploratory post-hoc window selected by scanning for maximum median Combined Radar Change after computing the radar change raster; serves only to illustrate localized spatial heterogeneity for investigation and is NEVER treated as confirmatory wildfire evidence."`
