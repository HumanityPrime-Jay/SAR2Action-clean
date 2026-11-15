from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.plot import plotting_extent
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds
from rasterio.windows import Window
from scipy.ndimage import label
from shapely.geometry import box, mapping
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from sar.change.delta import compute_signed_delta_db
from sar.change.radiometry import linear_power_to_db
from sar.change.statistics import compute_distribution_stats_db

INPUT = ROOT / "inputs"
OUT = ROOT / "taiwan-agricultural-demo-v1"
SCENES = [
    ("G4367321249-ASF", "OPERA_L2_RTC-S1_T069-146197-IW1_20261014T100042Z_20261015T103540Z_S1D_30_v1.0", "2026-10-14T10:00:42Z", {"VV": 7047381, "VH": 7121884, "mask": 59540}),
    ("G4389918405-ASF", "OPERA_L2_RTC-S1_T069-146197-IW1_20261026T100042Z_20261027T000531Z_S1D_30_v1.0", "2026-10-26T10:00:42Z", {"VV": 7044578, "VH": 7094791, "mask": 59733}),
]
PARCEL_URL = "https://data.moa.gov.tw/GetOpenDataFile.aspx?id=I75&FileType=DataMore&RID=44143"
EVIDENCE_SCHEMA = "taiwan-agricultural-demo/1.0"
ALGORITHM = "tw01-opera-rtc/1.0"
MATCH_TAGS = (
    "ORBIT_PASS_DIRECTION", "PRODUCT_VERSION", "BURST_ID", "INPUT_DEM_SOURCE",
    "SOFTWARE_VERSION", "ISCE3_VERSION", "PROCESSING_INFORMATION_RADIOMETRIC_TERRAIN_CORRECTION_ALGORITHM",
    "PROCESSING_INFORMATION_OUTPUT_BACKSCATTER_DECIBEL_CONVERSION_EQUATION",
)
TRACE_TAGS = MATCH_TAGS + ("ABSOLUTE_ORBIT_NUMBER", "SOURCE_DATA_SOFTWARE_VERSION", "INPUT_ORBIT_FILES")
x, y = Transformer.from_crs(4326, 3826, always_xy=True).transform(120.30, 23.71)
AOI = gpd.GeoSeries([box(x - 2500, y - 2500, x + 2500, y + 2500)], crs=3826)
LIMITATIONS = [
    "cause_not_determined",
    "SAR backscatter change can reflect moisture, irrigation, harvest, crop growth or acquisition effects.",
    "Short-lived inundation may have receded by the post-event acquisition.",
    "Radar observations do not establish crop damage, yield loss, financial loss or aid eligibility.",
    "Parcel boundaries do not identify event-date crop type or provide ground truth.",
]


def write_json(name, value):
    with (OUT / name).open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def crop_parcels():
    path = INPUT / "yunlin-parcels.zip"
    parcels = gpd.read_file(f"zip://{path.as_posix()}", bbox=tuple(AOI.total_bounds))
    if parcels.crs is None or parcels.crs.to_epsg() != 3826:
        raise ValueError("Unexpected parcel CRS; bbox query must use EPSG:3826.")
    parcels["geometry"] = parcels.geometry.make_valid()
    clipped = parcels.clip(AOI, keep_geom_type=True)
    clipped = clipped.loc[clipped.geometry.area > 0].copy()
    if clipped.empty:
        raise ValueError("No polygon parcels intersect the AOI.")
    fields = [c for c in clipped.columns if c.upper() == "PARCEL_NO"]
    clipped = clipped[fields + ["geometry"]].reset_index(drop=True)
    clipped.insert(0, "parcel_feature_id", np.arange(1, len(clipped) + 1))
    clipped["clipped_area_m2"] = clipped.geometry.area.round(2)
    clipped.to_crs(4326).to_file(OUT / "farmland.geojson", driver="GeoJSON")
    fig, ax = plt.subplots(figsize=(6.5, 6.5), layout="constrained")
    clipped.plot(ax=ax, facecolor="#4e8972", edgecolor="#ffffff", linewidth=.16)
    AOI.boundary.plot(ax=ax, color="#202b2d", linewidth=1.1)
    ax.set(title="Yunlin | Farm parcel boundaries within the 5 km × 5 km AOI",
           xlabel="TWD97 TM2 easting (m)", ylabel="TWD97 TM2 northing (m)")
    ax.ticklabel_format(style="plain", useOffset=False)
    fig.savefig(OUT / "farmland.png", dpi=150)
    plt.close(fig)
    return clipped


