"""Deterministic Product-Level GCOV Validator (Gate A.2).

Implements product-level verification functions operating on actual NISAR L-band Level-2 GCOV
grid metadata, subswath validity masks (`/science/LSAR/GCOV/grids/frequencyA/mask`),
and diagonal backscatter power arrays (`HHHH`, `HVHV`, `VVVV`):

1. Official GCOV `mask` semantics (`uint8`):
   - `255` (`_FillValue`): Pixel outside the radar acquisition extent.
   - `0`: Invalid / partially focused radar sample in the averaging set.
   - `1..254` (`(mask > 0) & (mask < 255)`): Valid fully-focused GCOV sample (subswath ID).
2. Grid equality & alignment verification (`EPSG`, `dx`, `dy`, `width`, `height`, `xCoordinates`, `yCoordinates`).
3. Diagonal power domain verification (`np.isfinite(P) & (P > 0.0)`) and strict nodata propagation.
4. Real valid-overlap computation (`valid_overlap_ratio`) across $T_0$ and $T_1$.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def evaluate_gcov_mask(mask: np.ndarray) -> dict[str, Any]:
    """Evaluate a NISAR GCOV `uint8` subswath mask according to official product semantics.

    Official HDF5 attribute specification:
    - `0`: Invalid / partially-focused radar sample in averaging set.
    - `1..254`: Valid GCOV sample (value indicates subswath number).
    - `255` (`_FillValue`): Outside radar acquisition extent.
    """
    if mask.ndim != 2:
        raise ValueError(f"Expected 2D GCOV mask array, got {mask.ndim}D with shape {mask.shape}.")

    total_pixels = int(mask.size)
    if total_pixels == 0:
        raise ValueError("GCOV mask array cannot be empty.")

    outside_fill_mask = mask == 255
    invalid_zero_mask = mask == 0
    valid_mask = (mask > 0) & (mask < 255)
    acquired_mask = ~outside_fill_mask

    n_total = total_pixels
    n_valid = int(valid_mask.sum())
    n_zero = int(invalid_zero_mask.sum())
    n_outside = int(outside_fill_mask.sum())
    n_acquired = int(acquired_mask.sum())

    vals, counts = np.unique(mask, return_counts=True)
    subswath_ids = [int(v) for v in vals if 0 < int(v) < 255]

    return {
        "valid_mask": valid_mask,
        "acquired_mask": acquired_mask,
        "total_pixels": n_total,
        "acquired_pixels": n_acquired,
        "valid_pixels": n_valid,
        "invalid_zero_pixels": n_zero,
        "outside_fill_255_pixels": n_outside,
        "valid_fraction_full_grid": float(n_valid / n_total),
        "valid_fraction_acquired": float(n_valid / n_acquired) if n_acquired > 0 else 0.0,
        "subswath_ids": subswath_ids,
        "value_counts": {int(k): int(v) for k, v in zip(vals, counts)},
    }


def compare_gcov_grids(
    grid_a: dict[str, Any],
    grid_b: dict[str, Any],
    *,
    tol: float = 1e-6,
) -> dict[str, Any]:
    """Compare CRS, spacing, dimensions, and coordinate vectors of two GCOV scenes."""
    epsg_a = int(grid_a["epsg"])
    epsg_b = int(grid_b["epsg"])
    same_epsg = epsg_a == epsg_b

    dx_a, dy_a = float(grid_a["x_spacing_m"]), float(grid_a["y_spacing_m"])
    dx_b, dy_b = float(grid_b["x_spacing_m"]), float(grid_b["y_spacing_m"])
    same_spacing = (abs(dx_a - dx_b) <= tol) and (abs(dy_a - dy_b) <= tol)

    shape_a = (int(grid_a["height"]), int(grid_a["width"]))
    shape_b = (int(grid_b["height"]), int(grid_b["width"]))
    same_shape = shape_a == shape_b

    x_a = np.asarray(grid_a["x_coordinates"], dtype=np.float64)
    y_a = np.asarray(grid_a["y_coordinates"], dtype=np.float64)
    x_b = np.asarray(grid_b["x_coordinates"], dtype=np.float64)
    y_b = np.asarray(grid_b["y_coordinates"], dtype=np.float64)

    same_x = bool(x_a.shape == x_b.shape and np.allclose(x_a, x_b, atol=tol, rtol=0.0))
    same_y = bool(y_a.shape == y_b.shape and np.allclose(y_a, y_b, atol=tol, rtol=0.0))

    exact_grid_match = bool(same_epsg and same_spacing and same_shape and same_x and same_y)
    reasons: list[str] = []
    if not same_epsg:
        reasons.append(f"EPSG mismatch ({epsg_a} vs {epsg_b}).")
    if not same_spacing:
        reasons.append(f"Grid spacing mismatch (({dx_a}, {dy_a}) vs ({dx_b}, {dy_b})).")
    if not same_shape:
        reasons.append(f"Raster dimension mismatch ({shape_a} vs {shape_b}).")
    if same_shape and not (same_x and same_y):
        reasons.append("Coordinate arrays (xCoordinates / yCoordinates) are offset or misaligned.")

    return {
        "exact_grid_match": exact_grid_match,
        "crs_compatible": same_epsg,
        "same_spacing": same_spacing,
        "same_shape": same_shape,
        "same_x_coordinates": same_x,
        "same_y_coordinates": same_y,
        "reasons": reasons,
    }


def inspect_power_layer(
    power: np.ndarray,
    mask: np.ndarray | None = None,
) -> dict[str, Any]:
    """Validate a GCOV diagonal linear power array (`HHHH`, `HVHV`, `VVVV`) and propagate nodata.

    Rules:
    - Non-positive values ($P \\le 0$), `NaN`, $\\pm\\infty$, and pixels where `mask` is invalid (`0` or `255`)
      are strictly invalid and propagated as `NaN` in decibel space (never coerced to `0.0`).
    """
    arr = np.asarray(power, dtype=np.float64)
    if mask is not None:
        if mask.shape != arr.shape:
            raise ValueError(
                f"Power array shape {arr.shape} does not match mask shape {mask.shape}."
            )
        mask_valid = (mask > 0) & (mask < 255)
    else:
        mask_valid = np.ones(arr.shape, dtype=bool)

    nan_count = int(np.isnan(arr).sum())
    inf_count = int(np.isinf(arr).sum())
    finite_mask = np.isfinite(arr)
    zero_count = int((finite_mask & (arr == 0.0)).sum())
    negative_count = int((finite_mask & (arr < 0.0)).sum())

    valid_power_mask = mask_valid & finite_mask & (arr > 0.0)
    db_array = np.full(arr.shape, np.nan, dtype=np.float32)
    if np.any(valid_power_mask):
        db_array[valid_power_mask] = (10.0 * np.log10(arr[valid_power_mask])).astype(np.float32)

    valid_vals = arr[valid_power_mask]
    if valid_vals.size > 0:
        pcts = np.percentile(valid_vals, [10, 50, 90]).tolist()
        lin_min = float(valid_vals.min())
        lin_median = float(pcts[1])
        lin_max = float(valid_vals.max())
        lin_p10 = float(pcts[0])
        lin_p90 = float(pcts[2])
    else:
        lin_min = lin_median = lin_max = lin_p10 = lin_p90 = None

    return {
        "valid_power_mask": valid_power_mask,
        "db_array": db_array,
        "total_pixels": int(arr.size),
        "valid_pixel_count": int(valid_vals.size),
        "nan_pixel_count": nan_count,
        "inf_pixel_count": inf_count,
        "zero_pixel_count": zero_count,
        "negative_pixel_count": negative_count,
        "non_positive_finite_count": zero_count + negative_count,
        "linear_min": lin_min,
        "linear_p10": lin_p10,
        "linear_median": lin_median,
        "linear_p90": lin_p90,
        "linear_max": lin_max,
    }


def compute_product_valid_overlap(
    mask_t0: np.ndarray,
    mask_t1: np.ndarray,
    power_t0: dict[str, np.ndarray | None],
    power_t1: dict[str, np.ndarray | None],
) -> dict[str, Any]:
    """Compute product-level valid pixel overlap across T0 and T1 for available polarizations.

    Never synthesizes missing polarizations: only polarizations with non-None arrays in BOTH
    `power_t0` and `power_t1` are included in `common_polarizations`.
    """
    if mask_t0.shape != mask_t1.shape:
        raise ValueError(
            f"Grid shape mismatch between mask_t0 {mask_t0.shape} and mask_t1 {mask_t1.shape}."
        )

    m0_info = evaluate_gcov_mask(mask_t0)
    m1_info = evaluate_gcov_mask(mask_t1)

    common_pols: list[str] = []
    unavailable_pols: list[str] = []
    all_pol_keys = sorted(set(power_t0.keys()) | set(power_t1.keys()))
    for pol in all_pol_keys:
        a0 = power_t0.get(pol)
        a1 = power_t1.get(pol)
        if a0 is not None and a1 is not None:
            common_pols.append(pol)
        else:
            unavailable_pols.append(pol)

    if not common_pols:
        return {
            "common_polarizations": [],
            "unavailable_polarizations": unavailable_pols,
            "t0_valid_fraction": 0.0,
            "t1_valid_fraction": 0.0,
            "common_valid_pixel_count": 0,
            "valid_overlap_ratio_acquired_union": 0.0,
            "valid_overlap_ratio_full_grid": 0.0,
        }

    t0_combined_valid = m0_info["valid_mask"].copy()
    t1_combined_valid = m1_info["valid_mask"].copy()
    per_pol_overlap: dict[str, int] = {}

    for pol in common_pols:
        p0_info = inspect_power_layer(power_t0[pol], mask_t0)  # type: ignore[arg-type]
        p1_info = inspect_power_layer(power_t1[pol], mask_t1)  # type: ignore[arg-type]
        t0_combined_valid &= p0_info["valid_power_mask"]
        t1_combined_valid &= p1_info["valid_power_mask"]
        per_pol_overlap[pol] = int(
            (p0_info["valid_power_mask"] & p1_info["valid_power_mask"]).sum()
        )

    common_valid_mask = t0_combined_valid & t1_combined_valid
    acquired_union_mask = m0_info["acquired_mask"] | m1_info["acquired_mask"]

    n_total = int(mask_t0.size)
    n_acq_union = int(acquired_union_mask.sum())
    n_t0_valid = int(t0_combined_valid.sum())
    n_t1_valid = int(t1_combined_valid.sum())
    n_common = int(common_valid_mask.sum())

    return {
        "common_polarizations": common_pols,
        "unavailable_polarizations": unavailable_pols,
        "per_polarization_common_valid_pixels": per_pol_overlap,
        "t0_valid_pixel_count": n_t0_valid,
        "t1_valid_pixel_count": n_t1_valid,
        "common_valid_pixel_count": n_common,
        "acquired_union_pixel_count": n_acq_union,
        "t0_valid_fraction_acquired": (
            float(n_t0_valid / m0_info["acquired_pixels"])
            if m0_info["acquired_pixels"] > 0
            else 0.0
        ),
        "t1_valid_fraction_acquired": (
            float(n_t1_valid / m1_info["acquired_pixels"])
            if m1_info["acquired_pixels"] > 0
            else 0.0
        ),
        "t0_valid_fraction_full_grid": float(n_t0_valid / n_total),
        "t1_valid_fraction_full_grid": float(n_t1_valid / n_total),
        "valid_overlap_ratio_acquired_union": (
            float(n_common / n_acq_union) if n_acq_union > 0 else 0.0
        ),
        "valid_overlap_ratio_full_grid": float(n_common / n_total),
    }
