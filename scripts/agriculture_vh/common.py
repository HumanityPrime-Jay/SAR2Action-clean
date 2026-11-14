from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import os
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.environ.get("SAR2ACTION_DATA_ROOT") or (ROOT / "data")).resolve()
OUTPUT = DATA_ROOT / "exports" / "yunlin_vh_2025_2026"
RASTER_DIR = DATA_ROOT / "raw" / "opera_yunlin_vh"
AOI_SOURCE = DATA_ROOT / "exports" / "typhoon_champi" / "candidate_aois.geojson"
if not AOI_SOURCE.is_file():
    AOI_SOURCE = ROOT / "data" / "exports" / "typhoon_champi" / "candidate_aois.geojson"
if not AOI_SOURCE.is_file():
    raise RuntimeError("Official Taixi AOI GeoJSON is required for VH analysis")
_aoi_features = json.loads(AOI_SOURCE.read_text(encoding="utf-8"))["features"]
_taixi = [f for f in _aoi_features if f["properties"].get("township_name") == "Taixi Township"
          and f["properties"].get("boundary_kind") == "ADMINISTRATIVE_TOWNSHIP_NOT_FIELD"]
if len(_taixi) != 1:
    raise RuntimeError("Expected exactly one official Taixi township feature")
TAIXI_AOI = shape(_taixi[0]["geometry"])
BBOX = tuple(TAIXI_AOI.bounds)
PERIODS = {2025: ("2025-08-01T00:00:00Z", "2025-11-14T23:59:59Z"),
           2026: ("2026-08-01T00:00:00Z", "2026-11-14T23:59:59Z")}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temp.replace(path)


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_raster_path(raw_path: str | Path) -> Path:
    """Resolve manifest raster paths under the active RASTER_DIR."""
    candidate = RASTER_DIR / Path(str(raw_path).replace("\\", "/")).name
    if candidate.is_file():
        return candidate
    return Path(raw_path)
