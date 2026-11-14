"""Execute Phase 2C.6 Product-Level Validation and Phase 2C.7 Flagship AOI Change Analysis.

1. Validates the downloaded Primary Flagship Pair (Candidate F2: T010_F176 ASCENDING,
   2026-09-06 -> 2026-09-18) at the HDF5 product level -> promotes to COMPARABLE.
2. Runs the deterministic Change Engine (`sar/change/`) and `ScienceService` on:
   - Flagship OKI AOIs: `AOI-OKI-01`, `AOI-OKI-02`, `AOI-OKI-03`
   - Engineering Riau AOIs: `AOI-ENG-01`, `AOI-ENG-02` (refreshing with frozen L1 Combined Radar Change)
3. Exports QA GeoTIFFs to `data/processed/phase2c_flagship/` and `data/processed/phase2a_validation/`.
4. Persists `EvidenceRecord`s to `data/cache/evidence_store.json` and PNG layers to `data/cache/layer_pngs/`.
5. Writes summary JSON to `data/processed/phase2c_flagship/flagship_validation_summary.json`.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import time
from typing import Any

import h5py
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.schemas.api import RadarFingerprintRequest
from backend.app.services.science_service import ScienceService
from sar.change import (
    read_gcov_grid_and_metadata,
    run_aoi_change_analysis,
    verify_grids_compatible,
)

SCENES_DIR = ROOT / "data" / "raw" / "scenes"
OUT_FLAGSHIP_DIR = ROOT / "data" / "processed" / "phase2c_flagship"
OUT_PHASE2A_DIR = ROOT / "data" / "processed" / "phase2a_validation"

F2_T0_ID = "NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001"
F2_T1_ID = "NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001"

ENG_T0_ID = "NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001"
ENG_T1_ID = "NISAR_L2_PR_GCOV_031_047_D_087_4005_DHDH_A_20260921T112603_20260921T112609_P05023_N_P_J_001"


def inspect_h5_product(h5_path: pathlib.Path) -> dict[str, Any]:
    """Inspect top-level HDF5 groups, datasets, chunking, and coordinate vectors."""
    grid, meta = read_gcov_grid_and_metadata(h5_path)
    with h5py.File(h5_path, "r") as f:
        g_freq_a = f["/science/LSAR/GCOV/grids/frequencyA"]
        datasets: dict[str, Any] = {}
        for ds_name in ("HHHH", "HVHV", "mask", "numberOfLooks"):
            if ds_name in g_freq_a:
                ds = g_freq_a[ds_name]
                datasets[ds_name] = {
                    "shape": list(ds.shape),
                    "dtype": str(ds.dtype),
                    "chunks": list(ds.chunks) if ds.chunks else None,
                    "compression": ds.compression,
                }
    return {
        "scene_id": meta["scene_id"],
        "file_name": h5_path.name,
        "file_size_bytes": h5_path.stat().st_size,
        "file_size_gib": round(h5_path.stat().st_size / (1024**3), 4),
        "acquisition_start_utc": meta["acquisition_start_utc"],
        "acquisition_end_utc": meta["acquisition_end_utc"],
        "orbit_pass_direction": meta["orbit_pass_direction"],
        "look_direction": meta["look_direction"],
        "track_number": meta["track_number"],
        "frame_number": meta["frame_number"],
        "crid": meta["crid"],
        "product_version": meta["product_version"],
        "is_full_frame": meta["is_full_frame"],
        "data_maturity": meta["data_maturity"],
        "available_polarizations": meta["available_polarizations"],
        "epsg": grid.epsg,
        "width": grid.width,
        "height": grid.height,
        "x_spacing_m": grid.x_spacing_m,
        "y_spacing_m": grid.y_spacing_m,
        "x_min": float(grid.x_coordinates[0]),
        "x_max": float(grid.x_coordinates[-1]),
        "y_max": float(grid.y_coordinates[0]),
        "y_min": float(grid.y_coordinates[-1]),
        "datasets": datasets,
    }


def main() -> None:
    t0_path = SCENES_DIR / f"{F2_T0_ID}.h5"
    t1_path = SCENES_DIR / f"{F2_T1_ID}.h5"

    print("=== STEP 2C.6: PRODUCT-LEVEL VALIDATION OF PRIMARY FLAGSHIP PAIR ===")
    p0_info = inspect_h5_product(t0_path)
    p1_info = inspect_h5_product(t1_path)

    grid_t0, _ = read_gcov_grid_and_metadata(t0_path)
    grid_t1, _ = read_gcov_grid_and_metadata(t1_path)
    verify_grids_compatible(grid_t0, grid_t1)
    print(
        f"[PASS] Grid compatibility verified: EPSG:{grid_t0.epsg}, "
        f"{grid_t0.height} rows x {grid_t0.width} cols, "
        f"spacing=({grid_t0.x_spacing_m}, {grid_t0.y_spacing_m}) m"
    )

    free_disk_bytes = shutil.disk_usage(ROOT.anchor).free
    free_disk_gib = round(free_disk_bytes / (1024**3), 2)

    svc = ScienceService()
    svc._analysis_map.clear()
    svc._fingerprint_map.clear()
    OUT_FLAGSHIP_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PHASE2A_DIR.mkdir(parents=True, exist_ok=True)

    flagship_aois = [
        {
            "aoi_id": "AOI-OKI-01",
            "evidence_id": "E-FLAGSHIP-OKI-001",
            "name": "Tulung Selapan / Cengal Peatland Transition",
            "bbox": [105.28, -3.28, 105.48, -3.08],
            "selection_method": "PREDEFINED_GEOGRAPHIC_AOI",
            "selection_time": "PRE_ANALYSIS",
            "selection_basis": "Fixed ~22 km x 22 km district/peatland corridor in Tulung Selapan / Cengal defined prior to sub-patch inspection.",
        },
        {
            "aoi_id": "AOI-OKI-02",
            "evidence_id": "E-FLAGSHIP-OKI-002",
            "name": "Pangkalan Lampam / Pedamaran Peatland Belt",
            "bbox": [104.98, -3.32, 105.16, -3.14],
            "selection_method": "PREDEFINED_GEOGRAPHIC_AOI",
            "selection_time": "PRE_ANALYSIS",
            "selection_basis": "Fixed ~20 km x 20 km district/peatland corridor in Pangkalan Lampam / Pedamaran defined prior to sub-patch inspection.",
        },
        {
            "aoi_id": "AOI-OKI-03",
            "evidence_id": "E-FLAGSHIP-OKI-003",
            "name": "Eastern Cengal Coastal Peat Corridor",
            "bbox": [105.55, -3.42, 105.73, -3.24],
            "selection_method": "PREDEFINED_GEOGRAPHIC_AOI",
            "selection_time": "PRE_ANALYSIS",
            "selection_basis": "Fixed ~20 km x 20 km eastern Cengal coastal peat corridor defined prior to sub-patch inspection.",
        },
        {
            "aoi_id": "AOI-OKI-04",
            "evidence_id": "E-FLAGSHIP-OKI-004",
            "name": "Padang Sugihan Peatland Reserve & Buffer Corridor",
            "bbox": [105.08, -2.92, 105.24, -2.76],
            "selection_method": "PREDEFINED_EXTERNAL_CONTEXT",
            "selection_time": "PRE_ANALYSIS",
            "selection_basis": "Predefined from external ANTARA/Polda Sumsel/BPBD and BMKG event reports on Suaka Margasatwa Padang Sugihan before inspecting radar-change statistics.",
        },
    ]

    aoi_summaries: list[dict[str, Any]] = []
    print("\n=== STEP 2C.7: FLAGSHIP AOI CHANGE ENGINE & GEOTIFF EXPORT ===")
    for item in flagship_aois:
        t_start = time.perf_counter()
        res = run_aoi_change_analysis(
            t0_path,
            t1_path,
            item["bbox"],
            roi_id=item["aoi_id"],
            evidence_id=item["evidence_id"],
        )
        tifs = res.export_geotiffs(OUT_FLAGSHIP_DIR)
        fp_resp = svc.compute_radar_fingerprint(
            RadarFingerprintRequest(
                case_id="case-flagship-oki-f2",
                aoi_id=item["aoi_id"],
                aoi_bbox_wgs84=item["bbox"],
            )
        )
        elapsed = round(time.perf_counter() - t_start, 3)

        ev = res.evidence_record
        per_pol = ev.summary_statistics["per_polarization"]
        mb = res.mask_bundle

        # Exploratory post-hoc 2 km x 2 km (200x200 px) sub-patch inside this AOI
        # Explicitly marked as EXPLORATORY_POST_HOC_RADAR_CHANGE, not confirmatory evidence
        comb_arr = res.combined_radar_change.data if res.combined_radar_change else None
        subpatch_summary: dict[str, Any] = {}
        if comb_arr is not None and res.delta_hh_db is not None and res.delta_hv_db is not None:
            h, w = comb_arr.shape
            step = 200
            best_med = -1.0
            for r in range(0, max(1, h - step + 1), 100):
                for c in range(0, max(1, w - step + 1), 100):
                    sub_valid = res.common_valid_mask[r : r + step, c : c + step]
                    if np.mean(sub_valid) < 0.95:
                        continue
                    sub_comb = comb_arr[r : r + step, c : c + step][sub_valid]
                    med_val = float(np.median(sub_comb))
                    if med_val > best_med:
                        best_med = med_val
                        sub_dhh = res.delta_hh_db[r : r + step, c : c + step][sub_valid]
                        sub_dhv = res.delta_hv_db[r : r + step, c : c + step][sub_valid]
                        subpatch_summary = {
                            "selection_method": "EXPLORATORY_POST_HOC_RADAR_CHANGE",
                            "selection_time": "POST_HOC_INSPECTION",
                            "selection_basis": (
                                "Exploratory post-hoc 2 km x 2 km window selected after inspecting "
                                "radar change raster; not confirmatory wildfire evidence."
                            ),
                            "patch_shape_px": [int(step), int(step)],
                            "row_offset": int(r),
                            "col_offset": int(c),
                            "valid_pixels": int(np.sum(sub_valid)),
                            "median_delta_hh_db": round(float(np.median(sub_dhh)), 4),
                            "median_delta_hv_db": round(float(np.median(sub_dhv)), 4),
                            "p10_delta_hh_db": round(float(np.percentile(sub_dhh, 10)), 4),
                            "p90_delta_hh_db": round(float(np.percentile(sub_dhh, 90)), 4),
                            "p10_delta_hv_db": round(float(np.percentile(sub_dhv, 10)), 4),
                            "p90_delta_hv_db": round(float(np.percentile(sub_dhv, 90)), 4),
                            "median_combined_change_db_composite": round(med_val, 4),
                            "p90_combined_change_db_composite": round(float(np.percentile(sub_comb, 90)), 4),
                        }

        summary_entry = {
            "aoi_id": item["aoi_id"],
            "name": item["name"],
            "evidence_id": ev.evidence_id,
            "selection_method": item["selection_method"],
            "selection_time": item["selection_time"],
            "selection_basis": item["selection_basis"],
            "quality_status": ev.quality_status.value,
            "bbox_wgs84": item["bbox"],
            "window_shape_px": list(res.window.shape),
            "window_ram_mib": round(res.window_ram_bytes / (1024**2), 2),
            "full_frame_ram_gib": round(res.full_frame_equivalent_bytes / (1024**3), 2),
            "runtime_seconds": res.runtime_seconds,
            "total_with_export_seconds": elapsed,
            "valid_pixel_count": ev.valid_pixel_count,
            "valid_area_km2": ev.summary_statistics["valid_area_km2"],
            "valid_area_ha": ev.summary_statistics["valid_area_ha"],
            "coverage_ratio": ev.coverage_ratio,
            "missing_data_ratio": ev.missing_data_ratio,
            "mask_diagnostics": mb.diagnostics,
            "HH": per_pol["HH"],
            "HV": per_pol["HV"],
            "combined_radar_change": (
                ev.combined_change_db.model_dump(mode="json") if ev.combined_change_db else None
            ),
            "exploratory_post_hoc_2km_subpatch": subpatch_summary,
            "exported_geotiffs": {k: str(v.relative_to(ROOT)) for k, v in tifs.items()},
            "exported_png_layers": list(fp_resp.layers.keys()),
        }
        aoi_summaries.append(summary_entry)
        print(
            f"[{item['aoi_id']}] ({item['selection_method']}) status={ev.quality_status.value}, "
            f"valid_px={ev.valid_pixel_count:,} ({ev.coverage_ratio*100:.2f}%), "
            f"dHH_med={per_pol['HH']['median_delta_db']:+.4f} dB, "
            f"dHV_med={per_pol['HV']['median_delta_db']:+.4f} dB, "
            f"comb_med={ev.combined_change_db.stats.median:.4f} dB composite, "
            f"runtime={res.runtime_seconds:.3f}s"
        )

    # Refresh Engineering AOIs in store and GeoTIFFs with frozen L1 formula
    print("\n=== REFRESHING PHASE 2A ENGINEERING AOIS WITH FROZEN L1 COMBINED METRIC ===")
    eng_t0_path = SCENES_DIR / f"{ENG_T0_ID}.h5"
    eng_t1_path = SCENES_DIR / f"{ENG_T1_ID}.h5"
    eng_aois = [
        ("AOI-ENG-01", "E-PHASE2A-ENG-001", [104.20, 1.90, 104.35, 2.05]),
        ("AOI-ENG-02", "E-PHASE2A-ENG-002", [103.12, 2.08, 103.30, 2.25]),
    ]
    for aoi_id, ev_id, bbox in eng_aois:
        res_eng = run_aoi_change_analysis(
            eng_t0_path,
            eng_t1_path,
            bbox,
            roi_id=aoi_id,
            evidence_id=ev_id,
        )
        res_eng.export_geotiffs(OUT_PHASE2A_DIR)
        svc.compute_radar_fingerprint(
            RadarFingerprintRequest(
                case_id="case-engineering-riau-t047",
                aoi_id=aoi_id,
                aoi_bbox_wgs84=bbox,
            )
        )
        print(
            f"[{aoi_id}] refreshed {ev_id}: status={res_eng.evidence_record.quality_status.value}, "
            f"comb_med={res_eng.evidence_record.combined_change_db.stats.median:.4f} dB composite"
        )

    out_json = {
        "validation_decision": "COMPARABLE",
        "pair_role": "PRIMARY_FLAGSHIP",
        "track_frame": "T010_F176",
        "orbit_pass_direction": "ASCENDING",
        "t0_product": p0_info,
        "t1_product": p1_info,
        "grid_compatible": True,
        "post_download_free_disk_gib": free_disk_gib,
        "aoi_results": aoi_summaries,
    }
    summary_path = OUT_FLAGSHIP_DIR / "flagship_validation_summary.json"
    summary_path.write_text(json.dumps(out_json, indent=2), encoding="utf-8")
    print(f"\nSaved complete flagship validation summary to {summary_path}")


if __name__ == "__main__":
    main()
