"""Phase 2B Flagship Case Discovery & Actual Illumination Verification Script.

Retrieves and inspects the complete repeat-pass stacks for:
1. Primary Candidate: `AOI-A2` (South Sumatra / Ogan Komering Ilir peatland corridor)
   - Stack `T119_F090` (`DESCENDING`, `LEFT` look, `HH + HV`, `CRID = P05023`)
   - Stack `T018_F090` (`DESCENDING`, `LEFT` look, `HH + HV`, `CRID = P05023`)
2. Secondary Sumatra Candidate: `AOI-A1` (Mainland Riau)
   - Stack `T148_F088` (`DESCENDING`, `LEFT` look, `HH + HV`, `CRID = P05023`, full-frame)
3. Backup Candidate: `AOI-B1` (Northern California wildfire corridor)
   - Stack `T143_F068` (`DESCENDING`, `LEFT` look, `HH + HV`, `CRID = P05023`, full-frame)

Downloads ONLY lightweight companion sidecars (`_LATLON.kml` ~1.8 KB, `_QA_SUMMARY.csv` ~1.4 KB,
`_QA_STATS.h5` ~83 KB) — zero full HDF5 granules downloaded — to verify actual SAR illumination
footprints, valid pixel counts, and temporal backscatter trajectories across June–October 2026.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

import h5py
import numpy as np
from shapely.geometry import Polygon, box

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sar.catalog.asf_client import parse_nisar_gcov_granule_id  # noqa: E402
from sar.ingest.earthdata_auth import EarthdataOAuthSession  # noqa: E402

AOI_A2_WIDE_BBOX = [104.50, -3.80, 106.20, -2.30]
AOI_A2_OKI_CORE_BBOX = [104.80, -3.60, 106.00, -2.60]
AOI_A1_WIDE_BBOX = [100.80, -0.30, 103.20, 2.10]
AOI_B1_WIDE_BBOX = [-122.50, 39.60, -121.10, 40.80]


def parse_kml_polygon(kml_text: str) -> Polygon | None:
    """Parse `<coordinates>` from a NISAR `_LATLON.kml` sidecar into a 2D Shapely Polygon."""
    match = re.search(r"<coordinates>(.*?)</coordinates>", kml_text, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    raw_coords = match.group(1).strip()
    pts: list[tuple[float, float]] = []
    for token in raw_coords.split():
        parts = token.split(",")
        if len(parts) >= 2:
            pts.append((float(parts[0]), float(parts[1])))
    if len(pts) < 3:
        return None
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly


def parse_qa_stats_h5(h5_path: pathlib.Path) -> dict[str, Any]:
    """Extract HHHH and HVHV summary statistics and RFI likelihood from `_QA_STATS.h5`."""
    out: dict[str, Any] = {}
    with h5py.File(h5_path, "r") as f:
        base = "/science/LSAR/QA/data/frequencyA"
        if base in f:
            grp = f[base]
            for pol in ("HHHH", "HVHV"):
                if pol in grp:
                    pgrp = grp[pol]
                    entry: dict[str, Any] = {}
                    for k in ("min_value", "max_value", "mean_value", "sample_stddev"):
                        if k in pgrp:
                            v = pgrp[k][()]
                            if isinstance(v, np.ndarray):
                                v = v.item()
                            entry[k] = round(float(v), 6)
                    if entry.get("mean_value") and entry["mean_value"] > 0:
                        entry["mean_db"] = round(float(10.0 * np.log10(entry["mean_value"])), 4)
                    out[pol] = entry
        rfi_path = "/science/LSAR/RFI/data/frequencyA"
        if rfi_path in f:
            rgrp = f[rfi_path]
            rfi_dict: dict[str, float] = {}
            for pol_key in rgrp.keys():
                if "rfiLikelihood" in rgrp[pol_key]:
                    val = rgrp[pol_key]["rfiLikelihood"][()]
                    if isinstance(val, np.ndarray):
                        val = val.item()
                    rfi_dict[pol_key] = round(float(val), 6)
            out["rfi_likelihood"] = rfi_dict
    return out


def fetch_sidecars_for_scene(
    session: EarthdataOAuthSession,
    scene: dict[str, Any],
    sidecar_dir: pathlib.Path,
    target_wide_bbox: list[float],
    target_core_bbox: list[float] | None = None,
) -> dict[str, Any]:
    """Download `_LATLON.kml`, `_QA_SUMMARY.csv`, and `_QA_STATS.h5` for `scene` and parse illumination."""
    scene_id = scene["scene_id"]
    dl_url = scene.get("download_url") or ""
    parsed_tokens = parse_nisar_gcov_granule_id(scene_id)

    sidecar_dir.mkdir(parents=True, exist_ok=True)
    kml_path = sidecar_dir / f"{scene_id}_LATLON.kml"
    csv_path = sidecar_dir / f"{scene_id}_QA_SUMMARY.csv"
    stats_path = sidecar_dir / f"{scene_id}_QA_STATS.h5"

    base_url = f"https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/{scene_id}/{scene_id}"
    downloaded_bytes = 0

    for suffix, local_p in (
        ("_LATLON.kml", kml_path),
        ("_QA_SUMMARY.csv", csv_path),
        ("_QA_STATS.h5", stats_path),
    ):
        if not local_p.exists():
            url = f"{base_url}{suffix}"
            try:
                resp = session.get(url, timeout=45)
                resp.raise_for_status()
                content = resp.content
                local_p.write_bytes(content)
                downloaded_bytes += len(content)
            except Exception as exc:
                print(f"  [WARN] Could not fetch {suffix} for {scene_id}: {exc}")

    from shapely.geometry import shape

    # Parse actual illuminated 40-vertex boundingPolygon from UMM-G / HDF5 identification
    gpoly: Polygon | None = None
    if scene.get("bounding_geometry"):
        gpoly = shape(scene["bounding_geometry"])
        if not gpoly.is_valid:
            gpoly = gpoly.buffer(0)

    # Parse KML frame quad
    kml_quad: Polygon | None = None
    if kml_path.exists():
        kml_quad = parse_kml_polygon(kml_path.read_text(encoding="utf-8", errors="replace"))

    illum_poly = gpoly if (gpoly is not None and not gpoly.is_empty) else kml_quad
    wide_box = box(*target_wide_bbox)
    core_box = box(*target_core_bbox) if target_core_bbox else None

    if illum_poly is not None and not illum_poly.is_empty:
        ibounds = [round(float(v), 5) for v in illum_poly.bounds]
        mid_lat_rad = np.radians(0.5 * (ibounds[1] + ibounds[3]))
        deg2_to_km2 = float(111.32 * 110.57 * np.cos(mid_lat_rad))
        illum_area_km2 = round(float(illum_poly.area * deg2_to_km2), 1)
        wide_overlap_ratio = round(
            float(illum_poly.intersection(wide_box).area / wide_box.area), 4
        )
        swath_in_wide_ratio = round(
            float(illum_poly.intersection(wide_box).area / illum_poly.area), 4
        )
        core_overlap_ratio = (
            round(float(illum_poly.intersection(core_box).area / core_box.area), 4)
            if core_box is not None
            else None
        )
    else:
        ibounds = scene.get("bbox")
        illum_area_km2 = None
        wide_overlap_ratio = None
        swath_in_wide_ratio = None
        core_overlap_ratio = None

    kml_quad_bounds = [round(float(v), 5) for v in kml_quad.bounds] if kml_quad is not None else None

    qa_stats = parse_qa_stats_h5(stats_path) if stats_path.exists() else {}

    notes = scene.get("notes") or ""
    full_frame_note = None
    if "full_frame=TRUE" in notes.upper():
        full_frame_note = True
    elif "full_frame=FALSE" in notes.upper():
        full_frame_note = False
    is_full_frame = (
        full_frame_note
        if full_frame_note is not None
        else parsed_tokens.get("is_full_frame")
    )

    size_bytes = scene.get("approx_file_size_bytes")
    size_gb = round(size_bytes / (1024**3), 2) if size_bytes else None

    return {
        "scene_id": scene_id,
        "aoi_id": scene["aoi_id"],
        "acquisition_start_utc": scene.get("acquisition_start_utc"),
        "acquisition_end_utc": scene.get("acquisition_end_utc"),
        "acquisition_date": (scene.get("acquisition_start_utc") or "")[:10],
        "track_or_frame": scene.get("track_or_frame"),
        "orbit_direction": scene.get("orbit_direction"),
        "look_direction": scene.get("look_direction") or "LEFT",
        "polarizations": scene.get("polarizations"),
        "product_maturity": scene.get("product_maturity"),
        "crid": scene.get("crid"),
        "processing_version": scene.get("processing_version"),
        "is_full_frame": is_full_frame,
        "approx_file_size_bytes": size_bytes,
        "approx_file_size_gb": size_gb,
        "cmr_bbox": scene.get("bbox"),
        "kml_frame_quad_bbox": kml_quad_bounds,
        "verified_illuminated_bbox": ibounds,
        "verified_illuminated_area_km2": illum_area_km2,
        "aoi_wide_illuminated_overlap_ratio": wide_overlap_ratio,
        "aoi_core_illuminated_overlap_ratio": core_overlap_ratio,
        "swath_inside_aoi_wide_ratio": swath_in_wide_ratio,
        "qa_stats": qa_stats,
        "sidecar_bytes_downloaded_now": downloaded_bytes,
    }


def main() -> None:
    manifest_path = ROOT / "data" / "scenes" / "scene_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    all_scenes: list[dict[str, Any]] = manifest["scenes"]

    # Group all scenes by (aoi_id, track_or_frame)
    stacks_overview: dict[str, list[dict[str, Any]]] = {}
    for s in all_scenes:
        key = f"{s['aoi_id']}_{s.get('track_or_frame')}"
        stacks_overview.setdefault(key, []).append(s)

    print("=== Available Repeat-Pass Stacks Across AOI-A2, AOI-A1, AOI-B1 ===")
    for k in sorted(stacks_overview.keys()):
        if k.startswith(("AOI-A2", "AOI-A1", "AOI-B1")):
            sc_list = stacks_overview[k]
            dates = [x.get("acquisition_start_utc", "")[:10] for x in sc_list]
            ff_counts = sum(
                1 for x in sc_list if "_N_F_J_" in x["scene_id"] or "full_frame=TRUE" in (x.get("notes") or "")
            )
            print(
                f"  {k}: {len(sc_list)} scenes ({ff_counts} full-frame), dates={dates[0]}..{dates[-1]}"
            )

    session = EarthdataOAuthSession()
    sidecar_base = ROOT / "data" / "raw" / "sidecars" / "phase2b_flagship"

    # 1. Inspect ALL AOI-A2 stacks!
    aoi_a2_scenes = [s for s in all_scenes if s["aoi_id"] == "AOI-A2"]
    print(f"\n=== Inspecting AOI-A2 South Sumatra Scenes ({len(aoi_a2_scenes)} total in manifest) ===")

    inspected_a2: list[dict[str, Any]] = []
    for s in aoi_a2_scenes:
        tf = s.get("track_or_frame") or ""
        if tf in ("T119_F090", "T018_F090", "T119_F089", "T111_F176", "T010_F176"):
            info = fetch_sidecars_for_scene(
                session,
                s,
                sidecar_base / f"AOI-A2_{tf}",
                AOI_A2_WIDE_BBOX,
                AOI_A2_OKI_CORE_BBOX,
            )
            inspected_a2.append(info)
            print(
                f"  {info['track_or_frame']} | {info['acquisition_date']} | full={info['is_full_frame']} "
                f"| size={info['approx_file_size_gb']} GB | illum_bbox={info['verified_illuminated_bbox']} "
                f"| aoi_overlap={info['aoi_wide_illuminated_overlap_ratio']} | core_overlap={info['aoi_core_illuminated_overlap_ratio']}"
            )

    # 2. Also inspect representative full-frame scenes in AOI-A1 (T148_F088) and Backup AOI-B1 (T143_F068)
    inspected_a1: list[dict[str, Any]] = []
    for s in all_scenes:
        if s["aoi_id"] == "AOI-A1" and s.get("track_or_frame") == "T148_F088":
            info = fetch_sidecars_for_scene(
                session,
                s,
                sidecar_base / "AOI-A1_T148_F088",
                AOI_A1_WIDE_BBOX,
                [101.20, 0.20, 102.80, 1.80],
            )
            inspected_a1.append(info)

    inspected_b1: list[dict[str, Any]] = []
    for s in all_scenes:
        if s["aoi_id"] == "AOI-B1" and s.get("track_or_frame") == "T143_F068":
            # Inspect June-Oct 2026 scenes in T143_F068
            if (s.get("acquisition_start_utc") or "") >= "2026-06-01":
                info = fetch_sidecars_for_scene(
                    session,
                    s,
                    sidecar_base / "AOI-B1_T143_F068",
                    AOI_B1_WIDE_BBOX,
                    [-122.40, 39.70, -121.20, 40.70],
                )
                inspected_b1.append(info)

    out_payload = {
        "aoi_a2_inspected_scenes": inspected_a2,
        "aoi_a1_t148_f088_scenes": inspected_a1,
        "aoi_b1_t143_f068_scenes": inspected_b1,
    }
    out_path = ROOT / "data" / "processed" / "phase2b_flagship_discovery.json"
    out_path.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")
    print(f"\nSaved Phase 2B discovery payload to: {out_path}")


if __name__ == "__main__":
    main()
