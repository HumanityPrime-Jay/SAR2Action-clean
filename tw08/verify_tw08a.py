"""Verification suite for TW-08A Sentinel-2 L2A multi-temporal package."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import rasterio

ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "inputs"
OUT_DIR = ROOT / "sentinel2-demo-v1"


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    inv_path = INPUT_DIR / "stac_inventory.json"
    manifest_path = OUT_DIR / "manifest.json"
    assert inv_path.is_file(), f"Missing {inv_path}"
    assert manifest_path.is_file(), f"Missing {manifest_path}"

    with inv_path.open("r", encoding="utf-8") as stream:
        inventory = json.load(stream)
    with manifest_path.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    json.dumps(manifest, allow_nan=False)

    assert len(inventory["scenes"]) == 4, f"Expected 4 scenes, found {len(inventory['scenes'])}"
    for sc in inventory["scenes"]:
        assert sc["earthsearch_boa_offset_applied"] is True
        assert len(sc["bands"]) == 9
        for band_name, band_meta in sc["bands"].items():
            p = INPUT_DIR / band_meta["filename"]
            assert p.is_file(), f"Missing downloaded band {p}"
            assert _sha256(p) == band_meta["sha256"], f"Input SHA mismatch: {p}"

    for fname, expected_sha in manifest["artifact_sha256"].items():
        p = OUT_DIR / fname
        assert p.is_file(), f"Missing output artifact {p}"
        assert _sha256(p) == expected_sha, f"Output SHA mismatch: {p}"

    # Verify native 10m NDVI & 20m NDRE/LSWI/SCL grid integrity
    for sc in manifest["scenes"]:
        outputs = sc["outputs"]
        with rasterio.open(OUT_DIR / outputs["ndvi_tif"]) as ds:
            assert ds.crs.to_epsg() == 32651
            assert ds.shape == (510, 512)
            assert ds.res == (10.0, 10.0)
        for key in ("ndre_tif", "lswi_tif", "scl_tif"):
            with rasterio.open(OUT_DIR / outputs[key]) as ds:
                assert ds.crs.to_epsg() == 32651
                assert ds.shape == (255, 256)
                assert ds.res == (20.0, 20.0)

    # Verify CSV row counts and strict zero ground-truth flags
    cand_csv = OUT_DIR / manifest["csv_outputs"]["candidate_181"]
    farm_csv = OUT_DIR / manifest["csv_outputs"]["farmland_4863"]
    with cand_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        cand_rows = list(csv.DictReader(stream))
    with farm_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        farm_rows = list(csv.DictReader(stream))

    assert len(cand_rows) == 181, f"Expected 181 candidate rows, got {len(cand_rows)}"
    assert len(farm_rows) == 4863, f"Expected 4863 farmland rows, got {len(farm_rows)}"

    gt = manifest["ground_truth_and_classification_audit"]
    assert gt["ground_truth_labels_available"] is False
    assert gt["classifier_trained"] is False
    assert manifest["radiometry_and_cloud_masking"]["no_synthetic_gap_filling"] is True

    print(
        f"TW-08A VERIFICATION PASSED: 4 scenes (36 input bands), {len(manifest['artifact_sha256'])} outputs verified, "
        f"181 candidate rows, 4863 farmland rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
