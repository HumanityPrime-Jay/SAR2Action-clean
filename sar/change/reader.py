"""Windowed HDF5 reader and deterministic Change Engine pipeline for NISAR L2 GCOV (Phase 2A).

Key capabilities:
1. Reads only the 1D coordinate vectors (`xCoordinates`, `yCoordinates`, ~530 KB total) and
   scalar identification metadata to construct `GridDefinition`.
2. Verifies exact grid compatibility between T0 and T1 (`verify_grids_compatible`) before reading
   any 2D raster slices.
3. Reads only the 2D window slice `[row_start:row_stop, col_start:col_stop]` of `mask`, `HHHH`,
   `HVHV`, and `numberOfLooks` required for the AOI, avoiding loading 1.1-billion-pixel full frames
   into RAM.
4. Produces all Phase 2A.5 output products (`t0_hh_db`, `t1_hh_db`, `delta_hh_db`, `magnitude_hh_db`,
   `t0_hv_db`, `t1_hv_db`, `delta_hv_db`, `magnitude_hv_db`, `combined_radar_change`,
   `common_valid_mask`, `missing_invalid_mask`, `aoi_statistics`, `evidence_record`) and optional
   GeoTIFF exports.
"""

from __future__ import annotations

import pathlib
import time
from dataclasses import dataclass
from typing import Any

import h5py
import numpy as np
import rasterio
from rasterio.transform import Affine
from shapely.geometry.base import BaseGeometry

from backend.app.schemas.evidence import EvidenceRecord
from sar.change.delta import (
    CombinedRadarChangeLayer,
    compute_combined_radar_change,
    compute_magnitude_db,
    compute_signed_delta_db,
)
from sar.change.masks import MultiTemporalMaskBundle, build_multitemporal_valid_masks
from sar.change.radiometry import linear_power_to_db
from sar.change.statistics import (
    build_aoi_evidence_record,
    compute_polarization_aoi_statistics,
    summarize_number_of_looks_metadata,
)
from sar.change.windows import (
    GridDefinition,
    WindowSlice,
    aoi_to_window,
    verify_grids_compatible,
)

POLARIZATION_TO_DATASET = {
    "HH": "HHHH",
    "HV": "HVHV",
    "VV": "VVVV",
    "VH": "VHVH",
}


def _decode_h5_scalar(val: Any) -> Any:
    if isinstance(val, np.ndarray):
        if val.ndim == 0:
            val = val.item()
        elif val.size == 1:
            val = val.flat[0]
        else:
            return [_decode_h5_scalar(x) for x in val.tolist()]
    if isinstance(val, (bytes, np.bytes_)):
        return val.decode("utf-8", errors="replace").strip()
    if isinstance(val, np.generic):
        return val.item()
    return val


def _read_scalar(group: h5py.Group, name: str, default: Any = None) -> Any:
    if name not in group:
        return default
    return _decode_h5_scalar(group[name][()])


@dataclass(frozen=True)
class GCOVSceneWindow:
    """Windowed 2D arrays and metadata read from a single NISAR L2 GCOV HDF5 granule."""

    scene_id: str
    file_path: pathlib.Path | None
    acquisition_start_utc: str
    acquisition_end_utc: str
    orbit_pass_direction: str | None
    look_direction: str | None
    track_number: int | None
    frame_number: int | None
    crid: str | None
    product_version: str | None
    is_full_frame: bool
    data_maturity: str
    frequency_group: str
    available_polarizations: list[str]
    grid: GridDefinition
    window: WindowSlice
    mask: np.ndarray
    power: dict[str, np.ndarray | None]
    number_of_looks: np.ndarray | None
    window_ram_bytes: int
    full_frame_equivalent_bytes: int