def asset_records():
    scenes, missing = [], []
    for granule, scene, utc, sizes in SCENES:
        assets = {}
        for channel, expected in sizes.items():
            fname = f"{scene}_{channel}.tif"
            path = INPUT / fname
            present = path.is_file() and path.stat().st_size == expected
            if not present:
                missing.append(fname)
            assets[channel] = {
                "filename": fname, "expected_bytes": expected,
                "url": f"https://cumulus.asf.earthdatacloud.nasa.gov/OPERA/OPERA_L2_RTC-S1/{scene}/{fname}",
                "downloaded": present, "sha256": sha(path) if present else None,
            }
        scenes.append({"scene_id": scene, "cmr_granule_id": granule,
                       "acquisition_utc": utc, "assets": assets})
    return scenes, missing


def map_overlay(delta, crs, transform, channel):
    height, width = delta.shape
    left, bottom, right, top = rasterio.transform.array_bounds(height, width, transform)
    target = "EPSG:3857"
    target_transform, w, h = calculate_default_transform(
        crs, target, width, height, left, bottom, right, top
    )
    pixels = np.full((h, w), np.nan, dtype=np.float32)
    reproject(delta, pixels, src_transform=transform, src_crs=crs, src_nodata=np.nan,
              dst_transform=target_transform, dst_crs=target, dst_nodata=np.nan,
              resampling=Resampling.nearest)
    rgba = plt.get_cmap("RdBu_r")(plt.Normalize(-6, 6, clip=True)(pixels), bytes=True)
    name = f"delta_{channel.lower()}_overlay.png"
    Image.fromarray(rgba).save(OUT / name)
    west, south, east, north = transform_bounds(
        target, "EPSG:4326", *rasterio.transform.array_bounds(h, w, target_transform)
    )
    return {"href": name, "crs": target, "render_range_db": [-6, 6],
            "coordinates_lon_lat": [[west, north], [east, north], [east, south], [west, south]]}


