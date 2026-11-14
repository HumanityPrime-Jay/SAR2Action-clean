"""Render transparent map previews from already verified Taixi NISAR dB rasters.

This is a display conversion only. It verifies source hashes and QA pixel counts,
uses each observation's own p05/p95 stretch, and never computes a date difference.
Run manually with --source-dir when the ignored GeoTIFFs live in another checkout.
Requires numpy, Pillow, tifffile, imagecodecs, and pyproj.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer
from tifffile import TiffFile


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def paint(band: np.ndarray, low: float, high: float) -> Image.Image:
    valid = np.isfinite(band)
    t = np.clip((np.where(valid, band, low) - low) / (high - low), 0, 1)
    stops = np.array([[16, 28, 61], [44, 150, 174], [245, 212, 128]], dtype=float)
    halfway = t <= 0.5
    fraction = np.where(halfway, t * 2, (t - 0.5) * 2)[..., None]
    first = np.where(halfway[..., None], stops[0], stops[1])
    second = np.where(halfway[..., None], stops[1], stops[2])
    rgb = np.rint(first + (second - first) * fraction).astype(np.uint8)
    alpha = np.where(valid, 220, 0).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


def run(source: Path, output: Path) -> None:
    qa = json.loads((source / "science_qa.json").read_text(encoding="utf-8"))
    manifest = json.loads((source / "science_manifest.json").read_text(encoding="utf-8"))
    expected = {Path(item["path"]).name: item["sha256"] for item in manifest["outputs"]
                if item["path"].endswith(".tif")}
    if qa["comparability"]["verified_typhoon_delta_allowed"] is not False:
        raise ValueError("Expected separate NISAR observations only")
    output.mkdir(parents=True, exist_ok=True)
    scenes = []
    for period in ("PRE", "POST"):
        info = qa["observations"][period]
        name = f"Taixi_{period}_HH_HV_db.tif"
        path = source / name
        if sha256(path) != expected[name]:
            raise ValueError(f"Science manifest hash mismatch: {name}")
        with TiffFile(path) as tif:
            bands = tif.asarray()
            if bands.shape != (2, *info["shape"]):
                raise ValueError(f"Band/grid mismatch: {name}")
            scale = tuple(float(x) for x in tif.pages[0].tags[33550].value[:2])
            tie = tuple(float(x) for x in tif.pages[0].tags[33922].value[3:5])
            a, _, left, _, e, top = info["grid_transform"]
            if scale != (a, -e) or tie != (left, top):
                raise ValueError(f"GeoTIFF/QA georeference mismatch: {name}")
        west, north = left, top
        east = left + a * info["shape"][1]
        south = top + e * info["shape"][0]
        project = Transformer.from_crs(info["crs"], "EPSG:4326", always_xy=True)
        corners = [project.transform(x, y) for x, y in
                   ((west, north), (east, north), (east, south), (west, south))]
        layers = {}
        for index, polarization in enumerate(("HH", "HV")):
            band = bands[index]
            finite = int(np.isfinite(band).sum())
            if finite != info["valid_pixels"]:
                raise ValueError(f"QA valid-pixel mismatch: {period} {polarization}")
            stats = info["gamma0_db"][polarization]
            filename = f"nisar_{period.lower()}_{polarization.lower()}_map.png"
            paint(band, float(stats["p05"]), float(stats["p95"])).save(output / filename)
            layers[polarization] = {
                "image": filename, "valid_pixels": finite,
                "display_stretch_db": [stats["p05"], stats["p95"]],
            }
        scenes.append({
            "period": period, "scene_id": info["scene_id"],
            "acquisition_start_utc": info["acquisition_start_utc"],
            "crid": info["crid"], "product_maturity": info["product_maturity"],
            "crs": info["crs"], "grid_shape": info["shape"],
            "source_sha256": expected[name], "coordinates": corners,
            "layers": layers,
        })
    result = {
        "case_id": qa["case_id"], "aoi_id": qa["aoi_id"],
        "aoi_kind": qa["aoi_kind"], "status": qa["comparability"]["qa_decision"],
        "cross_crid_radiometric_equivalence_verified": False,
        "verified_typhoon_delta_allowed": False,
        "display_method": "Independent p05/p95 stretch per scene and polarization; transparent nonfinite pixels; not a quantitative cross-date comparison",
        "scenes": scenes,
    }
    (output / "nisar_map_manifest.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Rendered four hash-checked NISAR observation layers; no delta computed")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=root / "data/exports/typhoon_champi")
    parser.add_argument("--output-dir", type=Path, default=root / "frontend/public/studio")
    args = parser.parse_args()
    run(args.source_dir, args.output_dir)
