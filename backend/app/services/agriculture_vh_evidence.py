"""Read-only deterministic VH tools for the existing Scientific Agent surface.

No model generates pixel measurements. Every returned number must resolve to a
recorded OPERA scene, field and source raster digest.
"""
from __future__ import annotations

import json
import hashlib
from datetime import datetime

from scripts.agriculture_vh.common import OUTPUT, RASTER_DIR, ROOT, resolve_raster_path, write_json
from scripts.agriculture_vh.compare_years import EVENT_END, EVENT_START, compare

TOOL_NAMES = {"get_field_vh_timeseries", "compare_seasonal_backscatter",
              "check_event_temporal_alignment", "evaluate_field_hypotheses",
              "find_missing_observations", "calculate_temporal_changes", "compare_five_fields"}


def active_output():
    """Prefer verified OPERA artifacts; use separately recorded EE fallback only if absent."""
    primary = OUTPUT / "vh_timeseries.json"
    if primary.is_file():
        data = json.loads(primary.read_text(encoding="utf-8"))
        if data.get("status") == "OBSERVED_OPERA_RTC_S1":
            return OUTPUT
    fallback = OUTPUT / "gee_fallback"
    if (fallback / "vh_timeseries.json").is_file():
        data = json.loads((fallback / "vh_timeseries.json").read_text(encoding="utf-8"))
        if data.get("status") == "OBSERVED_EE_S1_GRD":
            return fallback
    raise RuntimeError("No observed Sentinel-1 VH evidence; result is UNKNOWN")


def build_evidence(observations: list[dict], statistics: dict) -> dict:
    records = [{"evidence_id": r["evidence_id"], "field_id": r["field_id"],
                "acquisition_datetime": r["acquisition_datetime"], "source_scene_id": r["source_scene_id"],
                "source_vh_sha256": r["source_vh_sha256"], "polarization": "VH",
                "frequency_band": "C", "product": "OPERA RTC-S1", "platform": r["platform"],
                "relative_orbit": r["relative_orbit"], "orbit_direction": r["orbit_direction"],
                "vh_median_db": r["vh_median_db"], "valid_pixel_count": r["valid_pixel_count"],
                "qa_flags": r["qa_flags"]} for r in observations]
    if len({r["evidence_id"] for r in records}) != len(records):
        raise RuntimeError("Duplicate field-scene Evidence ID")
    result = {"schema_version": "yunlin-vh-evidence-v2", "status": "OBSERVED_OPERA_RTC_S1",
              "field_status": "AGRICULTURAL_FIELD_CANDIDATE", "rice_crop_verified": False,
              "records": records, "statistics_status": statistics["status"],
              "causal_damage_status": "UNKNOWN"}
    write_json(OUTPUT / "agent_evidence.json", result)
    return result


