"""Stateless GIS endpoints for user-supplied geometry."""
from math import isfinite
from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, FiniteFloat, ValidationError
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform
from shapely.validation import explain_validity

router = APIRouter(prefix="/api/gis", tags=["GIS"])
WGS84, TWD97 = "EPSG:4326", "EPSG:3826"
Crs = Literal["EPSG:4326", "EPSG:3826"]
Case = Literal["CHAMPI-YUNLIN-TAIXI", "TW-05-YUNLIN-AGRO"]
MAX_BODY = 128 * 1024
MAX_VERTICES = 2_000
# Regional guard for this Yunlin service, independent of satellite footprints.
WEST, SOUTH, EAST, NORTH = 119.9, 23.4, 121.0, 24.0
FORWARD = Transformer.from_crs(WGS84, TWD97, always_xy=True)
INVERSE = Transformer.from_crs(TWD97, WGS84, always_xy=True)


class MeasureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: Case
    geometry: dict
    input_crs: Crs = WGS84
    geometry_source: Literal["USER_DRAWN"] = "USER_DRAWN"


class PointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    x: FiniteFloat
    y: FiniteFloat
    from_crs: Crs
    to_crs: Crs


def reject(message: str) -> None:
    raise HTTPException(422, detail=message)


def to_lonlat(x: float, y: float, crs: Crs) -> tuple[float, float]:
    if crs == TWD97:
        x, y = INVERSE.transform(x, y)
    if not WEST <= x <= EAST or not SOUTH <= y <= NORTH:
        reject("Coordinates must be within the supported Yunlin region.")
    return x, y


def validate_geometry(geometry: dict, crs: Crs) -> None:
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if kind not in ("Polygon", "MultiPolygon") or not isinstance(coordinates, list):
        reject("Expected a Polygon or MultiPolygon with coordinates.")
    polygons = [coordinates] if kind == "Polygon" else coordinates
    count = 0
    if not polygons:
        reject("Empty geometry.")
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            reject("Each polygon must have an exterior ring.")
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]:
                reject("Every ring must be closed and contain at least four positions.")
            count += len(ring)
            if count > MAX_VERTICES:
                reject(f"Geometry exceeds {MAX_VERTICES} positions.")
            for pair in ring:
                if (not isinstance(pair, list) or len(pair) != 2
                        or any(type(v) not in (float, int) or abs(v) > 1e8 or not isfinite(v) for v in pair)):
                    reject("Each position must contain two finite numeric coordinates.")
                to_lonlat(*pair, crs)


@router.post("/transform-point")
@router.post("/transform")
def transform_point(point: PointRequest):
    lon, lat = to_lonlat(point.x, point.y, point.from_crs)
    x, y = FORWARD.transform(lon, lat) if point.to_crs == TWD97 else (lon, lat)
    return {
        "x": x, "y": y, "axis_order": "longitude,latitude" if point.to_crs == WGS84 else "easting,northing",
        "crs": point.to_crs, "conversion_method": "pyproj Transformer(always_xy=True)",
    }


@router.post("/measure", openapi_extra={
    "requestBody": {"required": True, "content": {"application/json": {"schema": MeasureRequest.model_json_schema()}}},
})
async def measure(request: Request):
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY:
            raise HTTPException(413, detail="Geometry request exceeds 128 KiB.")
        body.extend(chunk)
    try:
        payload = MeasureRequest.model_validate_json(body)
    except ValidationError:
        reject("Invalid measurement request. Only user-drawn Polygon/MultiPolygon is supported.")
    validate_geometry(payload.geometry, payload.input_crs)
    original = shape(payload.geometry)
    if original.is_empty or not original.is_valid:
        reject(f"Invalid geometry: {explain_validity(original)}")
    projected = transform(FORWARD.transform, original) if payload.input_crs == WGS84 else original
    if not projected.is_valid or not 1 <= projected.area <= 1e8:
        reject("Projected geometry must be valid and have an area between 1 and 100,000,000 m².")
    return {
        "geometry_id": str(uuid4()), "case_id": payload.case_id, "input_crs": payload.input_crs,
        "geometry_source": "USER_DRAWN", "area_crs": TWD97, "geometry_valid": True,
        "area_m2": projected.area, "area_ha": projected.area / 10_000, "perimeter_m": projected.length,
        "measurement_status": "MEASURED_NOT_OFFICIAL", "parcel_feature_id": None,
        "satellite_statistics_status": "NO_REGISTERED_SATELLITE_STATISTICS",
        "official_cadastral_area_m2": None, "assumed_approved_area_ha": None,
        "warnings": ["User-drawn projected area only. Official cadastral and approved relief areas are unknown."],
    }