@dataclass(frozen=True)
class AOIChangeResult:
    """Complete deterministic output bundle from the SAR2Action Phase 2A Change Engine."""

    roi_id: str
    evidence_id: str
    scene_ids: list[str]
    grid: GridDefinition
    window: WindowSlice
    available_polarizations: list[str]
    unavailable_polarizations: list[str]
    t0_hh_db: np.ndarray | None
    t1_hh_db: np.ndarray | None
    delta_hh_db: np.ndarray | None
    magnitude_hh_db: np.ndarray | None
    t0_hv_db: np.ndarray | None
    t1_hv_db: np.ndarray | None
    delta_hv_db: np.ndarray | None
    magnitude_hv_db: np.ndarray | None
    combined_radar_change: CombinedRadarChangeLayer | None
    common_valid_mask: np.ndarray
    missing_invalid_mask: np.ndarray
    mask_bundle: MultiTemporalMaskBundle
    aoi_statistics: dict[str, Any]
    evidence_record: EvidenceRecord
    runtime_seconds: float
    window_ram_bytes: int
    full_frame_equivalent_bytes: int

    def export_geotiffs(self, output_dir: str | pathlib.Path) -> dict[str, pathlib.Path]:
        """Export computed AOI dB layers and validity masks as georeferenced GeoTIFFs."""
        out_path = pathlib.Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        written: dict[str, pathlib.Path] = {}

        if self.window.fully_outside_grid or self.window.window_geotransform is None:
            return written

        gt = self.window.window_geotransform
        transform = Affine(gt[1], gt[2], gt[0], gt[4], gt[5], gt[3])
        height, width = self.window.shape
        crs = f"EPSG:{self.grid.epsg}"

        float_layers: list[tuple[str, np.ndarray | None]] = [
            ("t0_hh_db", self.t0_hh_db),
            ("t1_hh_db", self.t1_hh_db),
            ("delta_hh_db", self.delta_hh_db),
            ("magnitude_hh_db", self.magnitude_hh_db),
            ("t0_hv_db", self.t0_hv_db),
            ("t1_hv_db", self.t1_hv_db),
            ("delta_hv_db", self.delta_hv_db),
            ("magnitude_hv_db", self.magnitude_hv_db),
            (
                "combined_radar_change_db",
                self.combined_radar_change.data if self.combined_radar_change is not None else None,
            ),
        ]

        for name, arr in float_layers:
            if arr is None:
                continue
            tif_path = out_path / f"{self.roi_id}_{name}.tif"
            with rasterio.open(
                tif_path,
                "w",
                driver="GTiff",
                height=height,
                width=width,
                count=1,
                dtype="float32",
                crs=crs,
                transform=transform,
                nodata=np.nan,
                compress="deflate",
            ) as dst:
                dst.write(arr.astype(np.float32), 1)
            written[name] = tif_path

        for mask_name, mask_arr in (
            ("common_valid_mask", self.common_valid_mask),
            ("missing_invalid_mask", self.missing_invalid_mask),
        ):
            tif_path = out_path / f"{self.roi_id}_{mask_name}.tif"
            with rasterio.open(
                tif_path,
                "w",
                driver="GTiff",
                height=height,
                width=width,
                count=1,
                dtype="uint8",
                crs=crs,
                transform=transform,
                nodata=255,
                compress="deflate",
            ) as dst:
                dst.write(mask_arr.astype(np.uint8), 1)
            written[mask_name] = tif_path

        return written


