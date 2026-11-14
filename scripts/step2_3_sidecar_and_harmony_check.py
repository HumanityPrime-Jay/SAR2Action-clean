"""Gate A.2 Step 2 & Step 3: Sidecar-First Validation and NASA Harmony Extraction Probe."""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import h5py
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sar.ingest.earthdata_auth import EarthdataOAuthSession

COLLECTION_SHORT_NAME = "NISAR_L2_GCOV_PROVISIONAL_V1"
T0_ID = "NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001"
T0_CONCEPT_ID = "G4260394498-ASF"
T1_ID = "NISAR_L2_PR_GCOV_031_047_D_087_4005_DHDH_A_20260921T112603_20260921T112609_P05023_N_P_J_001"
T1_CONCEPT_ID = "G4320561922-ASF"

SIDECAR_SUFFIXES = [
    "_QA_SUMMARY.csv",
    "_QA_STATS.h5",
    ".h5.iso.xml",
    ".rc.yaml",
    "_LATLON.kml",
    "_NATIVE.kml",
]


def download_sidecars(
    session: EarthdataOAuthSession,
    scene_id: str,
    out_dir: pathlib.Path,
) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    base_url = f"https://nisar.asf.earthdatacloud.nasa.gov/NISAR/{COLLECTION_SHORT_NAME}/{scene_id}/{scene_id}"
    for suffix in SIDECAR_SUFFIXES:
        fname = f"{scene_id}{suffix}"
        url = f"{base_url}{suffix}"
        target = out_dir / fname
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
        content = resp.content
        # Verify not HTML login redirect
        head_str = content[:256].decode("utf-8", errors="ignore").lower()
        if "<html" in head_str or "<!doctype html" in head_str:
            raise RuntimeError(f"Sidecar {fname} returned HTML login page instead of data!")
        target.write_bytes(content)
        records.append(
            {
                "scene_id": scene_id,
                "filename": fname,
                "size_bytes": len(content),
                "http_status": resp.status_code,
                "content_type": resp.headers.get("Content-Type"),
                "path": str(target),
            }
        )
        print(f"  Downloaded {fname}: {len(content):,} bytes (HTTP {resp.status_code})")
    return records


def inspect_qa_stats_h5(h5_path: pathlib.Path) -> dict[str, Any]:
    info: dict[str, Any] = {"datasets": {}}

    def _visitor(name: str, obj: Any) -> None:
        if isinstance(obj, h5py.Dataset):
            val = obj[()]
            if isinstance(val, np.ndarray):
                if val.size <= 20:
                    decoded = val.tolist()
                    if isinstance(decoded, bytes):
                        decoded = decoded.decode("utf-8", errors="replace")
                    info["datasets"][name] = {
                        "shape": list(obj.shape),
                        "dtype": str(obj.dtype),
                        "value": str(decoded),
                    }
                else:
                    info["datasets"][name] = {
                        "shape": list(obj.shape),
                        "dtype": str(obj.dtype),
                        "min": float(np.nanmin(val)) if np.issubdtype(obj.dtype, np.number) else None,
                        "max": float(np.nanmax(val)) if np.issubdtype(obj.dtype, np.number) else None,
                    }
            else:
                if isinstance(val, (bytes, np.bytes_)):
                    val = val.decode("utf-8", errors="replace")
                elif isinstance(val, np.generic):
                    val = val.item()
                info["datasets"][name] = {
                    "shape": list(obj.shape),
                    "dtype": str(obj.dtype),
                    "value": val,
                }

    with h5py.File(h5_path, "r") as f:
        f.visititems(_visitor)
    return info


def probe_harmony_capabilities(session: EarthdataOAuthSession) -> dict[str, Any]:
    # 1. Look up exact collection concept-id from CMR
    cmr_resp = session.get(
        "https://cmr.earthdata.nasa.gov/search/collections.umm_json",
        params={"short_name": COLLECTION_SHORT_NAME},
        timeout=30,
    )
    cmr_resp.raise_for_status()
    c_item = cmr_resp.json()["items"][0]
    coll_concept_id = c_item["meta"]["concept-id"]
    associations = c_item["meta"].get("associations", {})
    print(f"  Collection {COLLECTION_SHORT_NAME} -> concept_id={coll_concept_id}")
    print(f"  CMR service/tool associations: {associations}")

    # 2. Query NASA Harmony capabilities endpoint
    cap_url = "https://harmony.earthdata.nasa.gov/capabilities"
    cap_resp = session.get(
        cap_url,
        params={"collectionId": coll_concept_id},
        timeout=30,
    )
    print(f"  Harmony /capabilities?collectionId={coll_concept_id} -> HTTP {cap_resp.status_code}")
    try:
        cap_body = cap_resp.json()
    except Exception:
        cap_body = {"raw_text": cap_resp.text[:500]}

    # 3. Also test OGC Coverages rangeset description
    cov_url = (
        f"https://harmony.earthdata.nasa.gov/{coll_concept_id}/ogc-api-coverages/1.0.0/"
        f"collections/all/coverage/rangeset"
    )
    cov_resp = session.get(
        cov_url,
        params={"granuleId": T0_CONCEPT_ID, "variable": "HHHH"},
        timeout=30,
    )
    print(f"  Harmony OGC coverage/rangeset test -> HTTP {cov_resp.status_code}")
    try:
        cov_body = cov_resp.json()
    except Exception:
        cov_body = {"raw_text": cov_resp.text[:500]}

    return {
        "collection_concept_id": coll_concept_id,
        "cmr_associations": associations,
        "capabilities_http_status": cap_resp.status_code,
        "capabilities_response": cap_body,
        "ogc_rangeset_http_status": cov_resp.status_code,
        "ogc_rangeset_response": cov_body,
    }


def main() -> None:
    session = EarthdataOAuthSession()
    sidecar_dir = ROOT / "data" / "raw" / "sidecars" / "AOI-A1_T047_F087"

    print("=== STEP 2: Downloading & Inspecting Official Sidecars for T0 and T1 ===")
    t0_records = download_sidecars(session, T0_ID, sidecar_dir)
    t1_records = download_sidecars(session, T1_ID, sidecar_dir)

    t0_qa_h5 = inspect_qa_stats_h5(sidecar_dir / f"{T0_ID}_QA_STATS.h5")
    t1_qa_h5 = inspect_qa_stats_h5(sidecar_dir / f"{T1_ID}_QA_STATS.h5")

    t0_rc = (sidecar_dir / f"{T0_ID}.rc.yaml").read_text(encoding="utf-8")
    t1_rc = (sidecar_dir / f"{T1_ID}.rc.yaml").read_text(encoding="utf-8")

    print("\n=== STEP 3: Probing NASA Harmony Dataset Extraction Support ===")
    harmony_result = probe_harmony_capabilities(session)

    summary = {
        "t0_sidecars": t0_records,
        "t1_sidecars": t1_records,
        "t0_qa_stats": t0_qa_h5,
        "t1_qa_stats": t1_qa_h5,
        "t0_rc_yaml": t0_rc,
        "t1_rc_yaml": t1_rc,
        "harmony_probe": harmony_result,
    }
    out_json = sidecar_dir / "sidecar_and_harmony_summary.json"
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote sidecar and Harmony inspection summary to {out_json}")


if __name__ == "__main__":
    main()