def analyze(scenes, parcels):
    ref = None
    epochs, masks, tags = [], [], []
    for scene in scenes:
        arrays, epoch_tags = {}, {}
        for key, asset in scene["assets"].items():
            with rasterio.open(INPUT / asset["filename"]) as ds:
                signature = (ds.crs, ds.transform, ds.width, ds.height)
                if ref is None:
                    ref = signature
                    if not ds.crs or not ds.crs.is_projected or ds.crs.linear_units != "metre" or ds.res != (30, 30):
                        raise ValueError("Expected a projected 30 m grid.")
                    aoi = AOI.to_crs(ds.crs).iloc[0]
                    raw = rasterio.windows.from_bounds(*aoi.bounds, transform=ds.transform)
                    col, row = int(np.floor(raw.col_off)), int(np.floor(raw.row_off))
                    end_col, end_row = int(np.ceil(raw.col_off + raw.width)), int(np.ceil(raw.row_off + raw.height))
                    window = Window(col, row, end_col - col, end_row - row)
                    transform = ds.window_transform(window)
                    shape = (int(window.height), int(window.width))
                    inside = geometry_mask([mapping(aoi)], shape, transform, invert=True)
                if signature != ref:
                    raise ValueError("RTC product grids differ; no implicit resampling.")
                image = ds.read(1, window=window, boundless=True, masked=True)
                epoch_tags[key] = {k: v for k, v in ds.tags().items() if k in TRACE_TAGS}
                if key == "mask":
                    mask = image.filled(255)
                    if not np.isin(mask[inside], [0, 1, 2, 3, 255]).all():
                        raise ValueError("Unknown OPERA mask class.")
                else:
                    arrays[key] = image.astype("float64").filled(np.nan)
        epochs.append(arrays)
        masks.append(mask)
        tags.append(epoch_tags)

    for field in MATCH_TAGS:
        values = {band.get(field) for epoch in tags for band in epoch.values()}
        if None in values or len(values) != 1:
            raise ValueError(f"Product metadata missing or inconsistent: {field}")

    channels = ("VV", "VH")
    valid = [{k: inside & (masks[i] == 0) & np.isfinite(e[k]) & (e[k] > 0) for k in channels}
             for i, e in enumerate(epochs)]
    common = valid[0]["VV"] & valid[0]["VH"] & valid[1]["VV"] & valid[1]["VH"]
    total, count = int(inside.sum()), int(common.sum())
    if not count:
        raise ValueError("No common valid dual-polarization samples.")
    pack = {"grid": {"crs": ref[0].to_string(), "spacing_m": [30, 30],
                     "shape": list(shape), "transform": list(transform)[:6]},
            "aoi_pixel_count": total, "common_valid_pixel_count": count,
            "common_coverage_fraction": count / total,
            "valid_by_epoch": [{k: int(v.sum()) for k, v in e.items()} for e in valid],
            "mask_counts_by_epoch": [{str(k): int(((m == k) & inside).sum()) for k in (0, 1, 2, 3, 255)} for m in masks],
            "rtc_tags_by_epoch": tags, "polarizations": {}, "layers": []}
    projected = parcels.to_crs(ref[0])
    fig, axes = plt.subplots(1, 2, figsize=(10, 5), layout="constrained")
    deltas = {}
    for k, ax in zip(channels, axes, strict=True):
        t0, t1 = [linear_power_to_db(e[k], valid_mask=common) for e in epochs]
        d = compute_signed_delta_db(t0, t1, common_valid_mask=common)
        deltas[k] = d
        pack["polarizations"][k] = {
            label: compute_distribution_stats_db(arr, common).model_dump()
            for label, arr in (("t0_db", t0), ("t1_db", t1), ("delta_db", d))
        }
        filename = f"delta_{k.lower()}_db.tif"
        with rasterio.open(OUT / filename, "w", driver="GTiff", height=shape[0], width=shape[1],
                           count=1, dtype="float32", crs=ref[0], transform=transform,
                           nodata=np.nan, compress="deflate") as ds:
            ds.write(d, 1)
            ds.update_tags(units="dB", polarization=k, source_product="OPERA RTC-S1")
        pack["layers"].append({"polarization": k, "href": filename, "unit": "dB",
                               "overlay": map_overlay(d, ref[0], transform, k)})
        im = ax.imshow(d, extent=plotting_extent(d, transform), cmap="RdBu_r", vmin=-6, vmax=6)
        projected.boundary.plot(ax=ax, linewidth=.23, color="#333333", alpha=.65)
        ax.set(xlim=(aoi.bounds[0], aoi.bounds[2]), ylim=(aoi.bounds[1], aoi.bounds[3]), title=f"Delta {k} (dB)")
        ax.set_axis_off()
        fig.colorbar(im, ax=ax, shrink=.68)
    fig.suptitle("Yunlin | Sentinel-1D OPERA RTC | 14–26 Oct 2026\nBackscatter change and farmland boundaries")
    fig.savefig(OUT / "radar-change.png", dpi=170)
    plt.close(fig)
    pack["preview_png"] = "radar-change.png"
    pack["radiometry"] = {"comparison": "Same sensor, burst and RTC product version. Values are gamma0 power.",
                          "offset_correction_applied": False,
                          "upstream_s1_processor_versions": [t["VV"].get("SOURCE_DATA_SOFTWARE_VERSION") for t in tags],
                          "aoi_median_delta_db": {k: pack["polarizations"][k]["delta_db"]["median"] for k in channels},
                          "stable_reference_test": "Not independently established. Inspect AOI-wide shift and candidate controls before interpreting.",
                          "delta_formula": "10*log10(power_t1) - 10*log10(power_t0)"}
    changed = common & ((np.abs(deltas["VV"]) >= 3) | (np.abs(deltas["VH"]) >= 3))
    groups, _ = label(changed)
    retained = (groups > 0) & (np.bincount(groups.ravel())[groups] >= 9)
    with rasterio.open(OUT / "candidate-areas.tif", "w", driver="GTiff",
                       height=shape[0], width=shape[1], count=1, dtype="uint8",
                       crs=ref[0], transform=transform, nodata=255, compress="deflate") as ds:
        ds.write(np.where(common, retained, 255).astype(np.uint8), 1)
    pack["candidate_areas"] = {"href": "candidate-areas.tif",
                               "candidate_pixel_count": int(retained.sum()),
                               "criteria": "Absolute delta >= 3 dB in VV or VH, at least 9 edge-connected pixels; exploratory only.",
                               "classes": {"0": "other common-valid sample", "1": "radar change candidate", "255": "no common valid observation"}}

    candidate_features, eligible = [], 0
    for parcel in projected.itertuples():
        footprint = geometry_mask([mapping(parcel.geometry)], shape, transform, invert=True)
        n = int(footprint.sum())
        usable = footprint & common
        v = int(usable.sum())
        if v < 5 or v / n < 0.8:
            continue
        eligible += 1
        medians = {k: round(float(np.median(d[usable])), 4) for k, d in deltas.items()}
        if max(map(abs, medians.values())) >= 3:
            candidate_features.append({"parcel_feature_id": parcel.parcel_feature_id,
                                       "valid_pixel_count": v, "coverage_fraction": v/n,
                                       "median_delta_db": medians})
    pack["parcel_screening"] = {"eligible_parcels": eligible, "candidate_count": len(candidate_features),
                                "criteria": "At least 5 valid pixel centers and 80% coverage; abs(median delta) >= 3 dB in either channel. Exploratory threshold, not a damage classifier.",
                                "candidates": candidate_features}
    if candidate_features:
        ids = {c["parcel_feature_id"] for c in candidate_features}
        parcels.loc[parcels.parcel_feature_id.isin(ids)].to_crs(4326).to_file(
            OUT / "candidate-parcels.geojson", driver="GeoJSON")
        pack["parcel_screening"]["geometry_href"] = "candidate-parcels.geojson"
    return pack


