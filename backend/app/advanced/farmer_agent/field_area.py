"""Geodesic GIS Field Area Engine (Phase 3) — pure Python WGS84 equal-area calculation."""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
WGS84_AUTHALIC_RADIUS_M = 6371007.181
SQ_M_PER_HA = 10000.0
SQ_M_PER_FEN = 969.917  # Taiwan 1 分地 ≈ 969.917 m² (0.0969917 ha)


@dataclass
class FieldAreaResult:
    status: str  # "CALCULATED" | "INVALID_GEOMETRY" | "NOT_FOUND"
    field_id: str | None
    area_m2: float | None
    area_ha: float | None
    area_fen: float | None
    ownership_verified: bool = False
    is_valid: bool = True
    warnings: list[str] = field(default_factory=list)
    source: str = "WGS84_GEODESIC_SPHERICAL_EXCESS"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _segments_intersect(p1: list[float], p2: list[float], p3: list[float], p4: list[float]) -> bool:
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)


def validate_ring(ring: list[list[float]]) -> tuple[bool, str | None]:
    if not isinstance(ring, list) or len(ring) < 4:
        return False, "Polygon ring must have at least 4 coordinates."
    for pt in ring:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            return False, "Each coordinate must be [lon, lat]."
        lon, lat = float(pt[0]), float(pt[1])
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            return False, f"Coordinate out of WGS84 bounds: [{lon}, {lat}]"

    closed = list(ring)
    if closed[0] != closed[-1]:
        closed.append(closed[0])

    n = len(closed) - 1
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _segments_intersect(closed[i], closed[i + 1], closed[j], closed[j + 1]):
                return False, "Polygon has self-intersecting edges."
    return True, None


def geodesic_ring_area_m2(ring: list[list[float]]) -> float:
    """Compute geodesic polygon area on WGS84 sphere (Chamberlain-Duquette algorithm)."""
    pts = list(ring)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    if len(pts) < 4:
        return 0.0
    total = 0.0
    n = len(pts) - 1
    for i in range(n):
        lon1 = math.radians(pts[i][0])
        lat1 = math.radians(pts[i][1])
        lon2 = math.radians(pts[i + 1][0])
        lat2 = math.radians(pts[i + 1][1])
        total += (lon2 - lon1) * (2.0 + math.sin(lat1) + math.sin(lat2))
    area = abs(total * (WGS84_AUTHALIC_RADIUS_M ** 2) / 2.0)
    return round(area, 2)


def _point_in_ring(pt: list[float], ring: list[list[float]]) -> bool:
    x, y = pt[0], pt[1]
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-15) + xi):
            inside = not inside
        j = i
    return inside