def _read() -> tuple[list[dict], dict]:
    base = active_output()
    timeseries = json.loads((base / "vh_timeseries.json").read_text(encoding="utf-8"))
    evidence = json.loads((base / "agent_evidence.json").read_text(encoding="utf-8"))
    if timeseries.get("status") != evidence.get("status"):
        raise RuntimeError("VH time series and Evidence source modes differ")
    observations = timeseries["observations"]
    manifest = json.loads((base / "source_manifest.json").read_text(encoding="utf-8"))
    indexed = {r["evidence_id"]: r for r in evidence["records"]}
    if len(indexed) != len(evidence["records"]) or len(indexed) != len(observations):
        raise RuntimeError("Evidence inventory size mismatch")
    if base != OUTPUT:
        if manifest.get("status") != "OBSERVED_EE_S1_GRD":
            raise RuntimeError("Earth Engine source manifest is unavailable")
        scenes = {r["asset_id"] for r in json.loads((base / "scene_inventory.json").read_text(encoding="utf-8"))}
        for row in observations:
            record = indexed.get(row["evidence_id"])
            expected = "E-YL-GEE-VH-" + hashlib.sha256((row["field_id"] + "|" + row["source_asset_id"])
                                                    .encode()).hexdigest()[:16].upper()
            if (record is None or row["evidence_id"] != expected or row["source_asset_id"] not in scenes
                    or record.get("source_asset_id") != row["source_asset_id"]
                    or record.get("vh_median_db") != row["vh_median_db"]
                    or row.get("source_collection") != "COPERNICUS/S1_GRD"):
                raise RuntimeError("Earth Engine Evidence does not match source asset inventory")
        return observations, evidence
    downloads = json.loads((RASTER_DIR / "download_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "OBSERVED_MINIMUM_PIPELINE" or not downloads:
        raise RuntimeError("Observed VH source manifest is unavailable")
    source_files = {item["scene"]["granule_id"]: item["files"]["vh"] for item in downloads}
    for item in downloads:
        for layer in ("vh", "mask"):
            record = item["files"][layer]
            if hashlib.sha256(resolve_raster_path(record["path"]).read_bytes()).hexdigest() != record["sha256"]:
                raise RuntimeError("OPERA source COG digest mismatch")
    for row in observations:
        record = indexed.get(row["evidence_id"])
        expected_id = "E-YL-VH-" + hashlib.sha256((row["field_id"] + "|" + row["source_scene_id"]
                            + "|" + row["source_vh_sha256"]).encode()).hexdigest()[:16].upper()
        if (record is None or source_files.get(row["source_scene_id"], {}).get("sha256") != row["source_vh_sha256"]
                or record["source_scene_id"] != row["source_scene_id"]
                or record["source_vh_sha256"] != row["source_vh_sha256"]
                or record["vh_median_db"] != row["vh_median_db"]
                or row["evidence_id"] != expected_id):
            raise RuntimeError("Evidence does not match source observation")
    if set(manifest.get("evidence_ids", [])) != set(indexed):
        raise RuntimeError("Source manifest Evidence IDs do not match observations")
    return observations, evidence


def get_field_vh_timeseries(field_id: str | None = None) -> dict:
    rows, _ = _read()
    selected = [r for r in rows if field_id is None or r["field_id"] == field_id]
    return {"status": "OBSERVED" if selected else "UNKNOWN", "field_id": field_id,
            "observations": selected, "evidence_ids": [r["evidence_id"] for r in selected]}


def compare_seasonal_backscatter(field_id: str | None = None) -> dict:
    rows, _ = _read()
    selected = [r for r in rows if field_id is None or r["field_id"] == field_id]
    stats = compare(selected, persist=False)
    return {"status": stats["status"], "date_pair_tolerance_days": stats["date_pair_tolerance_days"],
            "fields": stats["fields"], "evidence_ids": [r["evidence_id"] for r in selected],
            "causation": "UNKNOWN"}


def check_event_temporal_alignment(field_id: str | None = None) -> dict:
    rows, _ = _read()
    start = datetime.fromisoformat(EVENT_START)
    end = datetime.fromisoformat(EVENT_END)
    selected = [r for r in rows if r["year"] == 2026 and
                "INSUFFICIENT_SPATIAL_SUPPORT" not in r["qa_flags"] and
                (field_id is None or r["field_id"] == field_id)]
    before = [r for r in selected if datetime.fromisoformat(r["acquisition_datetime"]) < start]
    during = [r for r in selected if start <= datetime.fromisoformat(r["acquisition_datetime"]) <= end]
    after = [r for r in selected if datetime.fromisoformat(r["acquisition_datetime"]) > end]
    return {"status": "OBSERVED_TEMPORAL_BRACKETING" if before and after else "UNKNOWN",
            "event_window_local": [EVENT_START, EVENT_END],
            "pre_event": [{"date": r["acquisition_datetime"], "evidence_id": r["evidence_id"]} for r in before],
            "warning_window": [{"date": r["acquisition_datetime"], "evidence_id": r["evidence_id"]} for r in during],
            "post_event": [{"date": r["acquisition_datetime"], "evidence_id": r["evidence_id"]} for r in after],
            "strict_pre_warning_change_available": len(before) >= 2,
            "evidence_ids": [r["evidence_id"] for r in selected],
            "causation": "UNKNOWN"}


def evaluate_field_hypotheses(field_id: str | None = None) -> dict:
    alignment = check_event_temporal_alignment(field_id)
    return {"status": "UNKNOWN", "field_id": field_id,
            "hypotheses": {name: "UNRESOLVED" for name in
                           ("harvesting", "field_preparation", "moisture", "storm_disturbance", "processing_geometry")},
            "temporal_evidence_ids": [r["evidence_id"] for r in
                                       alignment["pre_event"] + alignment["warning_window"] + alignment["post_event"]],
            "evidence_ids": alignment["evidence_ids"],
            "needed": ["Field planting and harvest records", "Field survey or optical imagery",
                       "Incidence angle and cross-platform calibration review"]}


def find_missing_observations(field_id: str | None = None) -> dict:
    rows, _ = _read()
    selected = [r for r in rows if field_id is None or r["field_id"] == field_id]
    counts = {year: sum(r["year"] == year and
                        "INSUFFICIENT_SPATIAL_SUPPORT" not in r["qa_flags"] for r in selected)
              for year in (2025, 2026)}
    return {"status": "INCOMPLETE" if any(v < 2 for v in counts.values()) else "MINIMUM_PIPELINE_ONLY",
            "qa_passing_counts": counts,
            "evidence_ids": [r["evidence_id"] for r in selected],
            "missing": [f"{year} needs at least two QA-passing field observations" for year, count in counts.items() if count < 2] +
                       ["Only one 2026 pre-warning observation; no pre-warning time-series change",
                        "Rice crop records", "Independent harvest and event evidence"]}


def _field_comparison() -> dict:
    if active_output() != OUTPUT:
        raise RuntimeError('Five-field raster re-verification is available for OPERA only')
    path = OUTPUT / 'field_comparison.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    csv_path = OUTPUT / 'vh_timeseries.csv'
    if hashlib.sha256(csv_path.read_bytes()).hexdigest() != data.get('input_csv_sha256'):
        raise RuntimeError('Five-field comparison does not match the current CSV')
    rows, _ = _read()
    from scripts.agriculture_vh.analyze_five_fields import _csv_rows, build_comparison, FIELDS_PATH
    csv_rows = _csv_rows()
    by_id = {r['evidence_id']: r for r in rows}
    if len(csv_rows) != len(rows) or any(
            csv_row['evidence_id'] not in by_id or
            csv_row['vh_median_db'] != by_id[csv_row['evidence_id']]['vh_median_db'] or
            csv_row['valid_pixel_count'] != by_id[csv_row['evidence_id']]['valid_pixel_count']
            for csv_row in csv_rows):
        raise RuntimeError('Five-field CSV does not match observed Evidence rows')
    features = json.loads(FIELDS_PATH.read_text(encoding='utf-8'))['features']
    recalculated = build_comparison(csv_rows, features, data['input_csv_sha256'])
    if (recalculated['fields'] != data.get('fields') or
            recalculated['cross_field_pattern'] != data.get('cross_field_pattern') or
            recalculated['event_reference'] != data.get('event_reference')):
        raise RuntimeError('Five-field comparison differs from deterministic CSV calculation')
    observed_ids = {r['evidence_id'] for r in rows}
    comparison_ids = {id for f in data.get('fields', []) for id in f.get('evidence_ids', [])}
    rechecked_ids = set(data.get('pixel_reverification', {}).get('evidence_ids', []))
    if (data.get('status') != 'OBSERVED_DESCRIPTIVE_ONLY' or
            data.get('pixel_reverification', {}).get('status') != 'PASS' or
            observed_ids != comparison_ids or observed_ids != rechecked_ids or len(data['fields']) != 5):
        raise RuntimeError('Five-field comparison Evidence or pixel QA is incomplete')
    return data


def calculate_temporal_changes(field_id: str | None = None) -> dict:
    data = _field_comparison()
    selected = next((f for f in data['fields'] if f['field_id'] == field_id), None)
    if selected is None:
        return {'status': 'UNKNOWN', 'field_id': field_id, 'evidence_ids': []}
    return {'status': 'OBSERVED_DESCRIPTIVE_ONLY', 'field_id': field_id,
            '2026_pre_warning_change': selected['2026_pre_warning_change'],
            '2026_pre_warning_status': selected['2026_pre_warning_status'],
            '2026_pre_to_warning_window': selected['2026_pre_to_warning_window'],
            '2026_pre_to_post_warning': selected['2026_pre_to_post_warning'],
            '2026_warning_to_post_warning': selected['2026_warning_to_post_warning'],
            '2025_early_to_middle': selected['2025_early_to_middle'],
            'cross_year_early_to_middle_change_difference_db':
                selected['cross_year_early_to_middle_change_difference_db'],
            'event_reference': data['event_reference'], 'source': data['source'],
            'evidence_ids': selected['evidence_ids'], 'causation': 'UNKNOWN'}


def compare_five_fields(field_id: str | None = None) -> dict:
    data = _field_comparison()
    return {'status': data['status'], 'selected_field_id': field_id,
            'fields': data['fields'], 'cross_field_pattern': data['cross_field_pattern'],
            'event_reference': data['event_reference'], 'scientific_limits': data['scientific_limits'],
            'source': data['source'], 'input_csv_sha256': data['input_csv_sha256'],
            'pixel_reverification': data['pixel_reverification'],
            'evidence_ids': [id for f in data['fields'] for id in f['evidence_ids']],
            'causation': 'UNKNOWN'}


def run_tool(name: str, field_id: str | None = None) -> dict:
    if name not in TOOL_NAMES:
        raise ValueError("Unknown agriculture VH tool")
    try:
        return globals()[name](field_id)
    except (FileNotFoundError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        return {"status": "UNKNOWN", "tool": name, "field_id": field_id,
                "reason": str(exc), "evidence_ids": []}