def main():
    OUT.mkdir(exist_ok=True)
    parcels = crop_parcels()
    aoi = AOI.to_crs(4326).iloc[0]
    write_json("aoi.geojson", {"type": "Feature", "geometry": mapping(aoi),
                               "properties": {"center_lon_lat": [120.3, 23.71], "area_km2": 25}})
    scenes, missing = asset_records()
    result = {"schema_version": EVIDENCE_SCHEMA, "algorithm_version": ALGORITHM,
              "status": "awaiting_rtc", "evidence_id": None, "sensor": "Sentinel-1D",
              "product": "OPERA_L2_RTC-S1_V1", "polarizations": ["VV", "VH"],
              "aoi_href": "aoi.geojson", "scenes": scenes,
              "farmland": {"href": "farmland.geojson", "preview_png": "farmland.png", "source_url": PARCEL_URL,
                           "parcel_count": len(parcels), "source_sha256": sha(INPUT / "yunlin-parcels.zip")},
              "official_background": {"source": "Agriculture and Food Agency final report",
                                      "url": "https://www.afa.gov.tw/cht/index.php?article_id=34384&code=list&flag=detail&ids=717",
                                      "scope": "County-level reporting only", "yunlin_reported_loss_twd": 157740000},
              "limitations": LIMITATIONS, "analysis": None, "missing_assets": missing}
    if not missing:
        try:
            result["analysis"] = analyze(scenes, parcels)
        except (ValueError, rasterio.errors.RasterioError) as exc:
            result.update(status="validation_failed", failure_reason=str(exc))
        else:
            hashes = [a["sha256"] for s in scenes for a in s["assets"].values()]
            identity = json.dumps([ALGORITHM, AOI.iloc[0].wkb_hex, *hashes,
                                   result["farmland"]["source_sha256"]])
            result.update(status="verified_observation",
                          evidence_id="E-TW01-" + hashlib.sha256(identity.encode()).hexdigest()[:16].upper())
    refs = ["aoi.geojson", "farmland.geojson", "farmland.png"]
    if result["analysis"] is not None:
        analysis = result["analysis"]
        refs.extend([analysis["preview_png"], *(layer["href"] for layer in analysis["layers"])])
        refs.extend(layer["overlay"]["href"] for layer in analysis["layers"])
        refs.append(analysis["candidate_areas"]["href"])
        if "geometry_href" in analysis["parcel_screening"]:
            refs.append(analysis["parcel_screening"]["geometry_href"])
    result["asset_sha256"] = {name: sha(OUT / name) for name in refs}
    write_json("manifest.json", result)
    print(result["status"], "parcel count", len(parcels), "missing RTC assets", len(missing))
    if result["analysis"]:
        print(result["evidence_id"], json.dumps(result["analysis"]["polarizations"]),
              result["analysis"]["common_coverage_fraction"])


if __name__ == "__main__":
    main()
