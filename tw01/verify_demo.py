"""Verify published assets and the internal consistency of the evidence manifest."""
import json

import geopandas as gpd
import jsonschema
import numpy as np
import rasterio
from PIL import Image

from build_demo import OUT, sha


def main():
    manifest = json.loads((OUT / "manifest.json").read_bytes())
    schema = json.loads((OUT / "schema.json").read_bytes())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(manifest, schema)
    for name, checksum in manifest["asset_sha256"].items():
        path = OUT / name
        assert sha(path) == checksum, name
        if path.suffix == ".png":
            with Image.open(path) as image:
                image.verify()

    aoi = gpd.read_file(OUT / "aoi.geojson").to_crs(3826).geometry.iloc[0]
    fields = gpd.read_file(OUT / "farmland.geojson").to_crs(3826)
    assert abs(aoi.area - 25_000_000) < 1
    assert fields.geometry.is_valid.all()
    assert fields.geometry.within(aoi.buffer(0.001)).all()
    assert len(fields) == manifest["farmland"]["parcel_count"]
    print(len(fields), "valid clipped features;", round(fields.union_all().area / 1e6, 3), "km^2 union")

    analysis = manifest["analysis"]
    if analysis is None:
        assert manifest["evidence_id"] is None
        print(manifest["status"], len(manifest["missing_assets"]), "missing assets")
        return

    raster_valid = []
    for layer in analysis["layers"]:
        overlay = layer["overlay"]
        assert overlay["crs"] == "EPSG:3857" and len(overlay["coordinates_lon_lat"]) == 4
        with Image.open(OUT / overlay["href"]) as image:
            assert image.mode == "RGBA"
            assert image.getchannel("A").getextrema()[1] == 255
        with rasterio.open(OUT / layer["href"]) as dataset:
            samples = dataset.read(1, masked=True)
            valid = ~np.ma.getmaskarray(samples)
            assert int(valid.sum()) == analysis["common_valid_pixel_count"]
            assert dataset.crs.to_string() == analysis["grid"]["crs"]
            assert np.allclose(tuple(dataset.transform)[:6], analysis["grid"]["transform"])
            expect = analysis["polarizations"][layer["polarization"]]["delta_db"]["median"]
            assert abs(float(np.median(samples.compressed())) - expect) < 0.0001
            raster_valid.append(valid)
    assert np.array_equal(*raster_valid)
    assert analysis["common_coverage_fraction"] == analysis["common_valid_pixel_count"] / analysis["aoi_pixel_count"]
    with rasterio.open(OUT / analysis["candidate_areas"]["href"]) as dataset:
        candidates = dataset.read(1)
        assert np.isin(candidates, [0, 1, 255]).all()
        assert np.array_equal(candidates != 255, raster_valid[0])
        assert int((candidates == 1).sum()) == analysis["candidate_areas"]["candidate_pixel_count"]
    print(manifest["evidence_id"], "raster masks, medians, coverage and candidate counts verified")


if __name__ == "__main__":
    main()