def _bbox_of_ring(ring: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


class FarmerFieldService:
    """Manage official farmland candidate lookup, user polygons, and geodesic areas."""

    def __init__(self, data_root: Path | None = None):
        self.data_root = data_root or ROOT

    def _load_candidate_features(self) -> list[dict[str, Any]]:
        path = self.data_root / "data" / "exports" / "yunlin_vh_2025_2026" / "fields.geojson"
        if not path.is_file():
            return []
        return json.loads(path.read_text(encoding="utf-8")).get("features", [])

    def get_field_geometry(self, field_id: str) -> dict[str, Any] | None:
        for feat in self._load_candidate_features():
            if feat.get("properties", {}).get("field_id") == field_id:
                return feat
        return None

    def calculate_field_area(
        self,
        *,
        field_id: str | None = None,
        geojson_geometry: dict[str, Any] | None = None,
    ) -> FieldAreaResult:
        if geojson_geometry is not None:
            gtype = geojson_geometry.get("type")
            coords = geojson_geometry.get("coordinates") or []
            if gtype == "Polygon" and coords:
                outer = coords[0]
                ok, err = validate_ring(outer)
                if not ok:
                    return FieldAreaResult("INVALID_GEOMETRY", field_id, None, None, None, is_valid=False, warnings=[err or "Invalid polygon"])
                area_m2 = geodesic_ring_area_m2(outer)
                for hole in coords[1:]:
                    area_m2 = max(0.0, area_m2 - geodesic_ring_area_m2(hole))
                return FieldAreaResult(
                    status="CALCULATED",
                    field_id=field_id,
                    area_m2=round(area_m2, 2),
                    area_ha=round(area_m2 / SQ_M_PER_HA, 4),
                    area_fen=round(area_m2 / SQ_M_PER_FEN, 3),
                    ownership_verified=False,
                    warnings=["User-drawn geometry area calculated; official land ownership is not verified."],
                )
            if gtype == "MultiPolygon" and coords:
                total = 0.0
                for poly in coords:
                    ok, err = validate_ring(poly[0])
                    if not ok:
                        return FieldAreaResult("INVALID_GEOMETRY", field_id, None, None, None, is_valid=False, warnings=[err or "Invalid multipolygon"])
                    total += geodesic_ring_area_m2(poly[0])
                return FieldAreaResult(
                    status="CALCULATED",
                    field_id=field_id,
                    area_m2=round(total, 2),
                    area_ha=round(total / SQ_M_PER_HA, 4),
                    area_fen=round(total / SQ_M_PER_FEN, 3),
                    ownership_verified=False,
                )
            return FieldAreaResult("INVALID_GEOMETRY", field_id, None, None, None, is_valid=False, warnings=["Unsupported GeoJSON geometry type."])

        if field_id:
            feat = self.get_field_geometry(field_id)
            if feat:
                res = self.calculate_field_area(field_id=field_id, geojson_geometry=feat["geometry"])
                res.warnings = [
                    "Official farmland candidate polygon only; does NOT establish user land ownership or cultivation right."
                ]
                return res
        return FieldAreaResult("NOT_FOUND", field_id, None, None, None, is_valid=False, warnings=["Field geometry not found."])

    def calculate_reported_damage_area(
        self,
        field_geometry: dict[str, Any],
        damage_geometry: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute intersection area between field boundary and farmer-drawn damage polygon."""
        f_ring = (field_geometry.get("coordinates") or [[]])[0]
        d_ring = (damage_geometry.get("coordinates") or [[]])[0]
        ok_f, err_f = validate_ring(f_ring)
        ok_d, err_d = validate_ring(d_ring)
        if not ok_f or not ok_d:
            return {"status": "INVALID_GEOMETRY", "error": err_f or err_d, "affected_area_m2": None}

        field_area_m2 = geodesic_ring_area_m2(f_ring)
        damage_raw_m2 = geodesic_ring_area_m2(d_ring)

        # Deterministic grid-sampling intersection over bounding box overlap (geodesic fraction)
        fx0, fy0, fx1, fy1 = _bbox_of_ring(f_ring)
        dx0, dy0, dx1, dy1 = _bbox_of_ring(d_ring)
        ix0, iy0, ix1, iy1 = max(fx0, dx0), max(fy0, dy0), min(fx1, dx1), min(fy1, dy1)
        if ix0 >= ix1 or iy0 >= iy1:
            return {
                "status": "NO_INTERSECTION",
                "field_area_m2": field_area_m2,
                "affected_area_m2": 0.0,
                "affected_area_ha": 0.0,
                "exceeds_field_boundary": damage_raw_m2 > 0,
            }

        grid = 40
        in_field = 0
        in_both = 0
        for gx in range(grid):
            x = fx0 + (fx1 - fx0) * (gx + 0.5) / grid
            for gy in range(grid):
                y = fy0 + (fy1 - fy0) * (gy + 0.5) / grid
                if _point_in_ring([x, y], f_ring):
                    in_field += 1
                    if _point_in_ring([x, y], d_ring):
                        in_both += 1

        frac = (in_both / in_field) if in_field > 0 else 0.0
        clipped_m2 = round(min(field_area_m2, field_area_m2 * frac), 2)
        return {
            "status": "FARMER_REPORTED",
            "field_area_m2": field_area_m2,
            "raw_drawn_area_m2": damage_raw_m2,
            "affected_area_m2": clipped_m2,
            "affected_area_ha": round(clipped_m2 / SQ_M_PER_HA, 4),
            "affected_area_fen": round(clipped_m2 / SQ_M_PER_FEN, 3),
            "affected_ratio": round(frac, 4),
            "exceeds_field_boundary": damage_raw_m2 > field_area_m2 * 1.02,
            "label": "FARMER_REPORTED",
        }