def read_gcov_grid_and_metadata(
    h5_path: str | pathlib.Path,
    *,
    frequency_group: str = "frequencyA",
) -> tuple[GridDefinition, dict[str, Any]]:
    """Read `GridDefinition` and identification metadata from a NISAR GCOV HDF5 file."""
    path = pathlib.Path(h5_path)
    if not path.exists():
        raise FileNotFoundError(f"GCOV HDF5 file not found: {path}")

    with h5py.File(path, "r") as f:
        ident = f["/science/LSAR/identification"]
        grid_grp = f[f"/science/LSAR/GCOV/grids/{frequency_group}"]

        granule_id = str(
            _read_scalar(ident, "granuleId", path.stem) or path.stem
        ).removesuffix(".h5")
        start_utc_raw = str(_read_scalar(ident, "zeroDopplerStartTime", ""))
        end_utc_raw = str(_read_scalar(ident, "zeroDopplerEndTime", ""))
        start_utc = start_utc_raw if start_utc_raw.endswith("Z") else f"{start_utc_raw}Z"
        end_utc = end_utc_raw if end_utc_raw.endswith("Z") else f"{end_utc_raw}Z"

        orbit_pass = _read_scalar(ident, "orbitPassDirection")
        look_dir = _read_scalar(ident, "lookDirection")
        track_num = _read_scalar(ident, "trackNumber")
        frame_num = _read_scalar(ident, "frameNumber")
        crid = str(_read_scalar(ident, "compositeReleaseId", "")) or None
        prod_ver = str(_read_scalar(ident, "productVersion", "")) or None
        is_full_str = str(_read_scalar(ident, "isFullFrame", "False"))
        is_full_frame = is_full_str.strip().upper() == "TRUE"

        maturity = "PROVISIONAL"
        if crid and (crid.startswith("B") or crid.startswith("T")):
            maturity = "BETA"
        elif crid and (crid.startswith("V") or crid.startswith("R")):
            maturity = "VALIDATED"

        pols_raw = _read_scalar(grid_grp, "listOfPolarizations", [])
        if isinstance(pols_raw, str):
            avail_pols = [pols_raw.upper()]
        elif isinstance(pols_raw, list):
            avail_pols = [str(p).upper() for p in pols_raw]
        else:
            avail_pols = []

        epsg = int(_read_scalar(grid_grp, "projection"))
        dx = float(_read_scalar(grid_grp, "xCoordinateSpacing"))
        dy = float(_read_scalar(grid_grp, "yCoordinateSpacing"))
        x_coords = np.asarray(grid_grp["xCoordinates"][()], dtype=np.float64)
        y_coords = np.asarray(grid_grp["yCoordinates"][()], dtype=np.float64)

        grid = GridDefinition(
            epsg=epsg,
            width=int(x_coords.size),
            height=int(y_coords.size),
            x_spacing_m=dx,
            y_spacing_m=dy,
            x_coordinates=x_coords,
            y_coordinates=y_coords,
        )

        meta = {
            "scene_id": granule_id,
            "file_path": path,
            "acquisition_start_utc": start_utc,
            "acquisition_end_utc": end_utc,
            "orbit_pass_direction": str(orbit_pass) if orbit_pass is not None else None,
            "look_direction": str(look_dir) if look_dir is not None else None,
            "track_number": int(track_num) if track_num is not None else None,
            "frame_number": int(frame_num) if frame_num is not None else None,
            "crid": crid,
            "product_version": prod_ver,
            "is_full_frame": is_full_frame,
            "data_maturity": maturity,
            "frequency_group": frequency_group,
            "available_polarizations": avail_pols,
        }
        return grid, meta


