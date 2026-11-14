"""Lightweight NISAR L-band Level-2 GCOV HDF5 structure and metadata inspector.

Supports both `h5py` and pure-Python `pyfive` so HDF5 structure, identification metadata,
coordinate spacing, EPSG projection, available diagonal covariance terms (`HHHH`, `HVHV`, `VVVV`),
and `mask` presence can be verified deterministically without loading full multi-GB rasters into RAM.
"""

from __future__ import annotations

import pathlib
from typing import Any

import numpy as np


def _open_hdf5(path: pathlib.Path) -> Any:
    """Open an HDF5 file read-only using `h5py` if available, falling back to pure-Python `pyfive`."""
    try:
        import h5py  # type: ignore

        return h5py.File(path, "r")
    except Exception:
        import pyfive  # type: ignore

        return pyfive.File(str(path))


def _decode_scalar(val: Any) -> Any:
    if isinstance(val, np.ndarray):
        if val.ndim == 0:
            val = val.item()
        elif val.size == 1:
            val = val.flat[0]
        else:
            return [_decode_scalar(x) for x in val.tolist()]
    if isinstance(val, (bytes, np.bytes_)):
        return val.decode("utf-8", errors="replace").strip()
    if isinstance(val, np.generic):
        return val.item()
    return val


def _read_dataset_value(group: Any, key: str) -> Any:
    if key not in group:
        return None
    ds = group[key]
    data = ds[...]
    return _decode_scalar(data)


def inspect_gcov_hdf5_structure(
    path: str | pathlib.Path,
    *,
    frequency_group: str = "frequencyA",
) -> dict[str, Any]:
    """Inspect a local NISAR Level-2 GCOV HDF5 file and return its structural & grid metadata."""
    file_path = pathlib.Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"GCOV HDF5 file not found: {file_path}")

    with _open_hdf5(file_path) as h5:
        has_lsar = "science" in h5 and "LSAR" in h5["science"]
        if not has_lsar:
            raise ValueError(f"File {file_path.name} does not contain `/science/LSAR`.")

        lsar = h5["science"]["LSAR"]
        ident = lsar["identification"] if "identification" in lsar else {}

        start_utc = _read_dataset_value(ident, "zeroDopplerStartTime")
        end_utc = _read_dataset_value(ident, "zeroDopplerEndTime")
        orbit_pass = _read_dataset_value(ident, "orbitPassDirection")
        look_dir = _read_dataset_value(ident, "lookDirection")
        track_num = _read_dataset_value(ident, "trackNumber")
        frame_num = _read_dataset_value(ident, "frameNumber")
        crid = _read_dataset_value(ident, "compositeReleaseId")
        product_version = _read_dataset_value(ident, "productVersion")
        frequencies = _read_dataset_value(ident, "listOfFrequencies")

        if "GCOV" not in lsar or "grids" not in lsar["GCOV"]:
            raise ValueError(f"File {file_path.name} does not contain `/science/LSAR/GCOV/grids`.")

        grids = lsar["GCOV"]["grids"]
        if frequency_group not in grids:
            raise ValueError(
                f"Requested frequency group {frequency_group!r} not in `/science/LSAR/GCOV/grids`."
            )

        fgrid = grids[frequency_group]
        pol_list_raw = _read_dataset_value(fgrid, "listOfPolarizations")
        if isinstance(pol_list_raw, str):
            polarizations = [pol_list_raw]
        elif isinstance(pol_list_raw, list):
            polarizations = [str(p) for p in pol_list_raw]
        else:
            polarizations = []

        dx = _read_dataset_value(fgrid, "xCoordinateSpacing")
        dy = _read_dataset_value(fgrid, "yCoordinateSpacing")
        epsg = _read_dataset_value(fgrid, "projection")

        diagonal_datasets: dict[str, tuple[int, ...]] = {}
        for pol in ("HHHH", "HVHV", "VVVV", "VHVH"):
            if pol in fgrid:
                diagonal_datasets[pol] = tuple(int(d) for d in fgrid[pol].shape)

        has_mask = "mask" in fgrid
        mask_shape = tuple(int(d) for d in fgrid["mask"].shape) if has_mask else None

        return {
            "file_name": file_path.name,
            "frequency_group": frequency_group,
            "acquisition_start_utc": start_utc,
            "acquisition_end_utc": end_utc,
            "orbit_pass_direction": orbit_pass,
            "look_direction": look_dir,
            "track_number": track_num,
            "frame_number": frame_num,
            "crid": crid,
            "product_version": product_version,
            "frequencies": frequencies,
            "list_of_polarizations": polarizations,
            "diagonal_datasets": diagonal_datasets,
            "x_spacing_m": float(dx) if dx is not None else None,
            "y_spacing_m": float(dy) if dy is not None else None,
            "epsg": int(epsg) if epsg is not None else None,
            "has_mask": has_mask,
            "mask_shape": mask_shape,
        }
