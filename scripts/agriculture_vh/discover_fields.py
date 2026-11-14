"""Select conservative agricultural candidates from an official farmland SHP ZIP.

Official farmland boundaries do not prove rice cultivation. Visual review of
roads, buildings and fishponds remains required before a candidate is trusted.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

from .common import OUTPUT, ROOT, TAIXI_AOI, write_json

OFFICIAL_SOURCE = "https://data.moa.gov.tw/GetOpenDataFile.aspx?id=I75&FileType=DataMore&RID=44143"
MIN_AREA_M2 = 20_000
INWARD_BUFFER_M = 35
MIN_INTERIOR_PIXEL_ESTIMATE = 8


def locate_source(explicit: Path | None = None) -> Path | None:
    if explicit:
        return explicit if explicit.is_file() else None
    matches = []
    for base in (ROOT / "data" / "raw", ROOT / "data" / "aoi"):
        if base.exists():
            matches.extend(p for p in base.rglob("*") if p.is_file() and
                           p.suffix.lower() in (".zip", ".shp", ".gpkg") and
                           ("農田" in p.name or "farmland" in p.name.lower()))
    return sorted(matches)[0] if matches else None


def try_portal_download(destination: Path) -> Path:
    import requests
    with requests.get(OFFICIAL_SOURCE, stream=True, timeout=(15, 90)) as result:
        result.raise_for_status()
        if not result.url.startswith("https://data.moa.gov.tw/"):
            raise RuntimeError("Official farmland source redirected outside data.moa.gov.tw")
        destination.parent.mkdir(parents=True, exist_ok=True)
        part = destination.with_suffix(".part")
        count = 0
        with part.open("wb") as stream:
            for chunk in result.iter_content(1 << 20):
                count += len(chunk)
                if count > 50_000_000:
                    raise RuntimeError("Farmland download exceeds 50 MB bound")
                stream.write(chunk)
        if not zipfile.is_zipfile(part):
            raise RuntimeError("Farmland response is not a ZIP")
        part.replace(destination)
    return destination


def _read_source(path: Path):
    import geopandas as gpd
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            shp = [name for name in archive.namelist() if name.lower().endswith(".shp")
                   and ".." not in Path(name).parts and not name.startswith("/")]
        if len(shp) != 1:
            raise RuntimeError("ZIP must contain exactly one SHP; choose a specific source")
        return gpd.read_file("zip://" + str(path.resolve()) + "!" + shp[0])
    return gpd.read_file(path)


def discover(source: Path, *, limit: int = 5) -> dict:
    import geopandas as gpd
    from shapely.geometry import mapping
    if not source.is_file():
        raise FileNotFoundError(source)
    frame = _read_source(source)
    if frame.crs is None:
        raise RuntimeError("Farmland source has no declared CRS")
    frame = frame.to_crs("EPSG:4326")
    frame = frame[frame.geometry.notna() & frame.geometry.intersects(TAIXI_AOI)].copy()
    projected = frame.to_crs("EPSG:32651")
    projected_aoi = gpd.GeoSeries([TAIXI_AOI], crs="EPSG:4326").to_crs("EPSG:32651").iloc[0]
    ranked = []
    for original_index, row in projected.iterrows():
        geom = row.geometry
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        # Only the portion within the official township can enter the study.
        geom = geom.intersection(projected_aoi)
        if geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        interior = geom.buffer(-INWARD_BUFFER_M)
        if interior.is_empty or geom.area < MIN_AREA_M2 or interior.area / 900 < MIN_INTERIOR_PIXEL_ESTIMATE:
            continue
        ranked.append((interior.area, original_index, geom, interior))
    ranked.sort(reverse=True, key=lambda item: item[0])
    features = []
    for i, (_, original_index, geom, interior) in enumerate(ranked[:limit], 1):
        geometry = gpd.GeoSeries([geom], crs="EPSG:32651").to_crs("EPSG:4326").iloc[0]
        inside = gpd.GeoSeries([interior], crs="EPSG:32651").to_crs("EPSG:4326").iloc[0]
        features.append({"type": "Feature", "geometry": mapping(geometry), "properties": {
            "field_id": f"YL-CAND-{i:02d}", "status": "AGRICULTURAL_FIELD_CANDIDATE",
            "source_row": str(original_index), "source_file": source.name,
            "area_m2": round(geom.area, 1), "interior_area_m2": round(interior.area, 1),
            "interior_geometry": mapping(inside),
            "selection_basis": "Official farmland boundary; >=2 ha; 35 m inward buffer; >=8 nominal 30 m interior pixels",
            "rice_crop_verified": False, "visual_mixed_land_use_review": "PENDING"}})
    result = {"type": "FeatureCollection", "features": features}
    write_json(OUTPUT / "fields.geojson", result)
    write_json(OUTPUT / "field_candidates.geojson", result)
    return result
