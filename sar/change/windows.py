"""Windowed coordinate transformation and grid compatibility utilities for NISAR L2 GCOV.

Converts WGS84 (`EPSG:4326`) or native projected (`EPSG:32648`, etc.) AOI bounding boxes
and polygons into exact 2D raster slice indices `(row_start, row_stop, col_start, col_stop)`
using the verified NISAR GCOV coordinate vectors (`xCoordinates`, `yCoordinates`) and
10 m spacing, avoiding loading 1.1-billion-pixel full frames into RAM.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import Affine
from shapely.geometry import box, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shp_transform


class GridMismatchError(ValueError):
    """Raised when T0 and T1 GCOV grids do not share compatible CRS, spacing, or coordinates."""


@dataclass(frozen=True)
class GridDefinition:
    """Verified 2D coordinate grid specification for a NISAR Level-2 GCOV frequency group."""

    epsg: int
    width: int
    height: int
    x_spacing_m: float
    y_spacing_m: float
    x_coordinates: np.ndarray  # 1D float64 array of pixel center X coordinates (len = width)
    y_coordinates: np.ndarray  # 1D float64 array of pixel center Y coordinates (len = height)

    @property
    def pixel_area_m2(self) -> float:
        return float(abs(self.x_spacing_m * self.y_spacing_m))

    @property
    def geotransform(self) -> tuple[float, float, float, float, float, float]:
        """GDAL-style 6-element affine geotransform (upper-left corner of pixel (0, 0))."""
        dx = float(self.x_spacing_m)
        dy = float(self.y_spacing_m)
        ulx = float(self.x_coordinates[0]) - 0.5 * dx
        uly = float(self.y_coordinates[0]) - 0.5 * dy
        return (ulx, dx, 0.0, uly, 0.0, dy)

    @property
    def bounds_utm(self) -> tuple[float, float, float, float]:
        """Outer grid bounding box `(min_x, min_y, max_x, max_y)` in native projected meters."""
        dx = abs(float(self.x_spacing_m))
        dy = abs(float(self.y_spacing_m))
        min_x = float(min(self.x_coordinates[0], self.x_coordinates[-1])) - 0.5 * dx
        max_x = float(max(self.x_coordinates[0], self.x_coordinates[-1])) + 0.5 * dx
        min_y = float(min(self.y_coordinates[0], self.y_coordinates[-1])) - 0.5 * dy
        max_y = float(max(self.y_coordinates[0], self.y_coordinates[-1])) + 0.5 * dy
        return (min_x, min_y, max_x, max_y)


@dataclass(frozen=True)
class WindowSlice:
    """Computed 2D raster slice for an AOI query against a `GridDefinition`."""

    row_start: int
    row_stop: int
    col_start: int
    col_stop: int
    requested_bbox_wgs84: tuple[float, float, float, float]
    requested_bbox_utm: tuple[float, float, float, float]
    clipped_bbox_utm: tuple[float, float, float, float] | None
    aoi_geometry_wgs84: dict[str, Any]
    requested_pixel_count: int
    window_pixel_count: int
    fully_outside_grid: bool
    partly_outside_grid: bool
    window_x_coordinates: np.ndarray
    window_y_coordinates: np.ndarray
    window_geotransform: tuple[float, float, float, float, float, float] | None
    polygon_mask: np.ndarray | None  # 2D bool mask (True inside AOI polygon) if non-empty

    @property
    def shape(self) -> tuple[int, int]:
        return (max(0, self.row_stop - self.row_start), max(0, self.col_stop - self.col_start))


def verify_grids_compatible(
    grid_t0: GridDefinition,
    grid_t1: GridDefinition,
    *,
    tol: float = 1e-6,
) -> None:
    """Verify that T0 and T1 share identical CRS, pixel spacing, shape, and coordinate vectors.

    Raises `GridMismatchError` if any grid property is incompatible.
    """
    reasons: list[str] = []
    if int(grid_t0.epsg) != int(grid_t1.epsg):
        reasons.append(f"EPSG mismatch: T0={grid_t0.epsg} vs T1={grid_t1.epsg}.")

    if (
        abs(float(grid_t0.x_spacing_m) - float(grid_t1.x_spacing_m)) > tol
        or abs(float(grid_t0.y_spacing_m) - float(grid_t1.y_spacing_m)) > tol
    ):
        reasons.append(
            f"Pixel spacing mismatch: T0=({grid_t0.x_spacing_m}, {grid_t0.y_spacing_m}) "
            f"vs T1=({grid_t1.x_spacing_m}, {grid_t1.y_spacing_m})."
        )

    if (grid_t0.height, grid_t0.width) != (grid_t1.height, grid_t1.width):
        reasons.append(
            f"Grid shape mismatch: T0=({grid_t0.height}, {grid_t0.width}) "
            f"vs T1=({grid_t1.height}, {grid_t1.width})."
        )
    else:
        if not np.allclose(grid_t0.x_coordinates, grid_t1.x_coordinates, atol=tol, rtol=0.0):
            reasons.append("xCoordinates vectors between T0 and T1 are offset or misaligned.")
        if not np.allclose(grid_t0.y_coordinates, grid_t1.y_coordinates, atol=tol, rtol=0.0):
            reasons.append("yCoordinates vectors between T0 and T1 are offset or misaligned.")

    if reasons:
        raise GridMismatchError("GCOV grid mismatch refused: " + " ".join(reasons))


def _coerce_aoi_geometry(
    aoi: list[float] | tuple[float, ...] | dict[str, Any] | BaseGeometry,
) -> tuple[BaseGeometry, bool]:
    """Convert an AOI specification into a Shapely 2D geometry and a flag indicating if it is a simple bbox."""
    if isinstance(aoi, BaseGeometry):
        geom_2d = shp_transform(lambda x, y, z=None: (x, y), aoi)
        if geom_2d.is_empty or not geom_2d.is_valid:
            raise ValueError("Provided AOI geometry is empty or invalid.")
        return geom_2d, False

    if isinstance(aoi, (list, tuple)) and len(aoi) == 4:
        w, s, e, n = (float(v) for v in aoi)
        if w >= e or s >= n:
            raise ValueError(
                f"Invalid AOI bounding box [{w}, {s}, {e}, {n}]: min must be strictly less than max."
            )
        return box(w, s, e, n), True

    if isinstance(aoi, dict):
        if "type" in aoi and "coordinates" in aoi:
            geom = shape(aoi)
            geom_2d = shp_transform(lambda x, y, z=None: (x, y), geom)
            if geom_2d.is_empty or not geom_2d.is_valid:
                raise ValueError("Provided GeoJSON AOI geometry is empty or invalid.")
            return geom_2d, False
        if "bbox" in aoi and len(aoi["bbox"]) == 4:
            w, s, e, n = (float(v) for v in aoi["bbox"])
            if w >= e or s >= n:
                raise ValueError(f"Invalid AOI bbox {aoi['bbox']}.")
            return box(w, s, e, n), True

    raise ValueError(f"Unsupported AOI specification: {type(aoi)!r}")


def aoi_to_window(
    aoi: list[float] | tuple[float, ...] | dict[str, Any] | BaseGeometry,
    grid: GridDefinition,
    *,
    aoi_crs: str = "EPSG:4326",
) -> WindowSlice:
    """Convert an AOI (in `EPSG:4326` or `grid.epsg`) into a 2D `WindowSlice` on `grid`.

    Handles:
    - AOI fully inside the grid
    - AOI partly outside the grid (clips to valid grid indices and sets `partly_outside_grid=True`)
    - AOI fully outside the grid (returns 0x0 window and sets `fully_outside_grid=True`)
    """
    geom_in, is_simple_bbox = _coerce_aoi_geometry(aoi)
    target_crs = f"EPSG:{grid.epsg}"

    if aoi_crs.upper() == target_crs.upper():
        geom_utm = geom_in
        to_wgs84 = Transformer.from_crs(target_crs, "EPSG:4326", always_xy=True)
        geom_wgs84 = shp_transform(to_wgs84.transform, geom_utm)
    else:
        to_utm = Transformer.from_crs(aoi_crs, target_crs, always_xy=True)
        geom_utm = shp_transform(to_utm.transform, geom_in)
        if aoi_crs.upper() == "EPSG:4326":
            geom_wgs84 = geom_in
        else:
            to_wgs84 = Transformer.from_crs(aoi_crs, "EPSG:4326", always_xy=True)
            geom_wgs84 = shp_transform(to_wgs84.transform, geom_in)

    wgs_bounds = tuple(float(v) for v in geom_wgs84.bounds)  # type: ignore[assignment]
    req_min_x, req_min_y, req_max_x, req_max_y = (float(v) for v in geom_utm.bounds)

    dx = abs(float(grid.x_spacing_m))
    dy = abs(float(grid.y_spacing_m))
    ulx, _, _, uly, _, _ = grid.geotransform
    grid_min_x, grid_min_y, grid_max_x, grid_max_y = grid.bounds_utm

    # Compute unclipped index span to know how many grid pixels the AOI requested
    unclipped_col_start = int(math.floor((req_min_x - ulx) / dx))
    unclipped_col_stop = int(math.ceil((req_max_x - ulx) / dx))
    # Note: yCoordinates in NISAR GCOV decrease from north (row 0, uly) to south (row height, y_spacing < 0)
    if grid.y_spacing_m < 0:
        unclipped_row_start = int(math.floor((uly - req_max_y) / dy))
        unclipped_row_stop = int(math.ceil((uly - req_min_y) / dy))
    else:
        unclipped_row_start = int(math.floor((req_min_y - grid_min_y) / dy))
        unclipped_row_stop = int(math.ceil((req_max_y - grid_min_y) / dy))

    req_rows = max(0, unclipped_row_stop - unclipped_row_start)
    req_cols = max(0, unclipped_col_stop - unclipped_col_start)
    requested_pixel_count = int(req_rows * req_cols)

    # Check if completely disjoint from the grid bounds
    if (
        req_max_x <= grid_min_x
        or req_min_x >= grid_max_x
        or req_max_y <= grid_min_y
        or req_min_y >= grid_max_y
        or unclipped_col_stop <= 0
        or unclipped_col_start >= grid.width
        or unclipped_row_stop <= 0
        or unclipped_row_start >= grid.height
    ):
        return WindowSlice(
            row_start=0,
            row_stop=0,
            col_start=0,
            col_stop=0,
            requested_bbox_wgs84=wgs_bounds,  # type: ignore[arg-type]
            requested_bbox_utm=(req_min_x, req_min_y, req_max_x, req_max_y),
            clipped_bbox_utm=None,
            aoi_geometry_wgs84=mapping(geom_wgs84),
            requested_pixel_count=requested_pixel_count,
            window_pixel_count=0,
            fully_outside_grid=True,
            partly_outside_grid=False,
            window_x_coordinates=np.empty((0,), dtype=np.float64),
            window_y_coordinates=np.empty((0,), dtype=np.float64),
            window_geotransform=None,
            polygon_mask=None,
        )

    col_start = max(0, min(grid.width, unclipped_col_start))
    col_stop = max(0, min(grid.width, unclipped_col_stop))
    row_start = max(0, min(grid.height, unclipped_row_start))
    row_stop = max(0, min(grid.height, unclipped_row_stop))

    if row_stop <= row_start or col_stop <= col_start:
        return WindowSlice(
            row_start=0,
            row_stop=0,
            col_start=0,
            col_stop=0,
            requested_bbox_wgs84=wgs_bounds,  # type: ignore[arg-type]
            requested_bbox_utm=(req_min_x, req_min_y, req_max_x, req_max_y),
            clipped_bbox_utm=None,
            aoi_geometry_wgs84=mapping(geom_wgs84),
            requested_pixel_count=requested_pixel_count,
            window_pixel_count=0,
            fully_outside_grid=True,
            partly_outside_grid=False,
            window_x_coordinates=np.empty((0,), dtype=np.float64),
            window_y_coordinates=np.empty((0,), dtype=np.float64),
            window_geotransform=None,
            polygon_mask=None,
        )

    partly_outside = bool(
        unclipped_row_start < 0
        or unclipped_row_stop > grid.height
        or unclipped_col_start < 0
        or unclipped_col_stop > grid.width
    )

    win_x = grid.x_coordinates[col_start:col_stop].copy()
    win_y = grid.y_coordinates[row_start:row_stop].copy()
    win_ulx = float(win_x[0]) - 0.5 * float(grid.x_spacing_m)
    win_uly = float(win_y[0]) - 0.5 * float(grid.y_spacing_m)
    win_gt = (win_ulx, float(grid.x_spacing_m), 0.0, win_uly, 0.0, float(grid.y_spacing_m))

    clipped_min_x = float(min(win_x[0], win_x[-1])) - 0.5 * dx
    clipped_max_x = float(max(win_x[0], win_x[-1])) + 0.5 * dx
    clipped_min_y = float(min(win_y[0], win_y[-1])) - 0.5 * dy
    clipped_max_y = float(max(win_y[0], win_y[-1])) + 0.5 * dy

    win_h = row_stop - row_start
    win_w = col_stop - col_start
    window_pixel_count = int(win_h * win_w)

    if is_simple_bbox and aoi_crs.upper() == target_crs.upper():
        poly_mask = np.ones((win_h, win_w), dtype=bool)
    elif is_simple_bbox and not partly_outside:
        # Even for a WGS84 bounding box, all pixels in the tightly bounding UTM window represent the bbox
        poly_mask = np.ones((win_h, win_w), dtype=bool)
    else:
        affine = Affine(
            win_gt[1],
            win_gt[2],
            win_gt[0],
            win_gt[4],
            win_gt[5],
            win_gt[3],
        )
        burned = rasterize(
            [(geom_utm, 1)],
            out_shape=(win_h, win_w),
            transform=affine,
            fill=0,
            all_touched=True,
            dtype="uint8",
        )
        poly_mask = burned == 1

    return WindowSlice(
        row_start=row_start,
        row_stop=row_stop,
        col_start=col_start,
        col_stop=col_stop,
        requested_bbox_wgs84=wgs_bounds,  # type: ignore[arg-type]
        requested_bbox_utm=(req_min_x, req_min_y, req_max_x, req_max_y),
        clipped_bbox_utm=(clipped_min_x, clipped_min_y, clipped_max_x, clipped_max_y),
        aoi_geometry_wgs84=mapping(geom_wgs84),
        requested_pixel_count=requested_pixel_count,
        window_pixel_count=window_pixel_count,
        fully_outside_grid=False,
        partly_outside_grid=partly_outside,
        window_x_coordinates=win_x,
        window_y_coordinates=win_y,
        window_geotransform=win_gt,
        polygon_mask=poly_mask,
    )