def read_gcov_window(
    h5_path: str | pathlib.Path,
    aoi: list[float] | tuple[float, ...] | dict[str, Any] | BaseGeometry,
    *,
    frequency_group: str = "frequencyA",
    requested_polarizations: tuple[str, ...] = ("HH", "HV"),
    aoi_crs: str = "EPSG:4326",
    precomputed_grid: GridDefinition | None = None,
    precomputed_meta: dict[str, Any] | None = None,
    precomputed_window: WindowSlice | None = None,
) -> GCOVSceneWindow:
    """Read only the 2D HDF5 window corresponding to `aoi` from `h5_path`."""
    path = pathlib.Path(h5_path)
    if precomputed_grid is None or precomputed_meta is None:
        grid, meta = read_gcov_grid_and_metadata(path, frequency_group=frequency_group)
    else:
        grid, meta = precomputed_grid, precomputed_meta

    window = (
        precomputed_window
        if precomputed_window is not None
        else aoi_to_window(aoi, grid, aoi_crs=aoi_crs)
    )

    # Full-frame memory footprint for 1 uint8 mask + 2 float32 power + 1 float32 looks (13 bytes/px)
    full_frame_bytes = int(grid.height * grid.width * (1 + 4 * (len(requested_polarizations) + 1)))

    if window.fully_outside_grid or window.window_pixel_count == 0:
        empty_mask = np.empty((0, 0), dtype=np.uint8)
        empty_power: dict[str, np.ndarray | None] = {
            pol: (
                np.empty((0, 0), dtype=np.float32)
                if pol in meta["available_polarizations"]
                else None
            )
            for pol in requested_polarizations
        }
        return GCOVSceneWindow(
            scene_id=meta["scene_id"],
            file_path=path,
            acquisition_start_utc=meta["acquisition_start_utc"],
            acquisition_end_utc=meta["acquisition_end_utc"],
            orbit_pass_direction=meta["orbit_pass_direction"],
            look_direction=meta["look_direction"],
            track_number=meta["track_number"],
            frame_number=meta["frame_number"],
            crid=meta["crid"],
            product_version=meta["product_version"],
            is_full_frame=meta["is_full_frame"],
            data_maturity=meta["data_maturity"],
            frequency_group=frequency_group,
            available_polarizations=meta["available_polarizations"],
            grid=grid,
            window=window,
            mask=empty_mask,
            power=empty_power,
            number_of_looks=np.empty((0, 0), dtype=np.float32),
            window_ram_bytes=0,
            full_frame_equivalent_bytes=full_frame_bytes,
        )

    r0, r1 = window.row_start, window.row_stop
    c0, c1 = window.col_start, window.col_stop

    with h5py.File(path, "r") as f:
        grid_grp = f[f"/science/LSAR/GCOV/grids/{frequency_group}"]
        mask_arr = np.asarray(grid_grp["mask"][r0:r1, c0:c1], dtype=np.uint8)
        ram_bytes = int(mask_arr.nbytes)

        power_dict: dict[str, np.ndarray | None] = {}
        for pol in requested_polarizations:
            ds_name = POLARIZATION_TO_DATASET.get(pol.upper(), pol.upper())
            if pol.upper() in meta["available_polarizations"] and ds_name in grid_grp:
                arr = np.asarray(grid_grp[ds_name][r0:r1, c0:c1], dtype=np.float32)
                power_dict[pol.upper()] = arr
                ram_bytes += int(arr.nbytes)
            else:
                power_dict[pol.upper()] = None

        looks_arr: np.ndarray | None = None
        if "numberOfLooks" in grid_grp:
            looks_arr = np.asarray(grid_grp["numberOfLooks"][r0:r1, c0:c1], dtype=np.float32)
            ram_bytes += int(looks_arr.nbytes)

    return GCOVSceneWindow(
        scene_id=meta["scene_id"],
        file_path=path,
        acquisition_start_utc=meta["acquisition_start_utc"],
        acquisition_end_utc=meta["acquisition_end_utc"],
        orbit_pass_direction=meta["orbit_pass_direction"],
        look_direction=meta["look_direction"],
        track_number=meta["track_number"],
        frame_number=meta["frame_number"],
        crid=meta["crid"],
        product_version=meta["product_version"],
        is_full_frame=meta["is_full_frame"],
        data_maturity=meta["data_maturity"],
        frequency_group=frequency_group,
        available_polarizations=meta["available_polarizations"],
        grid=grid,
        window=window,
        mask=mask_arr,
        power=power_dict,
        number_of_looks=looks_arr,
        window_ram_bytes=ram_bytes,
        full_frame_equivalent_bytes=full_frame_bytes,
    )


