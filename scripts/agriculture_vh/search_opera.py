"""Bounded ASF metadata search; no pixels are downloaded in this stage."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from shapely.geometry import box, shape

from .common import BBOX, OUTPUT, PERIODS, TAIXI_AOI, write_csv, write_json

SCENE_COLUMNS = ["granule_id", "acquisition_datetime", "year", "platform", "relative_orbit",
                 "orbit_direction", "polarization", "product_version", "beam_mode", "burst_id",
                 "product_type", "vh_url", "mask_url", "data_url", "aoi_overlap_ratio",
                 "footprint_geojson"]


def _urls(properties: dict) -> tuple[str | None, str | None]:
    all_urls = [properties.get("url")] + list(properties.get("additionalUrls") or [])
    urls = [u.get("url") or u.get("href") if isinstance(u, dict) else u for u in all_urls]
    urls = [u for u in urls if isinstance(u, str) and u.startswith("https://")]
    vh = next((u for u in urls if re.search(r"_VH\.tiff?(?:\?|$)", u, re.I)), None)
    mask = next((u for u in urls if re.search(r"_mask\.tiff?(?:\?|$)", u, re.I)), None)
    return vh, mask


def normalize_product(product, year: int, aoi) -> dict | None:
    p = product.properties
    scene = str(p.get("fileID") or p.get("sceneName") or "")
    if not scene.startswith("OPERA_L2_RTC-S1_") or not re.search(r"_T\d{3}-\d+-IW[123]_", scene):
        return None
    acquisition = p.get("startTime") or p.get("startDate")
    if not acquisition:
        return None
    time = datetime.fromisoformat(str(acquisition).replace("Z", "+00:00"))
    if time.tzinfo is None:
        time = time.replace(tzinfo=timezone.utc)
    start = datetime.fromisoformat(PERIODS[year][0].replace("Z", "+00:00"))
    end = datetime.fromisoformat(PERIODS[year][1].replace("Z", "+00:00"))
    if not (start <= time <= min(end, datetime.now(timezone.utc))):
        return None
    footprint = product.geometry
    footprint_geom = shape(footprint)
    overlap = footprint_geom.intersection(aoi).area / aoi.area if aoi.area else 0.0
    if overlap <= 0:
        return None
    vh, mask = _urls(p)
    match = re.search(r"_T(\d{3}-\d+-IW[123])_", scene)
    version = re.search(r"_(v\d+\.\d+)(?:_|$)", scene)
    return {"granule_id": scene, "acquisition_datetime": time.isoformat(), "year": year,
            "platform": str(p.get("platform") or ""),
            "relative_orbit": p.get("relativeOrbit") or p.get("pathNumber") or (match.group(1)[:3] if match else ""),
            "orbit_direction": str(p.get("flightDirection") or "").upper(),
            "polarization": str(p.get("polarization") or ""),
            "product_version": version.group(1) if version else "",
            "beam_mode": str(p.get("beamModeType") or p.get("beamMode") or "IW"),
            "burst_id": match.group(1) if match else "",
            "product_type": str(p.get("processingLevel") or "RTC"),
            "vh_url": vh, "mask_url": mask, "data_url": str(p.get("url") or ""),
            "aoi_overlap_ratio": round(overlap, 6), "footprint_geojson": footprint}


def search(*, bbox=BBOX, max_results: int = 1000) -> list[dict]:
    import asf_search as asf
    area = TAIXI_AOI if bbox == BBOX else box(*bbox)
    wkt = area.wkt
    rows: list[dict] = []
    completed_years = []
    for year, (start, end) in PERIODS.items():
        end = min(datetime.fromisoformat(end.replace("Z", "+00:00")),
                  datetime.now(timezone.utc)).isoformat()
        if datetime.fromisoformat(start.replace("Z", "+00:00")) > datetime.fromisoformat(end):
            raise RuntimeError(f"{year} requested season has not begun; future observations are prohibited")
        products = asf.geo_search(dataset=asf.DATASET.OPERA_S1,
                                  processingLevel=asf.PRODUCT_TYPE.RTC,
                                  intersectsWith=wkt, start=start, end=end,
                                  maxResults=max_results)
        if len(products) >= max_results:
            raise RuntimeError(f"{year} ASF search hit max_results={max_results}; inventory would be incomplete")
        rows.extend(row for product in products
                    if (row := normalize_product(product, year, area)) is not None)
        completed_years.append(year)
        rows.sort(key=lambda row: (row["acquisition_datetime"], row["granule_id"]))
        export = [{**row, "footprint_geojson": __import__("json").dumps(row["footprint_geojson"])} for row in rows]
        write_csv(OUTPUT / "scene_inventory.csv", export, SCENE_COLUMNS)
        write_json(OUTPUT / "scene_inventory.json", rows)
        write_json(OUTPUT / "scene_inventory_search_status.json",
                   {"completed_years": completed_years,
                    "status": "COMPLETE" if len(completed_years) == len(PERIODS) else "PARTIAL",
                    "counts": {str(y): sum(r["year"] == y for r in rows) for y in completed_years}})
    return rows


def eligible_scene(row: dict, field_geometry) -> bool:
    has_assets = (row.get("source_collection") == "COPERNICUS/S1_GRD" or
                  (row.get("vh_url") is not None and row.get("mask_url") is not None))
    return (has_assets and
            "VH" in row.get("polarization", "").upper() and
            row.get("orbit_direction") in ("ASCENDING", "DESCENDING") and
            bool(row.get("relative_orbit")) and
            row.get("beam_mode", "").upper().startswith("IW") and
            shape(row["footprint_geojson"]).covers(field_geometry))
