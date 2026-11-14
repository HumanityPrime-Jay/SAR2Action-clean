"""Single CLI entry for bounded Yunlin OPERA VH analysis.

Local: python -m scripts.agriculture_vh.run_pipeline --field-source P雲林縣_農田坵塊圖.zip
Colab: run the same command after mounting or uploading the official ZIP.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .common import AOI_SOURCE, BBOX, OUTPUT, PERIODS, ROOT, now_utc, write_json
from .discover_fields import OFFICIAL_SOURCE


def diagnose() -> dict:
    checks = {}
    for hostname in ("odportal.tw", "api.daac.asf.alaska.edu", "urs.earthdata.nasa.gov"):
        try:
            address = socket.getaddrinfo(hostname, 443)[0][4][0]
            dns = {"status": "OK", "address": address}
        except OSError as exc:
            checks[hostname] = {"dns": {"status": "ERROR", "error": repr(exc)},
                                "https": {"status": "NOT_ATTEMPTED"}}
            continue
        try:
            with urlopen("https://" + hostname, timeout=8) as response:
                https = {"status": "OK", "http_status": response.status}
        except HTTPError as exc:
            https = {"status": "REACHABLE_HTTP_ERROR", "http_status": exc.code}
        except (URLError, OSError) as exc:
            https = {"status": "ERROR", "error": repr(exc)}
        checks[hostname] = {"dns": dns, "https": https}
    result = {"checked_at_utc": now_utc(), "checks": checks,
              "proxy_variable_names": [key for key in os.environ if "PROXY" in key.upper()]}
    write_json(OUTPUT / "pipeline_network_diagnostics.json", result)
    return result


def _plot_python(explicit: Path | None) -> Path:
    if explicit:
        return explicit
    if importlib.util.find_spec("matplotlib"):
        return Path(sys.executable)
    fallback = Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python311" / "python.exe"
    if fallback.is_file():
        return fallback
    raise RuntimeError("matplotlib unavailable; install it or pass --plot-python to an environment with matplotlib")


def run(args) -> dict:
    network = diagnose()
    if network["checks"]["api.daac.asf.alaska.edu"]["dns"]["status"] != "OK":
        raise RuntimeError("NETWORK_BLOCKED: ASF DNS unavailable; run the same pipeline in Colab")
    from .discover_fields import discover, locate_source, try_portal_download
    from .search_opera import search
    from .download_opera import download, select_minimum
    from .extract_vh import extract
    from .compare_years import compare
    source = locate_source(args.field_source)
    if source is None:
        source = try_portal_download(ROOT / "data" / "raw" / "P雲林縣_農田坵塊圖.zip")
    fields = discover(source, limit=args.max_fields)
    if not fields["features"]:
        raise RuntimeError("No sufficiently large official farmland polygon in independent study AOI")
    inventory = search()
    selected, first_field = select_minimum(inventory, fields, per_year=3)
    if args.metadata_only:
        result = {"status": "METADATA_ONLY", "inventory_count": len(inventory),
                  "selected_scene_ids": [s["granule_id"] for s in selected], "first_field": first_field,
                  "study_bbox_wgs84": list(BBOX), "source": "NASA OPERA RTC-S1 VH"}
        write_json(OUTPUT / "metadata_search_manifest.json", result)
        return result
    downloads = download(selected, interactive=args.interactive_login)
    observations = extract(downloads, fields)
    stats = compare(observations)
    first_rows = [r for r in observations if r["field_id"] == first_field and
                  "INSUFFICIENT_SPATIAL_SUPPORT" not in r["qa_flags"]]
    if any(sum(r["year"] == year for r in first_rows) < 2 for year in (2025, 2026)):
        raise RuntimeError("Downloaded pixels did not pass minimum two-per-year field QA; no plot published")
    # Draw only fields with sufficient observations; extra candidates are retained in fields.geojson.
    from .plot_timeseries import plot
    if importlib.util.find_spec("matplotlib"):
        plot(first_rows, OUTPUT / "vh_comparison.png")
    else:
        plot_data = {"status": "OBSERVED_OPERA_RTC_S1", "observations": first_rows}
        write_json(OUTPUT / "plot_input.json", plot_data)
        subprocess.run([str(_plot_python(args.plot_python)), str(Path(__file__).with_name("plot_timeseries.py")),
                        str(OUTPUT / "plot_input.json"), str(OUTPUT / "vh_comparison.png")], check=True, timeout=120)
    from backend.app.services.agriculture_vh_evidence import build_evidence
    evidence = build_evidence(observations, stats)
    import hashlib
    qa = {"status": "OBSERVED_OPERA_RTC_S1", "aoi": "Taixi Township",
          "aoi_kind": "OFFICIAL_ADMINISTRATIVE_BOUNDARY_NOT_FIELD",
          "candidate_field_count": len(fields["features"]),
          "field_status": "OFFICIAL_FARMLAND_BOUNDARY_CROP_UNVERIFIED",
          "observed_scene_count": len(downloads), "observed_field_scene_count": len(observations),
          "qa_passing_field_scene_count": sum("INSUFFICIENT_SPATIAL_SUPPORT" not in r["qa_flags"] for r in observations),
          "source_platforms": sorted({r["platform"] for r in observations}),
          "relative_orbits": sorted({str(r["relative_orbit"]) for r in observations}),
          "orbit_directions": sorted({r["orbit_direction"] for r in observations}),
          "product_versions": sorted({r["product_version"] for r in observations}),
          "burst_ids": sorted({r["burst_id"] for r in observations}),
          "radiometric_convention": "OPERA RTC-S1 linear gamma0; positive finite power converted with 10*log10 before pixel statistics",
          "mean_definition": "Arithmetic mean of valid pixel dB values",
          "temporal_interpolation": "NONE", "crop_damage_status": "UNKNOWN",
          "cross_year_baseline_validated": False,
          "source_file_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
          "selected_scene_ids": [r["scene"]["granule_id"] for r in downloads]}
    write_json(OUTPUT / "scientific_qa.json", qa)
    manifest = {"status": "OBSERVED_MINIMUM_PIPELINE", "generated_at_utc": now_utc(),
                "study_bbox_wgs84": list(BBOX), "study_aoi_provenance": "OFFICIAL_NLSC_TAIXI_TOWNSHIP_NOT_FIELD",
                "official_aoi_source": str(AOI_SOURCE.relative_to(ROOT)),
                "field_source": str(source), "field_source_url": OFFICIAL_SOURCE,
                "field_source_sha256": qa["source_file_sha256"], "source": "NASA OPERA RTC-S1 VH",
                "source_product_spec": "https://d2pn8kiwq2w21t.cloudfront.net/documents/ProductSpec_RTC-S1.pdf",
                "periods": PERIODS, "searched_scene_count": {str(y): sum(r["year"] == y for r in inventory) for y in (2025, 2026)},
                "downloaded_scene_count": {str(y): sum(r["scene"]["year"] == y for r in downloads) for y in (2025, 2026)},
                "selected_first_field": first_field, "source_scene_ids": [r["scene"]["granule_id"] for r in downloads],
                "download_manifest": str(ROOT / "data" / "raw" / "opera_yunlin_vh" / "download_manifest.json"),
                "evidence_ids": [r["evidence_id"] for r in observations]}
    write_json(OUTPUT / "source_manifest.json", manifest)
    (OUTPUT / "scientific_limitations.md").write_text(
        "# Observed OPERA VH: scientific limits\n\n"
        "These are agricultural field candidates from official boundaries, not verified rice paddies. "
        "Visual checks for roads, buildings and fishponds and crop records are outstanding. "
        "Three selected dates per year demonstrate a bounded event-centered series, not a validated seasonal baseline. "
        "The selected scenes use one Sentinel-1C platform, orbit, burst, and processing version; incidence-angle effects still require review. "
        "The plot aligns calendar month/day but keeps actual acquisition dates in CSV/JSON. "
        "Harvesting, field preparation, moisture and storm effects cannot be distinguished from VH alone. "
        "No typhoon damage or crop loss is inferred.\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field-source", type=Path, help="Official Yunlin farmland SHP/ZIP/GPKG")
    parser.add_argument("--max-fields", type=int, default=5)
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--interactive-login", action="store_true", help="Let Earthdata prompt locally; never paste credentials into chat")
    parser.add_argument("--plot-python", type=Path)
    args = parser.parse_args()
    try:
        result = run(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        error = {"status": "BLOCKED", "checked_at_utc": now_utc(), "error_type": type(exc).__name__,
                 "error": str(exc), "no_synthetic_observations": True}
        write_json(OUTPUT / "pipeline_error.json", error)
        print(json.dumps(error, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
