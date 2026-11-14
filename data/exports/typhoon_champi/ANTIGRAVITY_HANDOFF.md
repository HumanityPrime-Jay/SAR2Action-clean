# CHAMPI real-data Agent V3 handoff

For the completed five-field OPERA VH investigation, see `docs/VH_AGENT_HANDOFF.md` and
`data/exports/yunlin_vh_2025_2026/field_investigation.json`. The API now also returns
`field_comparison` and `temporal_changes` while preserving the existing response fields.
The 2026-10-22 UTC OPERA scene is **2026-10-23 05:51 Taiwan**, inside the CWA land-warning
window. A strictly pre-warning VH change is unavailable because only one 2026 scene
precedes that warning. Five-field differences remain descriptive; crop damage is UNKNOWN.

## Ready API

- `POST /api/agent/investigate-v3`
- `GET /api/agent/champi/evidence/{evidence_id}`
- Request: `{"case_id":"CHAMPI-YUNLIN-TAIXI","aoi_id":"10009160","field_id":"YL-CAND-01","question":"Did agricultural radar observations in Taixi change after Typhoon Champi, and how does the 2026 VH series compare with 2025?","agent_mode":"deterministic"}`
- Set `agent_mode` to `gemini` only when `GEMINI_API_KEY` is available to the backend process. Gemini selects bounded tools and proposes hypotheses; deterministic code verifies evidence and assigns statuses.
- Response contract: `backend/app/schemas/investigation_v3.py`; implementation: `backend/app/services/investigation_v3.py`.
- Response fields: `case_id`, `aoi_id`, `investigation_id`, `question`, `data_mode`, `observation_timeline`, `observation_statistics`, `vh_timeseries`, `vh_comparison`, `available_sensors`, `observed_changes`, `hypotheses`, `hypothesis_tests`, `evidence_ids`, `scientific_limitations`, `missing_evidence`, `recommended_next_action`, `provenance_status`, `tool_trace`, `qa`, `official_loss_context`, and `expert_report`.
- Verified live Gemini example: `demo_response.json`; inspect actual execution events in `agent_trace.json`.

## Evidence and data mode

`REAL_NISAR_SEPARATE_AND_OPERA_VH_OBSERVED` means actual NISAR gamma0 pixels exist for both sides of the event **and** an independent, real OPERA Sentinel-1 VH series exists for five farmland candidates. No verified NISAR inter-date radiometric difference is reported. October 16 NISAR is provisional P05023; October 28 is validated P05036. NASA/ASF warns that processing differences may affect cross-maturity analysis. `science_qa.json` records the gate. The two date-specific HH/HV GeoTIFFs and preview PNGs are **separate observations**, never a typhoon damage layer.

The primary AOI is the official NLSC **Taixi Township administrative boundary**, not field polygons. The MOA's NT$157,743,000 refers to **Yunlin County**. Neither it nor the NISAR pixels label any Taixi parcel. The NISAR post scene covers 110,287 valid township pixels (63.44% of the township grid cells); the pre scene covers 173,852. Mask 0 accounts for 63,565 post pixels. The preview is single-date HH gamma0 dB color stretched around −10 dB; gray is excluded.

The OPERA ASF search found 33 real 2025 and 20 real 2026 scenes; six Sentinel-1C descending orbit 105 / burst `105-224320-IW3` / v1.0 scenes were downloaded for VH. Five official Ministry of Agriculture farmland polygons yielded 30 field-scene observations, all passing the >=8 interior-valid-pixel and >=80% coverage checks. OPERA linear gamma0 was converted per pixel with `10*log10(power)`; the output mean is an arithmetic mean of pixel dB values. These are **farmland candidates, not verified rice paddies or damage labels**. NISAR L-band HH/HV cannot be directly subtracted from Sentinel-1 C-band VH.

## Files to consume

| File | Use |
| --- | --- |
| `candidate_aois.geojson` | Official Mailiao, Taixi, Yuanchang administrative boundaries |
| `aoi_selection.json` | Bounded Taixi selection rationale |
| `scene_inventory.json` | NASA CMR discovery including exact scene IDs and acquisitions |
| `sentinel_catalog_inventory.json` | Bounded Copernicus catalog search; metadata only |
| `../yunlin_vh_2025_2026/scene_inventory.csv`, `field_candidates.geojson` | OPERA inventory and official farmland candidate polygons |
| `../yunlin_vh_2025_2026/vh_timeseries.csv`, `vh_timeseries.json`, `vh_comparison.png` | Real 2025/2026 OPERA VH observations and plot |
| `../yunlin_vh_2025_2026/agent_evidence.json`, `scientific_qa.json`, `source_manifest.json` | VH Evidence, pixel QA, and provenance |
| `Taixi_PRE_HH_HV_db.tif`, `Taixi_POST_HH_HV_db.tif` | Separate real NISAR HH/HV gamma0 dB rasters |
| `Taixi_PRE_HH_preview.png`, `Taixi_POST_HH_preview.png` | Separate date-specific quicklooks |
| `science_qa.json`, `science_manifest.json` | Pixel QA, processing caveat, source hashes |
| `official_loss_record.json` | Official MOA county/regional loss figures and scope |
| `evidence.json` | Evidence IDs, sources, numerical observation records |
| `investigation_report.json`, `agent_trace.json` | Structured report and actual run events |
| `manifest.json`, `benchmark_results.json` | Demonstration integrity and guard checks |

Do not render a NISAR change heat map, confirmed parcel damage, percentage crop loss, relief eligibility, or cross-sensor difference from these files. `observed_changes` now contains a **descriptive OPERA VH** pre/post statistic with causal status `UNKNOWN`. Use `observation_statistics.PRE` and `.POST` for separate NISAR values and `vh_timeseries` for real Sentinel-1 dates. The recommended next action is crop/harvest records, geolocated field verification, and reprocessed same-CRID pre-event GCOV when available.

## Provenance

- [MOA official loss report](https://www.moa.gov.tw/theme_data.php?id=10320&sub_theme=agri&theme=news)
- [CWA CHAMPI event record](https://rdc28.cwa.gov.tw/TDB/public/typhoon_detail?typhoon_id=202629)
- [NLSC official township boundary download](https://maps.nlsc.gov.tw/pro/download.jsp)
- [NASA/ASF NISAR P05036 release notes](https://hyp3-docs.asf.alaska.edu/nisar-docs/release-notes/)

## Verification and remaining gaps

The OPERA pipeline completed locally; the Colab notebook is prepared but has not been run in Colab. The agent executes the actual VH retrieval, timing, seasonal comparison, alternative explanation, and missing-evidence tools. Fifteen deterministic V3 science checks passed. In one live Gemini V3 run for the 2025/2026 VH question, Gemini selected the timing, field-series, and seasonal-comparison tools; the trace records their execution, and its proposed storm-disturbance hypothesis remains unresolved. This is not an end-to-end accuracy score. There are no verified crop labels, no cross-CRID NISAR equivalence, and no township-specific official loss amount. See `docs/VH_COLAB_EXECUTION.md` for the exact Colab steps and separately labeled Earth Engine fallback.
