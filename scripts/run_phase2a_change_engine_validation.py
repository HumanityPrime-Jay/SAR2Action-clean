"""Run Phase 2A Change Engine validation on the approved T047_F087 engineering pair.

Processes two validation AOIs:
1. `AOI-ENG-01` (`[104.20, 1.90, 104.35, 2.05]`): Core interior swath window (`E-PHASE2A-ENG-001`)
   exporting GeoTIFF rasters for all 11 Phase 2A.5 layers.
2. `AOI-ENG-02` (`[103.12, 2.08, 103.30, 2.25]`): Swath-edge window (`E-PHASE2A-ENG-002`)
   demonstrating real `mask == 0` finite-positive-power rejection in action.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tracemalloc

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sar.change import run_aoi_change_analysis  # noqa: E402

T0_H5 = (
    ROOT
    / "data"
    / "raw"
    / "scenes"
    / "NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001.h5"
)
T1_H5 = (
    ROOT
    / "data"
    / "raw"
    / "scenes"
    / "NISAR_L2_PR_GCOV_031_047_D_087_4005_DHDH_A_20260921T112603_20260921T112609_P05023_N_P_J_001.h5"
)


def main() -> None:
    out_dir = ROOT / "data" / "processed" / "phase2a_validation"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Core Interior Window (AOI-ENG-01)
    tracemalloc.start()
    res1 = run_aoi_change_analysis(
        T0_H5,
        T1_H5,
        [104.20, 1.90, 104.35, 2.05],
        roi_id="AOI-ENG-01",
        evidence_id="E-PHASE2A-ENG-001",
    )
    _, peak_ram_1 = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    tifs_1 = res1.export_geotiffs(out_dir / "AOI-ENG-01")

    # 2. Swath-Edge Window with mask == 0 finite-positive-power rejection (AOI-ENG-02)
    tracemalloc.start()
    res2 = run_aoi_change_analysis(
        T0_H5,
        T1_H5,
        [103.12, 2.08, 103.30, 2.25],
        roi_id="AOI-ENG-02",
        evidence_id="E-PHASE2A-ENG-002",
    )
    _, peak_ram_2 = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    tifs_2 = res2.export_geotiffs(out_dir / "AOI-ENG-02")

    # Update Evidence Store
    ev_store_path = ROOT / "data" / "cache" / "evidence_store.json"
    if ev_store_path.exists():
        store = json.loads(ev_store_path.read_text(encoding="utf-8"))
    else:
        store = {"records": {}}
    store["records"]["E-PHASE2A-ENG-001"] = res1.evidence_record.model_dump(mode="json")
    store["records"]["E-PHASE2A-ENG-002"] = res2.evidence_record.model_dump(mode="json")
    ev_store_path.write_text(json.dumps(store, indent=2), encoding="utf-8")

    summary = {
        "AOI-ENG-01": {
            "roi_id": res1.roi_id,
            "evidence_id": res1.evidence_id,
            "bbox_wgs84": [104.20, 1.90, 104.35, 2.05],
            "window_slice": {
                "row_start": res1.window.row_start,
                "row_stop": res1.window.row_stop,
                "col_start": res1.window.col_start,
                "col_stop": res1.window.col_stop,
                "shape": list(res1.window.shape),
                "window_pixel_count": res1.window.window_pixel_count,
            },
            "runtime_seconds": res1.runtime_seconds,
            "window_ram_bytes": res1.window_ram_bytes,
            "window_ram_mb": round(res1.window_ram_bytes / (1024**2), 2),
            "peak_python_tracemalloc_mb": round(peak_ram_1 / (1024**2), 2),
            "full_frame_equivalent_bytes": res1.full_frame_equivalent_bytes,
            "full_frame_equivalent_gb": round(res1.full_frame_equivalent_bytes / (1024**3), 2),
            "ram_reduction_factor": round(
                res1.full_frame_equivalent_bytes / max(1, res1.window_ram_bytes), 1
            ),
            "exported_geotiffs": {k: str(v) for k, v in tifs_1.items()},
            "evidence_record": res1.evidence_record.model_dump(mode="json"),
        },
        "AOI-ENG-02": {
            "roi_id": res2.roi_id,
            "evidence_id": res2.evidence_id,
            "bbox_wgs84": [103.12, 2.08, 103.30, 2.25],
            "window_slice": {
                "row_start": res2.window.row_start,
                "row_stop": res2.window.row_stop,
                "col_start": res2.window.col_start,
                "col_stop": res2.window.col_stop,
                "shape": list(res2.window.shape),
                "window_pixel_count": res2.window.window_pixel_count,
            },
            "runtime_seconds": res2.runtime_seconds,
            "window_ram_bytes": res2.window_ram_bytes,
            "window_ram_mb": round(res2.window_ram_bytes / (1024**2), 2),
            "peak_python_tracemalloc_mb": round(peak_ram_2 / (1024**2), 2),
            "full_frame_equivalent_bytes": res2.full_frame_equivalent_bytes,
            "full_frame_equivalent_gb": round(res2.full_frame_equivalent_bytes / (1024**3), 2),
            "ram_reduction_factor": round(
                res2.full_frame_equivalent_bytes / max(1, res2.window_ram_bytes), 1
            ),
            "exported_geotiffs": {k: str(v) for k, v in tifs_2.items()},
            "evidence_record": res2.evidence_record.model_dump(mode="json"),
        },
    }

    out_json = ROOT / "data" / "processed" / "phase2a_change_engine_results.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Saved Phase 2A Change Engine results to:", out_json)


if __name__ == "__main__":
    main()