def run_in_memory_change_analysis(
    *,
    win_t0: GCOVSceneWindow,
    win_t1: GCOVSceneWindow,
    roi_id: str,
    evidence_id: str,
    include_combined_change: bool = True,
    elapsed_io_seconds: float = 0.0,
) -> AOIChangeResult:
    """Execute deterministic radiometric change, masking, statistics, and EvidenceRecord generation
    on two `GCOVSceneWindow` objects (used by both HDF5 pipeline and unit tests).
    """
    t_start = time.perf_counter()
    verify_grids_compatible(win_t0.grid, win_t1.grid)

    window = win_t0.window
    grid = win_t0.grid
    poly_mask = window.polygon_mask

    mask_bundle = build_multitemporal_valid_masks(
        win_t0.mask,
        win_t1.mask,
        win_t0.power,
        win_t1.power,
        aoi_polygon_mask=poly_mask,
    )

    avail = mask_bundle.available_polarizations
    unavail = mask_bundle.unavailable_polarizations

    t0_hh_db: np.ndarray | None = None
    t1_hh_db: np.ndarray | None = None
    delta_hh_db: np.ndarray | None = None
    mag_hh_db: np.ndarray | None = None

    t0_hv_db: np.ndarray | None = None
    t1_hv_db: np.ndarray | None = None
    delta_hv_db: np.ndarray | None = None
    mag_hv_db: np.ndarray | None = None

    per_pol_stats: dict[str, dict[str, Any]] = {}

    if "HH" in avail and win_t0.power.get("HH") is not None and win_t1.power.get("HH") is not None:
        v0_hh = mask_bundle.valid_t0_by_pol["HH"]
        v1_hh = mask_bundle.valid_t1_by_pol["HH"]
        vc_hh = mask_bundle.common_valid_by_pol["HH"]

        t0_hh_db = linear_power_to_db(win_t0.power["HH"], valid_mask=v0_hh)
        t1_hh_db = linear_power_to_db(win_t1.power["HH"], valid_mask=v1_hh)
        delta_hh_db = compute_signed_delta_db(t0_hh_db, t1_hh_db, common_valid_mask=vc_hh)
        mag_hh_db = compute_magnitude_db(delta_hh_db, common_valid_mask=vc_hh)

        per_pol_stats["HH"] = compute_polarization_aoi_statistics(
            polarization="HH",
            t0_db=t0_hh_db,
            t1_db=t1_hh_db,
            delta_db=delta_hh_db,
            magnitude_db=mag_hh_db,
            common_valid_mask=vc_hh,
            aoi_footprint_mask=mask_bundle.aoi_footprint_mask,
            pixel_area_m2=grid.pixel_area_m2,
        )

    if "HV" in avail and win_t0.power.get("HV") is not None and win_t1.power.get("HV") is not None:
        v0_hv = mask_bundle.valid_t0_by_pol["HV"]
        v1_hv = mask_bundle.valid_t1_by_pol["HV"]
        vc_hv = mask_bundle.common_valid_by_pol["HV"]

        t0_hv_db = linear_power_to_db(win_t0.power["HV"], valid_mask=v0_hv)
        t1_hv_db = linear_power_to_db(win_t1.power["HV"], valid_mask=v1_hv)
        delta_hv_db = compute_signed_delta_db(t0_hv_db, t1_hv_db, common_valid_mask=vc_hv)
        mag_hv_db = compute_magnitude_db(delta_hv_db, common_valid_mask=vc_hv)

        per_pol_stats["HV"] = compute_polarization_aoi_statistics(
            polarization="HV",
            t0_db=t0_hv_db,
            t1_db=t1_hv_db,
            delta_db=delta_hv_db,
            magnitude_db=mag_hv_db,
            common_valid_mask=vc_hv,
            aoi_footprint_mask=mask_bundle.aoi_footprint_mask,
            pixel_area_m2=grid.pixel_area_m2,
        )

    combined_layer: CombinedRadarChangeLayer | None = None
    if include_combined_change and delta_hh_db is not None and delta_hv_db is not None:
        combined_layer = compute_combined_radar_change(
            delta_hh_db,
            delta_hv_db,
            common_valid_mask=mask_bundle.common_valid_mask,
        )

    looks_meta = summarize_number_of_looks_metadata(
        win_t0.number_of_looks,
        win_t1.number_of_looks,
        mask_bundle.common_valid_mask,
    )

    evidence = build_aoi_evidence_record(
        evidence_id=evidence_id,
        roi_id=roi_id,
        scene_ids=[win_t0.scene_id, win_t1.scene_id],
        t0_acquisition_utc=win_t0.acquisition_start_utc,
        t1_acquisition_utc=win_t1.acquisition_start_utc,
        aoi_geometry_wgs84=window.aoi_geometry_wgs84,
        mask_bundle=mask_bundle,
        per_pol_stats=per_pol_stats,
        combined_layer=combined_layer,
        looks_metadata=looks_meta,
        pixel_area_m2=grid.pixel_area_m2,
        requested_pixel_count=window.requested_pixel_count,
        partly_outside_grid=window.partly_outside_grid,
        fully_outside_grid=window.fully_outside_grid,
        crs_epsg=grid.epsg,
        pixel_spacing_m=(abs(grid.x_spacing_m), abs(grid.y_spacing_m)),
        orbit_pass_direction=win_t0.orbit_pass_direction,
        look_direction=win_t0.look_direction,
        t0_crid=win_t0.crid,
        t1_crid=win_t1.crid,
        data_maturity=win_t0.data_maturity,
    )

    total_runtime = round(elapsed_io_seconds + (time.perf_counter() - t_start), 6)
    total_window_ram = int(win_t0.window_ram_bytes + win_t1.window_ram_bytes)
    total_full_frame_bytes = int(
        win_t0.full_frame_equivalent_bytes + win_t1.full_frame_equivalent_bytes
    )

    return AOIChangeResult(
        roi_id=roi_id,
        evidence_id=evidence_id,
        scene_ids=[win_t0.scene_id, win_t1.scene_id],
        grid=grid,
        window=window,
        available_polarizations=avail,
        unavailable_polarizations=unavail,
        t0_hh_db=t0_hh_db,
        t1_hh_db=t1_hh_db,
        delta_hh_db=delta_hh_db,
        magnitude_hh_db=mag_hh_db,
        t0_hv_db=t0_hv_db,
        t1_hv_db=t1_hv_db,
        delta_hv_db=delta_hv_db,
        magnitude_hv_db=mag_hv_db,
        combined_radar_change=combined_layer,
        common_valid_mask=mask_bundle.common_valid_mask,
        missing_invalid_mask=mask_bundle.missing_invalid_mask,
        mask_bundle=mask_bundle,
        aoi_statistics=evidence.summary_statistics,
        evidence_record=evidence,
        runtime_seconds=total_runtime,
        window_ram_bytes=total_window_ram,
        full_frame_equivalent_bytes=total_full_frame_bytes,
    )


