"""Deterministic GIS coordinate transformation and polygon area measurement."""
from __future__ import annotations

from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from pyproj import Transformer
from shapely import transform as shp_transform
from shapely.geometry import shape

SUPPORTED_CRS = {'EPSG:4326', 'EPSG:3826'}


class TransformPointRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    x: float
    y: float
    from_crs: str = 'EPSG:4326'
    to_crs: str = 'EPSG:3826'


class TransformPointResponse(BaseModel):
    x: float
    y: float
    from_crs: str
    to_crs: str


class MeasureGeometryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: str = Field(min_length=1)
    geometry: dict[str, Any]
    input_crs: str = 'EPSG:4326'
    geometry_source: Literal['USER_DRAWN'] = 'USER_DRAWN'


class MeasureGeometryResponse(BaseModel):
    area_m2: float
    area_ha: float
    perimeter_m: float
    area_crs: str
    geometry_source: Literal['USER_DRAWN']
    measurement_status: Literal['MEASURED_NOT_OFFICIAL']


def transform_point(req: TransformPointRequest) -> TransformPointResponse:
    """Transform a 2D point between supported coordinate reference systems."""
    if req.from_crs not in SUPPORTED_CRS or req.to_crs not in SUPPORTED_CRS:
        raise ValueError(f'Unsupported CRS; expected one of {sorted(SUPPORTED_CRS)}')
    if not (np.isfinite(req.x) and np.isfinite(req.y)):
        raise ValueError('Point coordinates must be finite numbers')
    transformer = Transformer.from_crs(req.from_crs, req.to_crs, always_xy=True)
    tx, ty = transformer.transform(req.x, req.y)
    if not (np.isfinite(tx) and np.isfinite(ty)):
        raise ValueError('Transformed coordinates are non-finite')
    return TransformPointResponse(x=float(tx), y=float(ty), from_crs=req.from_crs, to_crs=req.to_crs)


def measure_geometry(req: MeasureGeometryRequest) -> MeasureGeometryResponse:
    """Project a WGS84 Polygon/MultiPolygon to TWD97 (EPSG:3826) and compute area/perimeter."""
    if req.input_crs != 'EPSG:4326':
        raise ValueError('input_crs must be EPSG:4326')
    geom = shape(req.geometry)
    if geom.is_empty or geom.geom_type not in {'Polygon', 'MultiPolygon'}:
        raise ValueError('Geometry must be a non-empty Polygon or MultiPolygon')
    if not geom.is_valid:
        raise ValueError('Geometry is topologically invalid (self-intersecting or unclosed)')

    transformer = Transformer.from_crs('EPSG:4326', 'EPSG:3826', always_xy=True)

    def _project(coords: np.ndarray) -> np.ndarray:
        xs, ys = transformer.transform(coords[:, 0], coords[:, 1])
        return np.column_stack([xs, ys])

    projected = shp_transform(geom, _project)
    area_m2 = round(float(projected.area), 2)
    area_ha = round(float(projected.area) / 10000.0, 6)
    perimeter_m = round(float(projected.length), 2)
    return MeasureGeometryResponse(
        area_m2=area_m2,
        area_ha=area_ha,
        perimeter_m=perimeter_m,
        area_crs='EPSG:3826',
        geometry_source='USER_DRAWN',
        measurement_status='MEASURED_NOT_OFFICIAL',
    )
