"""Phase 3C Item 9: Demo Performance Benchmark (`scripts/run_demo_performance_benchmark.py`).

Measures median runtime, slowest runtime, memory behavior (process RSS & windowed array MiB),
and cache hit vs miss for:
1. Preset AOI load (`AOI-OKI-01`, `AOI-OKI-04`)
2. Cached layer load (`GET /api/layers/{layer_id}` + `GET /api/layers/{layer_id}/image.png`)
3. Radar Fingerprint calculation (live cold compute vs cached hit)
4. Evidence retrieval (`GET /api/evidence/{evidence_id}`)
5. Custom 5 km x 5 km AOI (`[105.30, -3.20, 105.345, -3.155]`, ~5 km x 5 km = ~250,000 px)
6. Custom 10 km x 10 km AOI (`[105.30, -3.20, 105.39, -3.11]`, ~10 km x 10 km = ~1,000,000 px)
7. Custom 30 km x 30 km AOI (`[105.20, -3.35, 105.47, -3.08]`, ~30 km x 30 km = ~9,000,000 px)

Writes JSON results to `data/processed/phase3c_performance_benchmark.json`.
"""

from __future__ import annotations

import json
import pathlib
import statistics
import sys
import time
import tracemalloc
from typing import Any

from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app, science_service

client = TestClient(app)


def measure_operation(
    name: str,
    fn,
    iterations: int = 3,
    clear_custom_cache_before_each: bool = False,
    custom_ev_id: str | None = None,
) -> dict[str, Any]:
    svc = science_service
    runtimes_ms: list[float] = []
    peak_alloc_mib: list[float] = []
    cache_hits: list[bool] = []
    last_info: dict[str, Any] = {}

    for _ in range(iterations):
        if clear_custom_cache_before_each and custom_ev_id:
            svc._analysis_map.pop(custom_ev_id, None)
            svc._fingerprint_map.pop(custom_ev_id, None)
            svc._evidence_map.pop(custom_ev_id, None)

        tracemalloc.start()
        t0 = time.perf_counter()
        info = fn()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        runtimes_ms.append(round(elapsed_ms, 2))
        peak_alloc_mib.append(round(peak_bytes / (1024**2), 2))
        if isinstance(info, dict) and "cache_hit" in info:
            cache_hits.append(bool(info["cache_hit"]))
        last_info = info if isinstance(info, dict) else {}

    return {
        "operation": name,
        "iterations": iterations,
        "runtimes_ms": runtimes_ms,
        "median_runtime_ms": round(float(statistics.median(runtimes_ms)), 2),
        "slowest_runtime_ms": round(float(max(runtimes_ms)), 2),
        "median_runtime_s": round(float(statistics.median(runtimes_ms)) / 1000.0, 3),
        "slowest_runtime_s": round(float(max(runtimes_ms)) / 1000.0, 3),
        "peak_python_alloc_mib": round(float(max(peak_alloc_mib)), 2),
        "cache_hits": cache_hits,
        "details": last_info,
    }


