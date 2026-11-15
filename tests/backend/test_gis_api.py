import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
CASE = "CHAMPI-YUNLIN-TAIXI"


def square(x, y, width):
    return [[x, y], [x + width, y], [x + width, y + width], [x, y + width], [x, y]]


def measure(geometry, crs="EPSG:3826", **extra):
    return client.post("/api/gis/measure", json={
        "case_id": CASE, "geometry": geometry, "input_crs": crs, **extra,
    })


def test_square_hole_and_multipolygon():
    outer = square(170000, 2620000, 100)
    response = measure({"type": "Polygon", "coordinates": [outer]})
    assert response.status_code == 200
    value = response.json()
    assert (value["area_m2"], value["area_ha"], value["perimeter_m"]) == (10000, 1, 400)
    assert value["geometry_source"] == "USER_DRAWN"
    assert value["parcel_feature_id"] is None
    assert value["assumed_approved_area_ha"] is None
    assert value["official_cadastral_area_m2"] is None
    assert value["satellite_statistics_status"] == "NO_REGISTERED_SATELLITE_STATISTICS"
    result = measure({"type": "MultiPolygon", "coordinates": [
        [outer, square(170025, 2620025, 20)], [square(170150, 2620000, 50)],
    ]}).json()
    assert result["area_m2"] == 12100
    assert result["perimeter_m"] == 680


def test_round_trip():
    def convert(x, y, source, target):
        response = client.post("/api/gis/transform-point", json={
            "x": x, "y": y, "from_crs": source, "to_crs": target,
        })
        assert response.status_code == 200
        return response.json()

    original = (170000, 2620000)
    geographic = convert(*original, "EPSG:3826", "EPSG:4326")
    assert geographic["axis_order"] == "longitude,latitude"
    projected = convert(geographic["x"], geographic["y"], "EPSG:4326", "EPSG:3826")
    assert (projected["x"], projected["y"]) == pytest.approx(original, abs=0.001, rel=0)


@pytest.mark.parametrize("geometry", [
    {"type": "Point", "coordinates": [120.2, 23.7]},
    {"type": "Polygon", "coordinates": [[[120.2, 23.7], [120.21, 23.71], [120.2, 23.71], [120.21, 23.7], [120.2, 23.7]]]},
    {"type": "Polygon", "coordinates": [square(20, 12, 0.01)]},
    {"type": "Polygon", "coordinates": [square(120.2, 23.7, 0.01)[:-1]]},
    {"type": "Polygon", "coordinates": [[[120.2, 23.7]] * 2001]},
])
def test_invalid_geometry(geometry):
    assert measure(geometry, "EPSG:4326").status_code == 422


def test_cannot_claim_official_or_send_unbounded_input():
    geometry = {"type": "Polygon", "coordinates": [square(170000, 2620000, 100)]}
    assert measure(geometry, geometry_source="OFFICIAL_CADASTRAL").status_code == 422
    assert measure(geometry, parcel_feature_id=4183).status_code == 422
    assert client.post("/api/gis/measure", content=b" " * (129 * 1024)).status_code == 413


def test_real_taixi_parcels_from_committed_geojson():
    cand1 = Path(__file__).resolve().parents[2] / "frontend/public/studio/fields.geojson"
    cand2 = Path(__file__).resolve().parents[2] / "frontend/team-demo/public/studio/fields.geojson"
    cand3 = Path(__file__).resolve().parents[2] / "data/exports/yunlin_vh_2025_2026/fields.geojson"
    target = cand1 if cand1.is_file() else (cand2 if cand2.is_file() else cand3)
    features = json.loads(target.read_text(encoding="utf8"))["features"]
    expected = [125089.43, 96723.58, 82955.76, 61780.83, 54639.29]
    for feature, area in zip(sorted(features, key=lambda f: f["properties"]["field_id"]), expected, strict=True):
        response = measure(feature["geometry"], "EPSG:4326")
        assert response.status_code == 200
        assert response.json()["area_m2"] == pytest.approx(area, abs=0.01)
