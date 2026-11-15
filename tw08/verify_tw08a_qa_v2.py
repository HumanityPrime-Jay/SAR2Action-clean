"""Strict verification suite for TW-08A Phase 1 Scientific QA v2 + v1 immutability."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QA_V2_DIR = ROOT / "sentinel2-qa-v2"


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    # 1. Confirm TW-08A v1 artifacts & SHA-256 remain 100% unmodified
    v1_res = subprocess.run(
        [sys.executable, str(ROOT / "verify_tw08a.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    if v1_res.returncode != 0:
        print(v1_res.stdout)
        print(v1_res.stderr, file=sys.stderr)
        raise AssertionError("TW-08A v1 immutability check FAILED!")

    # 2. Validate QA v2 JSON manifest strictly (no NaN/Inf)
    manifest_path = QA_V2_DIR / "qa_v2_manifest.json"
    raw_text = manifest_path.read_text(encoding="utf-8")
    for bad in ("NaN", "Infinity", "-Infinity"):
        if bad in raw_text:
            raise AssertionError(f"Non-standard JSON token {bad!r} in qa_v2_manifest.json")
    manifest = json.loads(raw_text)

    assert manifest["schema_version"] == "tw08a-scientific-qa/2.0"
    assert manifest["overall_qa_gate"] == "PASS"
    assert manifest["v1_unmodified_verified"] is True

    # Audit 1: SCL 4/5/6 semantics
    scl_scenes = manifest["audit_1_scl_4_5_6_semantics"]["scenes"]
    assert len(scl_scenes) == 4
    s1105 = [s for s in scl_scenes if s["date_utc"] == "2026-11-05"][0]
    assert s1105["water_spectral_separation_verified"] is True
    assert s1105["veg_gt_bare_ndvi_verified"] is True
    assert s1105["classes"]["SCL_6_water"]["pixel_count_20m"] == 6
    assert s1105["classes"]["SCL_6_water"]["lswi_20m_stats"]["median"] > 0.30

    # Audit 2: BOA offset & 10m/20m alignment
    align = manifest["audit_2_boa_offset_and_grid_alignment"]
    assert align["overall_status"] == "PASS"
    assert align["origin_x_offset_m"] == 0.0
    assert align["origin_y_offset_m"] == 0.0
    assert align["exact_2x_integer_nesting"] is True
    assert len(align["scenes"]) == 4
    for sc in align["scenes"]:
        assert sc["earthsearch_boa_offset_applied"] is True
        assert sc["all_bands_crs_shape_bounds_transform_ok"] is True

    # Audit 3: 119 vs 62 & 4,863 breakdown
    c181 = manifest["audit_3_candidates_119_vs_62_and_farmland_4863"]["candidates_181"]["counts"]
    assert c181["total_candidates"] == 181
    assert c181["included_10m_strict_both"] == 119
    assert c181["excluded_insufficient_total"] == 62
    assert c181["excluded_breakdown"] == {
        "fail_20261011_only": 4,
        "fail_20261105_only": 47,
        "fail_both_dates": 11,
    }
    f4863 = manifest["audit_3_candidates_119_vs_62_and_farmland_4863"]["farmland_4863"]
    assert f4863["total_parcels"] == 4863
    assert f4863["sufficient_clear_both_1011_1105"] == 3166
    assert f4863["insufficient_optical_evidence_parcels"] == 1697

    # Audit 4: Spatial & Selection Sensitivity
    sens = manifest["audit_4_spatial_and_selection_bias_sensitivity"]
    assert sens["spatial_block_bootstrap"]["block_1000m_vh"]["positive_correlation_holds_at_95ci"] is True
    assert sens["spatial_block_bootstrap"]["block_500m_vh"]["positive_correlation_holds_at_95ci"] is True

    # Check output files and SHA-256
    csv_path = QA_V2_DIR / manifest["outputs"]["candidate_csv"]
    fig_path = QA_V2_DIR / manifest["outputs"]["diagnostic_figure"]
    assert csv_path.is_file() and _sha256(csv_path) == manifest["outputs"]["candidate_csv_sha256"]
    assert fig_path.is_file() and _sha256(fig_path) == manifest["outputs"]["diagnostic_figure_sha256"]
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 181

    print("TW-08A QA v2 VERIFICATION PASSED (v1 intact, 181 candidate rows, all 4 QA gates PASS).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