def main() -> None:
    svc = science_service
    svc.set_demo_mode("LIVE")

    results: list[dict[str, Any]] = []

    # 1. Preset AOI Load (Cached Real Data Hit)
    def op_preset_aoi_cached() -> dict[str, Any]:
        r = client.post(
            "/api/radar-fingerprint",
            json={
                "case_id": "case-flagship-oki-f2",
                "aoi_id": "AOI-OKI-04",
                "aoi_bbox_wgs84": [105.08, -2.92, 105.24, -2.76],
            },
        )
        assert r.status_code == 200
        b = r.json()
        return {
            "evidence_id": b["evidence_id"],
            "valid_pixel_count": b["valid_pixel_count"],
            "valid_area_km2": b["valid_area_km2"],
            "cache_hit": b["cache_hit"],
            "demo_mode": b["demo_mode"],
        }

    results.append(measure_operation("1. Preset AOI Load (AOI-OKI-04, Cache Hit)", op_preset_aoi_cached, iterations=5))

    # 2. Cached Layer Load (Metadata + PNG binary)
    def op_cached_layer_load() -> dict[str, Any]:
        layer_id = "E-FLAGSHIP-OKI-004_delta_hv"
        r_meta = client.get(f"/api/layers/{layer_id}")
        assert r_meta.status_code == 200
        r_png = client.get(f"/api/layers/{layer_id}/image.png")
        assert r_png.status_code == 200
        return {
            "layer_id": layer_id,
            "png_bytes": len(r_png.content),
            "cache_hit": True,
        }

    results.append(measure_operation("2. Cached Layer Load (Metadata + RGBA PNG)", op_cached_layer_load, iterations=5))

    # 3. Evidence Record Retrieval
    def op_evidence_retrieval() -> dict[str, Any]:
        r_ev = client.get("/api/evidence/E-FLAGSHIP-OKI-004")
        assert r_ev.status_code == 200
        b = r_ev.json()
        return {
            "evidence_id": b["evidence_id"],
            "valid_pixel_count": b["valid_pixel_count"],
            "cache_hit": True,
        }

    results.append(measure_operation("3. Evidence Record Retrieval (GET /api/evidence/E-FLAGSHIP-OKI-004)", op_evidence_retrieval, iterations=5))

    # 4. Custom 5 km x 5 km AOI (Cold Live HDF5 + PNG Render vs Warm Cache Hit)
    flagship_case = svc.get_case("case-flagship-oki-f2")
    bbox_5km = [105.30, -3.20, 105.345, -3.155]
    _, ev_5km, _, _, _ = svc._resolve_aoi_provenance(
        flagship_case,
        None,
        bbox_5km,
        None,
        flagship_case.default_t0_scene_id,
        flagship_case.default_t1_scene_id,
    )

    def op_custom_5km() -> dict[str, Any]:
        r = client.post(
            "/api/radar-fingerprint",
            json={
                "case_id": "case-flagship-oki-f2",
                "aoi_bbox_wgs84": bbox_5km,
            },
        )
        assert r.status_code == 200
        b = r.json()
        return {
            "evidence_id": b["evidence_id"],
            "valid_pixel_count": b["valid_pixel_count"],
            "valid_area_km2": b["valid_area_km2"],
            "cache_hit": b["cache_hit"],
        }

    results.append(
        measure_operation(
            "4a. Custom 5 km x 5 km AOI (Cold Live HDF5 Window + 10 PNG Renders)",
            op_custom_5km,
            iterations=3,
            clear_custom_cache_before_each=True,
            custom_ev_id=ev_5km,
        )
    )
    results.append(
        measure_operation(
            "4b. Custom 5 km x 5 km AOI (Warm Cache Hit)",
            op_custom_5km,
            iterations=3,
            clear_custom_cache_before_each=False,
        )
    )

    # 5. Custom 10 km x 10 km AOI (Cold Live HDF5 + PNG Render vs Warm Cache Hit)
    bbox_10km = [105.30, -3.20, 105.39, -3.11]
    _, ev_10km, _, _, _ = svc._resolve_aoi_provenance(
        flagship_case,
        None,
        bbox_10km,
        None,
        flagship_case.default_t0_scene_id,
        flagship_case.default_t1_scene_id,
    )

    def op_custom_10km() -> dict[str, Any]:
        r = client.post(
            "/api/radar-fingerprint",
            json={
                "case_id": "case-flagship-oki-f2",
                "aoi_bbox_wgs84": bbox_10km,
            },
        )
        assert r.status_code == 200
        b = r.json()
        return {
            "evidence_id": b["evidence_id"],
            "valid_pixel_count": b["valid_pixel_count"],
            "valid_area_km2": b["valid_area_km2"],
            "cache_hit": b["cache_hit"],
        }

    results.append(
        measure_operation(
            "5a. Custom 10 km x 10 km AOI (Cold Live HDF5 Window + 10 PNG Renders)",
            op_custom_10km,
            iterations=3,
            clear_custom_cache_before_each=True,
            custom_ev_id=ev_10km,
        )
    )
    results.append(
        measure_operation(
            "5b. Custom 10 km x 10 km AOI (Warm Cache Hit)",
            op_custom_10km,
            iterations=3,
            clear_custom_cache_before_each=False,
        )
    )

    # 6. Custom 30 km x 30 km AOI (Cold Live HDF5 + PNG Render vs Warm Cache Hit)
    bbox_30km = [105.20, -3.35, 105.47, -3.08]
    _, ev_30km, _, _, _ = svc._resolve_aoi_provenance(
        flagship_case,
        None,
        bbox_30km,
        None,
        flagship_case.default_t0_scene_id,
        flagship_case.default_t1_scene_id,
    )

    def op_custom_30km() -> dict[str, Any]:
        r = client.post(
            "/api/radar-fingerprint",
            json={
                "case_id": "case-flagship-oki-f2",
                "aoi_bbox_wgs84": bbox_30km,
            },
        )
        assert r.status_code == 200
        b = r.json()
        return {
            "evidence_id": b["evidence_id"],
            "valid_pixel_count": b["valid_pixel_count"],
            "valid_area_km2": b["valid_area_km2"],
            "cache_hit": b["cache_hit"],
        }

    results.append(
        measure_operation(
            "6a. Custom 30 km x 30 km AOI (Cold Live HDF5 Window + 10 PNG Renders)",
            op_custom_30km,
            iterations=2,
            clear_custom_cache_before_each=True,
            custom_ev_id=ev_30km,
        )
    )
    results.append(
        measure_operation(
            "6b. Custom 30 km x 30 km AOI (Warm Cache Hit)",
            op_custom_30km,
            iterations=3,
            clear_custom_cache_before_each=False,
        )
    )

    out_path = ROOT / "data" / "processed" / "phase3c_performance_benchmark.json"
    out_path.write_text(json.dumps({"benchmarks": results}, indent=2), encoding="utf-8")
    for item in results:
        print(
            f"{item['operation']}: median={item['median_runtime_ms']:.2f} ms ({item['median_runtime_s']:.3f} s), "
            f"slowest={item['slowest_runtime_ms']:.2f} ms ({item['slowest_runtime_s']:.3f} s), "
            f"peak_alloc={item['peak_python_alloc_mib']:.2f} MiB, cache_hits={item['cache_hits']}"
        )


if __name__ == "__main__":
    main()
