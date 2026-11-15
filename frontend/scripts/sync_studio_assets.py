"""Publish only verified, nonsecret science JSON to Vite's static studio assets."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend" / "public" / "studio"
DATA_ROOT = Path(os.environ.get("SAR2ACTION_DATA_ROOT") or (ROOT / "data")).resolve()
CHAMPI = DATA_ROOT / "exports" / "typhoon_champi"
VH = DATA_ROOT / "exports" / "yunlin_vh_2025_2026"
FILES = {
    "recorded_investigation.json": CHAMPI / "demo_response.json",
    "recorded_trace.json": CHAMPI / "agent_trace.json",
    "champi_evidence.json": CHAMPI / "evidence.json",
    "official_loss_record.json": CHAMPI / "official_loss_record.json",
    "vh_timeseries.json": VH / "vh_timeseries.json",
    "vh_evidence.json": VH / "agent_evidence.json",
    "fields.geojson": VH / "fields.geojson",
    "field_comparison.json": VH / "field_comparison.json",
    "field_investigation.json": VH / "field_investigation.json",
    "field_investigation_gemini_trace.json": VH / "field_investigation_gemini_trace.json",
}
IMAGES = {name: VH / name for name in (
    "five_fields_comparison.png", "selected_field_comparison.png",
    "event_timeline.png", "cross_field_change_comparison.png")}


def run() -> None:
    # An isolated worktree can use reviewed static snapshots without copying
    # private science directories. The main checkout refreshes them from exports.
    resolved = {name: source if source.is_file() else PUBLIC / name
                for name, source in FILES.items()}
    loaded = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in resolved.items()}
    if loaded["vh_timeseries.json"].get("status") != "OBSERVED_OPERA_RTC_S1":
        raise RuntimeError("VH time series is not an observed product")
    fields = loaded["fields.geojson"].get("features", [])
    if not fields or any(f.get("properties", {}).get("status") != "AGRICULTURAL_FIELD_CANDIDATE" for f in fields):
        raise RuntimeError("Field candidate GeoJSON is invalid")
    recorded = loaded["recorded_investigation.json"]
    trace = loaded["recorded_trace.json"]
    if not trace.get("trace") or trace.get("investigation_id") != recorded.get("investigation_id"):
        raise RuntimeError("Recorded Gemini trace does not match investigation")
    ledger_ids = {r["evidence_id"] for r in loaded["champi_evidence.json"]["records"]}
    ledger_ids.update(r["evidence_id"] for r in loaded["vh_evidence.json"]["records"])
    if not set(recorded.get("evidence_ids", [])) <= ledger_ids:
        raise RuntimeError("Recorded investigation contains unresolved Evidence IDs")
    comparison = loaded["field_comparison.json"]
    if (comparison.get("status") != "OBSERVED_DESCRIPTIVE_ONLY" or
            len(comparison.get("fields", [])) != 5 or
            comparison.get("pixel_reverification", {}).get("reextracted_field_scene_count") != 30):
        raise RuntimeError("Five-field comparison lacks real pixel QA")
    deterministic = loaded["field_investigation.json"]
    if (deterministic.get("agent_mode") != "deterministic" or
            deterministic.get("parcel_damage_status") != "UNKNOWN" or
            deterministic.get("api_response", {}).get("investigation_id") is None):
        raise RuntimeError("Recorded deterministic investigation is incomplete")
    if loaded["field_investigation_gemini_trace.json"].get("agent_mode") != "gemini":
        raise RuntimeError("Standalone Gemini trace has wrong execution mode")
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for name, source in resolved.items():
        # Do not publish a source manifest or absolute private paths.
        raw = source.read_text(encoding="utf-8")
        if "D:\\" in raw or "C:\\Users\\" in raw:
            raise RuntimeError(f"Private local path in {source.name}")
        if source != PUBLIC / name:
            shutil.copyfile(source, PUBLIC / name)
    for name, original in IMAGES.items():
        source = original if original.is_file() else PUBLIC / name
        if source.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"Invalid verified science image: {name}")
        if source != PUBLIC / name:
            shutil.copyfile(source, PUBLIC / name)
    # The four optional GeoTIFF sources are intentionally Git-ignored. Their
    # already rendered previews must still match tracked science QA metadata when present.
    map_manifest = json.loads((PUBLIC / "nisar_map_manifest.json").read_text(encoding="utf-8"))
    if (map_manifest.get("status") != "SEPARATE_OBSERVATIONS_ONLY" or
            map_manifest.get("verified_typhoon_delta_allowed") is not False or
            len(map_manifest.get("scenes", [])) != 2):
        raise RuntimeError("NISAR map release gate failed")
    qa_path = CHAMPI / "science_qa.json"
    science_path = CHAMPI / "science_manifest.json"
    has_qa = qa_path.is_file() and science_path.is_file()
    qa = json.loads(qa_path.read_text(encoding="utf-8")) if has_qa else None
    science = json.loads(science_path.read_text(encoding="utf-8")) if has_qa else None
    digests = (
        {Path(item["path"]).name: item["sha256"] for item in science["outputs"] if item["path"].endswith(".tif")}
        if science is not None else {}
    )
    for scene in map_manifest["scenes"]:
        period = scene["period"]
        if qa is not None:
            reference = qa["observations"][period]
            if (scene["scene_id"] != reference["scene_id"] or
                    scene["crid"] != reference["crid"] or
                    scene["product_maturity"] != reference["product_maturity"] or
                    scene["source_sha256"] != digests[f"Taixi_{period}_HH_HV_db.tif"]):
                raise RuntimeError("NISAR map source provenance mismatch")
        for pol in ("HH", "HV"):
            layer = scene["layers"][pol]
            if qa is not None and layer["valid_pixels"] != qa["observations"][period]["valid_pixels"]:
                raise RuntimeError("NISAR map valid pixel mismatch")
            path = PUBLIC / layer["image"]
            if path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                raise RuntimeError(f"Invalid NISAR map preview: {path.name}")
    print(f"Published or verified {len(FILES) + len(IMAGES)} studio assets")


if __name__ == "__main__":
    run()