def run_aoi_change_analysis(
    t0_h5_path: str | pathlib.Path,
    t1_h5_path: str | pathlib.Path,
    aoi: list[float] | tuple[float, ...] | dict[str, Any] | BaseGeometry,
    *,
    roi_id: str = "AOI-01",
    evidence_id: str = "E-CHANGE-001",
    frequency_group: str = "frequencyA",
    requested_polarizations: tuple[str, ...] = ("HH", "HV"),
    aoi_crs: str = "EPSG:4326",
    include_combined_change: bool = True,
) -> AOIChangeResult:
    """Run the end-to-end deterministic Change Engine on two NISAR L2 GCOV HDF5 granules over `aoi`."""
    t_io_start = time.perf_counter()
    grid_t0, meta_t0 = read_gcov_grid_and_metadata(t0_h5_path, frequency_group=frequency_group)
    grid_t1, meta_t1 = read_gcov_grid_and_metadata(t1_h5_path, frequency_group=frequency_group)

    # Refuse mismatched grids before touching any 2D raster slices
    verify_grids_compatible(grid_t0, grid_t1)

    window = aoi_to_window(aoi, grid_t0, aoi_crs=aoi_crs)
    win_t0 = read_gcov_window(
        t0_h5_path,
        aoi,
        frequency_group=frequency_group,
        requested_polarizations=requested_polarizations,
        aoi_crs=aoi_crs,
        precomputed_grid=grid_t0,
        precomputed_meta=meta_t0,
        precomputed_window=window,
    )
    win_t1 = read_gcov_window(
        t1_h5_path,
        aoi,
        frequency_group=frequency_group,
        requested_polarizations=requested_polarizations,
        aoi_crs=aoi_crs,
        precomputed_grid=grid_t1,
        precomputed_meta=meta_t1,
        precomputed_window=window,
    )
    io_elapsed = time.perf_counter() - t_io_start

    return run_in_memory_change_analysis(
        win_t0=win_t0,
        win_t1=win_t1,
        roi_id=roi_id,
        evidence_id=evidence_id,
        include_combined_change=include_combined_change,
        elapsed_io_seconds=io_elapsed,
    )
