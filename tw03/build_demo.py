"""Build and verify the pinned TW-03 NISAR demo from the two local ASF granules."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import h5py
import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from backend.app.schemas.evidence import EvidenceRecord, PolarizationChannel
from backend.app.services.layer_renderer import build_legend_for_layer, render_layer_rgba
from sar.change.masks import MASK_RULE_SPECIFICATION
from sar.change.reader import read_gcov_grid_and_metadata, read_gcov_window, run_in_memory_change_analysis
from sar.change.windows import aoi_to_window, verify_grids_compatible

SCENES = (
    ("G4343404696-ASF", "NISAR_L2_PR_GCOV_032_061_D_076_2005_DHDH_A_20261004T103752_20261004T103826_P05023_N_F_J_001"),
    ("G4374517324-ASF", "NISAR_L2_PR_GCOV_033_061_D_076_2005_DHDH_A_20261016T103752_20261016T103826_P05023_N_F_J_001"),
)
SOURCE = "https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1"
AOI = ROOT.parent / "tw01/taiwan-agricultural-demo-v1/aoi.geojson"
OUT = ROOT / "nisar-demo-v1"
SIZE = 1_535_115_264
CASE = "TW03-YUNLIN"
LIMITS = [
    "Both acquisitions predate the 2026-10-23/24 typhoon impact window in Taiwan.",
    "Backscatter change alone does not establish cause, crop damage, yield loss or monetary loss.",
    "Both NISAR GCOV products are Provisional P05023.",
    "NISAR HH/HV and Sentinel-1 VV/VH are independent observations; no cross-sensor difference was computed.",
    "QA RFI likelihood is not used as a cross-scene quantitative quality score.",
]


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_inputs(geometry):
    paths, records, windows = [], [], []
    expected = {
        "track_number": 61, "frame_number": 76, "crid": "P05023",
        "product_version": "1.0.11", "data_maturity": "PROVISIONAL", "is_full_frame": True,
    }
    for granule, scene in SCENES:
        p = ROOT / "inputs" / f"{scene}.h5"
        require(p.is_file() and p.stat().st_size == SIZE and h5py.is_hdf5(p), f"Incomplete HDF5: {scene}")
        paths.append(p)
        records.append({"scene_id": scene, "granule_id": granule, "bytes": SIZE,
                        "sha256": sha(p), "url": f"{SOURCE}/{scene}/{scene}.h5",
                        "metadata_url": f"https://cmr.earthdata.nasa.gov/search/concepts/{granule}.umm_json"})
    grids, metadata = zip(*(read_gcov_grid_and_metadata(p) for p in paths), strict=True)
    verify_grids_compatible(*grids)
    window = aoi_to_window(geometry, grids[0])
    require(not window.fully_outside_grid and not window.partly_outside_grid, "AOI leaves the common grid.")
    for p, record, grid, meta in zip(paths, records, grids, metadata, strict=True):
        require(meta["scene_id"] == record["scene_id"], "HDF5 scene identity differs from the requested scene.")
        require(all(meta[k] == v for k, v in expected.items()), "HDF5 product metadata differs from the pinned pair.")
        require(meta["orbit_pass_direction"].lower() == "descending" and meta["look_direction"].lower() == "left",
                "Scene orbit pass or look direction differs.")
        require(set(meta["available_polarizations"]) >= {"HH", "HV"}, "HH/HV not available in frequencyA.")
        with h5py.File(p, "r") as h:
            group = h["/science/LSAR/GCOV/grids/frequencyA"]
            for key in ("mask", "HHHH", "HVHV"):
                require(group[key].shape == (grid.height, grid.width), f"Grid shape mismatch in {key}.")
            require(group["mask"].dtype == np.uint8, "Unexpected GCOV mask dtype.")
        samples = read_gcov_window(p, geometry, precomputed_grid=grid, precomputed_meta=meta, precomputed_window=window)
        windows.append(samples)
        record.update(expected)
        record.update({k: meta[k] for k in ("acquisition_start_utc", "acquisition_end_utc", "orbit_pass_direction", "look_direction", "frequency_group")})
        record["polarizations"] = ["HH", "HV"]
    return records, windows


def overlay(tif, output, pol, evidence_id):
    with rasterio.open(tif) as src:
        transform, width, height = calculate_default_transform(src.crs, "EPSG:3857", src.width, src.height, *src.bounds)
        data = np.full((height, width), np.nan, dtype=np.float32)
        reproject(rasterio.band(src, 1), data,
                  dst_transform=transform, dst_crs="EPSG:3857",
                  src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.nearest)
    layer_type = f"delta_{pol.lower()}"
    legend, _ = build_legend_for_layer(layer_type, PolarizationChannel(pol))
    rgba = render_layer_rgba(data, layer_type=layer_type, min_val=legend.min_value, max_val=legend.max_value)
    name = f"{layer_type}.png"
    Image.fromarray(rgba).save(output / name)
    west, south, east, north = transform_bounds(
        "EPSG:3857", "EPSG:4326", *rasterio.transform.array_bounds(height, width, transform)
    )
    return {"layer_id": layer_type, "polarization": pol, "units": "dB", "geotiff_href": tif.name,
            "evidence_id": evidence_id, "legend": legend.model_dump(mode="json"),
            "overlay": {"href": name, "crs": "EPSG:3857",
                        "coordinates_lon_lat": [[west, north], [east, north], [east, south], [west, south]]}}


def verify(directory, result, windows):
    m = json.loads((directory / "manifest.json").read_bytes())
    evidence = EvidenceRecord.model_validate_json((directory / m["evidence_href"]).read_bytes())
    stats = json.loads((directory / m["statistics_href"]).read_bytes())
    require(evidence.evidence_id == m["evidence_id"] == stats["evidence_id"], "Evidence links disagree.")
    require(evidence.scene_ids == [s["scene_id"] for s in m["scenes"]], "Evidence scene links disagree.")
    for name, expected in m["asset_sha256"].items():
        require(sha(directory / name) == expected, f"Hash mismatch: {name}")
    pair = []
    for layer in m["layers"]:
        pol = layer["polarization"]
        require(layer["evidence_id"] == evidence.evidence_id, "Layer Evidence ID mismatch.")
        with rasterio.open(directory / layer["geotiff_href"]) as ds:
            values = ds.read(1)
            valid = np.isfinite(values)
            require(ds.crs.to_epsg() == m["grid"]["epsg"], "GeoTIFF CRS mismatch.")
            require(np.array_equal(valid, result.mask_bundle.common_valid_by_pol[pol]), "GeoTIFF validity differs.")
            require(int(valid.sum()) == stats["polarizations"][pol]["valid_pixel_count"], "Channel count differs.")
            require(np.isclose(np.median(values[valid]), stats["polarizations"][pol]["median_delta_db"], atol=0.0001),
                    "Raster median differs from engine statistics.")
            t0, t1 = (w.power[pol].astype(np.float64) for w in windows)
            independent = result.mask_bundle.aoi_footprint_mask.copy()
            for w, power in zip(windows, (t0, t1), strict=True):
                independent &= (w.mask > 0) & (w.mask < 255) & np.isfinite(power) & (power > 0)
            require(np.array_equal(valid, independent), "GeoTIFF validity differs from raw mask and power.")
            expected = 10 * np.log10(t1[valid] / t0[valid])
            require(np.allclose(values[valid], expected, atol=0.00002, rtol=0),
                    "GeoTIFF dB differs from independent calculation.")
            pair.append(valid)
        with Image.open(directory / layer["overlay"]["href"]) as img:
            img.verify()
        with Image.open(directory / layer["overlay"]["href"]) as img:
            require(img.mode == "RGBA" and img.getchannel("A").getextrema()[1] > 0, "Empty PNG overlay.")
        corners = layer["overlay"]["coordinates_lon_lat"]
        require(len(corners) == 4 and corners[0][0] < corners[1][0] and corners[0][1] > corners[3][1],
                "Invalid MapLibre corner order.")
    require(int((pair[0] & pair[1]).sum()) == evidence.valid_pixel_count, "Common valid count differs.")


def main():
    require(not OUT.exists(), "Output already exists; preserve the published bundle.")
    aoi = json.loads(AOI.read_bytes())
    scenes, windows = check_inputs(aoi["geometry"])
    identity = json.dumps(["sar2action-change-engine-v1.0.0", aoi["geometry"], "frequencyA",
                           *(s["sha256"] for s in scenes)], sort_keys=True)
    evidence_id = "E-TW03-" + hashlib.sha256(identity.encode()).hexdigest()[:16].upper()
    result = run_in_memory_change_analysis(win_t0=windows[0], win_t1=windows[1], roi_id=CASE,
                                           evidence_id=evidence_id, include_combined_change=False)
    ev = result.evidence_record
    require(ev.valid_pixel_count > 0 and ev.quality_status.value != "INSUFFICIENT_EVIDENCE"
            and result.available_polarizations == ["HH", "HV"], "GCOV mask or coverage failed the science gate.")
    ev.limitations.extend(x for x in LIMITS if x not in ev.limitations)
    stats = {"evidence_id": evidence_id, "valid_pixel_count": ev.valid_pixel_count,
             "coverage_ratio": ev.coverage_ratio, "missing_data_ratio": ev.missing_data_ratio,
             "requested_pixel_count": ev.summary_statistics["requested_pixel_count"],
             "polarizations": ev.summary_statistics["per_polarization"],
             "mask_rule": MASK_RULE_SPECIFICATION,
             "mask_classes_by_epoch": []}
    for w in windows:
        classes, counts = np.unique(w.mask[result.mask_bundle.aoi_footprint_mask], return_counts=True)
        stats["mask_classes_by_epoch"].append({str(k): int(v) for k, v in zip(classes, counts, strict=True)})
    with TemporaryDirectory(prefix="build-", dir=ROOT) as tmp:
        stage = Path(tmp) / OUT.name
        stage.mkdir()
        save(stage / "aoi.geojson", aoi)
        save(stage / "evidence.json", ev.model_dump(mode="json"))
        save(stage / "statistics.json", stats)
        with TemporaryDirectory(prefix="geotiff-", dir=ROOT) as tifs:
            exported = result.export_geotiffs(tifs)
            layers = []
            for pol in ("HH", "HV"):
                tif = stage / f"delta_{pol.lower()}_db.tif"
                exported[f"delta_{pol.lower()}_db"].replace(tif)
                layers.append(overlay(tif, stage, pol, evidence_id))
        manifest = {"schema_version": "nisar-tw03-demo/1.0", "status": "verified_observation",
                    "case_id": CASE, "evidence_id": evidence_id, "evidence_href": "evidence.json",
                    "statistics_href": "statistics.json", "aoi_href": "aoi.geojson",
                    "sensor": "NASA-ISRO NISAR L-band", "collection": "NISAR_L2_GCOV_PROVISIONAL_V1",
                    "frequency_group": "frequencyA", "algorithm_version": ev.algorithm_version,
                    "quality_status": ev.quality_status.value,
                    "grid": {"epsg": result.grid.epsg, "spacing_m": [abs(result.grid.x_spacing_m), abs(result.grid.y_spacing_m)],
                             "full_shape": [result.grid.height, result.grid.width], "window_shape": list(result.window.shape)},
                    "scenes": scenes, "layers": layers, "limitations": ev.limitations,
                    "asset_sha256": {p.name: sha(p) for p in sorted(stage.iterdir())}}
        save(stage / "manifest.json", manifest)
        verify(stage, result, windows)
        stage.rename(OUT)
    print("PASS: evidence schema, hashes, scene IDs, raster masks and counts, medians, PNG and MapLibre coordinates")
    print(json.dumps({"evidence_id": evidence_id, "quality": ev.quality_status.value,
                      "grid": manifest["grid"], "statistics": stats}, ensure_ascii=True))


if __name__ == "__main__":
    main()
