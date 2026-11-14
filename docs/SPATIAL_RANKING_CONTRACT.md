# Spatial change ranking handoff — B → D

## Current availability

No readable per-pixel change GeoTIFF is present in this checkout. The files under `data/processed/phase2c_flagship` are masks and JSON summaries; the JSON names change rasters that are absent here. Metadata-only GCOV QA sidecars are present under `data/raw/sidecars` but cannot replace observation pixels. Thus the root app only runs spatial ranking in **explicit Synthetic Demo mode** until B supplies the rasters below.

## Live input contract

Set `SAR2ACTION_SPATIAL_MANIFEST` to an absolute path to a JSON manifest. The GeoTIFF paths in it are relative to the manifest directory and may not escape that directory. Do not set it for a synthetic file.

```json
{
  "schema_version": "1",
  "data_kind": "nisar",
  "case_id": "<existing case ID>",
  "polarization": "HV",
  "scene_ids": ["<actual T0 scene ID>", "<actual T1 scene ID>"],
  "observation_times": ["<actual UTC T0>", "<actual UTC T1>"],
  "parent_evidence_id": "<existing E-... evidence record>",
  "method": "<B validated dB comparison method/version>",
  "scene_versions": ["<T0 CRID or product version>", "<T1 CRID or product version>"],
  "pixel_resolution_deg": [0.0001, 0.0001],
  "source_backscatter_unit": "linear_power",
  "change_unit": "dB",
  "conversion_formula": "10*log10(P)",
  "change_geotiff": "delta_hv_db.tif",
  "valid_mask_geotiff": "common_valid_mask.tif",
  "change_sha256": "<SHA-256 of change GeoTIFF bytes>",
  "valid_mask_sha256": "<SHA-256 of mask GeoTIFF bytes>"
}
```

`change_geotiff` is one band of **signed** `B(T1,p) - B(T0,p)` in dB. B must convert positive GCOV diagonal linear power with `10 log10(P)` before differencing. The mask has nonzero values only where both observations are scientifically comparable. Both rasters must be single-band, co-registered, same shape/transform, north-up EPSG:4326. Their pixel values must be finite where the mask is valid. D does not silently reproject, align, replace nodata, or infer polarization.

The Phase 5 extension makes method/version, scene versions, declared pixel resolution and units mandatory. If B supplies already calibrated dB source rasters, use `source_backscatter_unit: "dB"` and `conversion_formula: "none"`; do not apply `log10` twice. `change_unit` must remain `dB`. The validator compares declared spacing with the GeoTIFF transform and checks scene CRIDs against parent Evidence when available. These declarations alone do not prove external NASA provenance; parent Evidence and B/A approval remain necessary.

The manifest must include SHA-256 hashes of both GeoTIFF files. D verifies them before reading data, so a changed raster invalidates its manifest and derived evidence IDs. This integrity check does not replace A/B scientific approval or establish the external origin of a file.

Derived spatial Evidence IDs bind the source GeoTIFF and mask hashes, parent Evidence ID, scene IDs and versions, AOI, polarization, method and region measurements. A new source file changes the Evidence ID even when a region's rounded summary happens to remain the same. Cross-AOI, cross-version or cross-source region comparison is refused. Valid-mask pixels explicitly exclude the mask GeoTIFF's declared NoData value, including a nonzero sentinel.

The parent evidence must already exist in the root Evidence Ledger and have matching scene IDs, polarization, UTC timestamps, valid pixels, and `COMPARABLE` or `LIMITED` quality. A must approve pair comparability, calibration, masking, AOI selection and interpretation. The live ranking API refuses missing or mismatched inputs without a synthetic fallback.

## API and ranking method

`POST /api/agent/spatial/rank` accepts:

```json
{"case_id":"<case>","aoi_bbox_wgs84":[105.28,-3.28,105.48,-3.08],"polarization":"HV","mode":"live","limit":3,"min_pixels":6,"min_area_km2":0.001,"threshold_db":2.0,"min_valid_fraction":0.5}
```

`mode:"fixture"` deliberately generates synthetic, georeferenced test arrays inside the requested WGS84 AOI and returns `SIMULATED DATA — NOT NASA OBSERVATIONS`. The fixture contains three contiguous patches and one isolated extreme pixel to test the area gate.

The algorithm intersects the valid mask with `|Δ| >= threshold_db`, finds four-neighbour connected components, excludes components below pixel, WGS84 geodesic area and minimum valid bounding-box coverage thresholds, and ranks by median `|Δ| × valid bbox coverage × log(1 + connected pixel count)`. This is a **descriptive radar-change ranking**, not a hazard or fire-severity score. Area sums WGS84 geodesic pixel areas by occupied row; the returned value is rounded to four decimal places.

Each region has a stable ID, WGS84 bounding box and GeoJSON bounding rectangle, pixel count, geodesic area, valid coverage, median signed and absolute dB change, scene/date/polarization provenance, quality status, Evidence ID and limitations. The rectangle is an extent of a connected component, not a pixel-exact boundary; different component extents can overlap although their pixels are disjoint. `GET /api/agent/spatial/evidence/{id}` returns the derived record; `POST /api/agent/spatial/compare` compares two registered and compatible regions. The agent can focus a verified region with an allowlisted `map.focus_bbox` action. The map never evaluates model-supplied code.

## Local verification

```powershell
cd D:\SAR2Action
.\venv\Scripts\python.exe -m pytest tests\agent\test_spatial_ranking.py -q
```

For a normal Windows host with local HTTP enabled, run the backend and frontend commands in `docs/AGENT_IMPLEMENTATION_REPORT.md`, select **Synthetic Demo** in the investigator, and ask for the top three change regions. Do not call those values NISAR measurements.
