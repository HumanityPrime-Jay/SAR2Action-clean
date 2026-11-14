"""Reproducible science data inventory, verification, and bootstrap helper.

Never stores credentials or tokens in code. Uses SAR2ACTION_DATA_ROOT (or ./data)
and supports NASA Earthdata authentication via ~/.netrc or standard environment
variables when downloading OPERA RTC-S1 COGs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACKED_CHAMPI = ROOT / "data" / "exports" / "typhoon_champi"

OPERA_SCENES = [
    {
        "granule_id": "OPERA_L2_RTC-S1_T105-224320-IW3_20251008T215154Z_20251009T011425Z_S1C_30_v1.0",
        "product_version": "v1.0",
        "vh_sha256": "6cfc01875c279b25753821a017677b0cc009d7eea43395542088d4c1af70a1ec",
        "mask_sha256": "62daaf7ea503f71362b62f810cab8f7d1ad2585eb6a59002b69ad9b2e4a53d36",
    },
    {
        "granule_id": "OPERA_L2_RTC-S1_T105-224320-IW3_20251020T215154Z_20251021T015140Z_S1C_30_v1.0",
        "product_version": "v1.0",
        "vh_sha256": "4e552710092b31d638f9fa9d02ad06deb33ff44947da5665abea92aad05f95cb",
        "mask_sha256": "a81ed25eb95a5d26460bf0d54b54cfaaa7e142ffd21d5b8f0abe7cef9c659454",
    },
    {
        "granule_id": "OPERA_L2_RTC-S1_T105-224320-IW3_20251101T215154Z_20251102T011849Z_S1C_30_v1.0",
        "product_version": "v1.0",
        "vh_sha256": "bfe3c016228cb17c7265e11e3b189dfb2b2190e2a504c8ca2f650537fc9a82a8",
        "mask_sha256": "876c111950eec30b1cf8d25f2b727da2b21f8b818795c46cf1b33992a8b7729d",
    },
    {
        "granule_id": "OPERA_L2_RTC-S1_T105-224320-IW3_20261010T215156Z_20261011T203150Z_S1C_30_v1.0",
        "product_version": "v1.0",
        "vh_sha256": "8bd0cfc981fa7cfeac36f23d60de46de032115c0eb210600adc9390dad11d901",
        "mask_sha256": "a73953df4a570c61980d2afc8e5a00bdc8fd355f6fde0a4da6fc097b0323d8ac",
    },
    {
        "granule_id": "OPERA_L2_RTC-S1_T105-224320-IW3_20261022T215156Z_20261023T065025Z_S1C_30_v1.0",
        "product_version": "v1.0",
        "vh_sha256": "e19d4674835ee9174afb99b171c24f2de8222e0266d270c8fc66779e5bc49d6c",
        "mask_sha256": "6e85a5e1e39014cf4abf7e7607b566925a4b5b2a822827a4707aec2679e64184",
    },
    {
        "granule_id": "OPERA_L2_RTC-S1_T105-224320-IW3_20261103T215156Z_20261105T191651Z_S1C_30_v1.0",
        "product_version": "v1.0",
        "vh_sha256": "f3a7c227da82ecad38e6e1edab859c9b4ae6bcc2e0f889177546f4c7d690a952",
        "mask_sha256": "7b1462b1ff88645e6995c1e9115036e82a325f782605b6ff81af8b1ad4db1577",
    },
]


def resolve_data_root(cli_root: str | None) -> Path:
    if cli_root:
        return Path(cli_root).resolve()
    return Path(os.environ.get("SAR2ACTION_DATA_ROOT") or (ROOT / "data")).resolve()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_data_root(data_root: Path) -> dict:
    manifest_path = data_root / "exports/typhoon_champi/science_manifest.json"
    if not manifest_path.is_file():
        manifest_path = TRACKED_CHAMPI / "science_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    nisar_missing = []
    nisar_mismatch = []
    nisar_ok = 0
    for item in manifest["inputs"] + manifest["outputs"]:
        rel = Path(item["path"]).relative_to("data")
        target = data_root / rel
        if not target.is_file():
            nisar_missing.append(item["path"])
        elif _sha256(target) != item["sha256"]:
            nisar_mismatch.append(item["path"])
        else:
            nisar_ok += 1

    opera_dir = data_root / "raw/opera_yunlin_vh"
    opera_missing = []
    opera_mismatch = []
    opera_ok = 0
    for scene in OPERA_SCENES:
        gid = scene["granule_id"]
        for suffix, expected in (("_VH.tif", scene["vh_sha256"]), ("_mask.tif", scene["mask_sha256"])):
            target = opera_dir / f"{gid}{suffix}"
            if not target.is_file():
                opera_missing.append(target.name)
            elif _sha256(target) != expected:
                opera_mismatch.append(target.name)
            else:
                opera_ok += 1

    return {
        "data_root": str(data_root),
        "nisar": {"verified": nisar_ok, "missing": nisar_missing, "mismatch": nisar_mismatch},
        "opera": {"verified": opera_ok, "missing": opera_missing, "mismatch": opera_mismatch},
        "ready_for_live_v3": not (nisar_missing or nisar_mismatch or opera_missing or opera_mismatch),
    }


def print_sources() -> None:
    inv = json.loads((TRACKED_CHAMPI / "scene_inventory.json").read_text(encoding="utf-8"))
    print("== NISAR L2 GCOV (NASA ASF Earthdata Cloud) ==")
    for s in inv.get("scenes", [])[:2]:
        print(f"  Scene ID: {s['scene_id']}")
        print(f"  Collection: {s['collection']} | CRID: {s['crid']} | Relation: {s['event_relation']}")
        print(f"  Concept: {s['source_url']}")
    print("\n== OPERA L2 RTC-S1 v1.0 (NASA ASF Earthdata Cloud) ==")
    for s in OPERA_SCENES:
        print(f"  Granule: {s['granule_id']} ({s['product_version']})")
        print(f"    VH SHA256:   {s['vh_sha256']}")
        print(f"    Mask SHA256: {s['mask_sha256']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or bootstrap SAR2Action scientific data.")
    parser.add_argument("--data-root", help="Target SAR2ACTION_DATA_ROOT directory.")
    parser.add_argument("--check", action="store_true", help="Verify local science assets against SHA256 manifests.")
    parser.add_argument("--print-sources", action="store_true", help="Print scene IDs, versions, and SHA256 hashes.")
    parser.add_argument("--download-opera", action="store_true", help="Run OPERA VH downloader using local Earthdata auth.")
    args = parser.parse_args()

    data_root = resolve_data_root(args.data_root)
    if args.print_sources:
        print_sources()
    if args.download_opera:
        env = dict(os.environ)
        env["SAR2ACTION_DATA_ROOT"] = str(data_root)
        cmd = [sys.executable, "-m", "scripts.agriculture_vh.download_opera"]
        return subprocess.call(cmd, cwd=str(ROOT), env=env)
    if args.check or not (args.print_sources or args.download_opera):
        report = verify_data_root(data_root)
        print(json.dumps(report, indent=2))
        return 0 if report["ready_for_live_v3"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
