"""Official NISAR L2 GCOV validity mask and multi-temporal intersection logic (Phase 2A.2).

Enforces the Gate A.2 discovery:
Pixels in NISAR L2 GCOV may contain finite positive HHHH/HVHV float values even when `mask == 0`
(indicating at least one partially focused or invalid radar sample in the covariance averaging set).
Those pixels MUST NOT enter scientific change calculations.

Official Valid Pixel Rule:
- `0 < mask < 255`: Valid fully-focused GCOV sample (subswath number 1..254)
- `mask == 0`: Invalid / partially-focused sample -> EXCLUDED
- `mask == 255`: Outside radar acquisition extent -> EXCLUDED
- `np.isfinite(power) & (power > 0)`: Finite strictly positive linear gamma-naught power -> REQUIRED
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

MASK_RULE_SPECIFICATION = "(mask > 0) & (mask < 255) & np.isfinite(power) & (power > 0)"


def is_valid_gcov_product_mask(mask: np.ndarray) -> np.ndarray:
    """Return boolean mask True only where `0 < mask < 255` (valid fully-focused subswath sample)."""
    m = np.asarray(mask)
    return (m > 0) & (m < 255)


def is_valid_radiometric_power(power: np.ndarray) -> np.ndarray:
    """Return boolean mask True only where linear gamma-naught power is finite and strictly positive."""
    p = np.asarray(power, dtype=np.float64)
    return np.isfinite(p) & (p > 0.0)


def compute_valid_pixel_mask(
    mask: np.ndarray,
    power: np.ndarray,
    *,
    aoi_polygon_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Apply the official combined product-mask + radiometric-power validity rule (2A.2):

    ```python
    valid = (
        (mask > 0)
        & (mask < 255)
        & np.isfinite(power)
        & (power > 0)
    )
    ```
    """
    m = np.asarray(mask)
    p = np.asarray(power, dtype=np.float64)
    if m.shape != p.shape:
        raise ValueError(f"Mask shape {m.shape} does not match power shape {p.shape}.")

    valid = (m > 0) & (m < 255) & np.isfinite(p) & (p > 0.0)
    if aoi_polygon_mask is not None:
        poly = np.asarray(aoi_polygon_mask, dtype=bool)
        if poly.shape != m.shape:
            raise ValueError(
                f"AOI polygon mask shape {poly.shape} does not match grid shape {m.shape}."
            )
        valid = valid & poly
    return valid


@dataclass(frozen=True)
class MultiTemporalMaskBundle:
    """Complete validity mask bundle for a T0/T1 GCOV comparison window."""

    available_polarizations: list[str]
    unavailable_polarizations: list[str]
    valid_t0_by_pol: dict[str, np.ndarray]
    valid_t1_by_pol: dict[str, np.ndarray]
    common_valid_by_pol: dict[str, np.ndarray]
    common_valid_mask: np.ndarray  # Intersection across all available shared polarizations
    missing_invalid_mask: np.ndarray  # ~common_valid_mask (True where invalid/missing)
    aoi_footprint_mask: np.ndarray  # True inside the AOI polygon within the window
    diagnostics: dict[str, Any]


def build_multitemporal_valid_masks(
    mask_t0: np.ndarray,
    mask_t1: np.ndarray,
    power_t0: dict[str, np.ndarray | None],
    power_t1: dict[str, np.ndarray | None],
    *,
    aoi_polygon_mask: np.ndarray | None = None,
) -> MultiTemporalMaskBundle:
    """Compute per-polarization and combined common-valid masks across T0 and T1.

    Rules:
    - Never synthesizes missing polarizations.
    - Requires common validity in BOTH scenes for each shared polarization.
    - For dual-polarization analysis, `common_valid_mask` requires common validity across all
      shared polarizations (`HH` and `HV`), while `common_valid_by_pol[pol]` stores the
      channel-specific common validity mask.
    - Records explicit diagnostics proving how many `mask == 0` pixels had finite positive power
      and were rejected by the official mask rule.
    """
    m0 = np.asarray(mask_t0)
    m1 = np.asarray(mask_t1)
    if m0.shape != m1.shape:
        raise ValueError(f"T0 mask shape {m0.shape} does not match T1 mask shape {m1.shape}.")

    shape = m0.shape
    if aoi_polygon_mask is not None:
        aoi_mask = np.asarray(aoi_polygon_mask, dtype=bool)
        if aoi_mask.shape != shape:
            raise ValueError(
                f"aoi_polygon_mask shape {aoi_mask.shape} does not match mask shape {shape}."
            )
    else:
        aoi_mask = np.ones(shape, dtype=bool)

    all_pols = sorted(set(power_t0.keys()) | set(power_t1.keys()))
    avail_pols: list[str] = []
    unavail_pols: list[str] = []
    for pol in all_pols:
        if power_t0.get(pol) is not None and power_t1.get(pol) is not None:
            avail_pols.append(pol)
        else:
            unavail_pols.append(pol)

    valid_t0_by_pol: dict[str, np.ndarray] = {}
    valid_t1_by_pol: dict[str, np.ndarray] = {}
    common_valid_by_pol: dict[str, np.ndarray] = {}
    per_pol_diag: dict[str, Any] = {}

    for pol in avail_pols:
        p0 = np.asarray(power_t0[pol], dtype=np.float64)
        p1 = np.asarray(power_t1[pol], dtype=np.float64)
        v0 = compute_valid_pixel_mask(m0, p0, aoi_polygon_mask=aoi_mask)
        v1 = compute_valid_pixel_mask(m1, p1, aoi_polygon_mask=aoi_mask)
        vc = v0 & v1

        valid_t0_by_pol[pol] = v0
        valid_t1_by_pol[pol] = v1
        common_valid_by_pol[pol] = vc

        # Count finite positive power pixels that had mask == 0 and were excluded
        finite_pos_p0 = np.isfinite(p0) & (p0 > 0.0) & aoi_mask
        finite_pos_p1 = np.isfinite(p1) & (p1 > 0.0) & aoi_mask
        mask_zero_finite_pos_t0 = int(((m0 == 0) & finite_pos_p0).sum())
        mask_zero_finite_pos_t1 = int(((m1 == 0) & finite_pos_p1).sum())

        per_pol_diag[pol] = {
            "t0_valid_pixels": int(v0.sum()),
            "t1_valid_pixels": int(v1.sum()),
            "common_valid_pixels": int(vc.sum()),
            "t0_mask_zero_with_finite_positive_power_rejected": mask_zero_finite_pos_t0,
            "t1_mask_zero_with_finite_positive_power_rejected": mask_zero_finite_pos_t1,
            "t0_nan_power_pixels": int((np.isnan(p0) & aoi_mask).sum()),
            "t1_nan_power_pixels": int((np.isnan(p1) & aoi_mask).sum()),
            "t0_non_positive_finite_power_pixels": int(
                (np.isfinite(p0) & (p0 <= 0.0) & aoi_mask).sum()
            ),
            "t1_non_positive_finite_power_pixels": int(
                (np.isfinite(p1) & (p1 <= 0.0) & aoi_mask).sum()
            ),
        }

    if avail_pols:
        common_all = np.ones(shape, dtype=bool) & aoi_mask
        for pol in avail_pols:
            common_all = common_all & common_valid_by_pol[pol]
    else:
        common_all = np.zeros(shape, dtype=bool)

    missing_invalid = (~common_all) & aoi_mask

    diagnostics = {
        "mask_rule": MASK_RULE_SPECIFICATION,
        "window_shape": [int(shape[0]), int(shape[1])],
        "aoi_footprint_pixels_in_window": int(aoi_mask.sum()),
        "t0_mask_zero_pixels_in_aoi": int(((m0 == 0) & aoi_mask).sum()),
        "t0_mask_valid_subswath_pixels_in_aoi": int(((m0 > 0) & (m0 < 255) & aoi_mask).sum()),
        "t0_mask_255_outside_pixels_in_aoi": int(((m0 == 255) & aoi_mask).sum()),
        "t1_mask_zero_pixels_in_aoi": int(((m1 == 0) & aoi_mask).sum()),
        "t1_mask_valid_subswath_pixels_in_aoi": int(((m1 > 0) & (m1 < 255) & aoi_mask).sum()),
        "t1_mask_255_outside_pixels_in_aoi": int(((m1 == 255) & aoi_mask).sum()),
        "common_valid_all_channels_pixels": int(common_all.sum()),
        "missing_or_invalid_pixels_in_aoi": int(missing_invalid.sum()),
        "per_polarization": per_pol_diag,
    }

    return MultiTemporalMaskBundle(
        available_polarizations=avail_pols,
        unavailable_polarizations=unavail_pols,
        valid_t0_by_pol=valid_t0_by_pol,
        valid_t1_by_pol=valid_t1_by_pol,
        common_valid_by_pol=common_valid_by_pol,
        common_valid_mask=common_all,
        missing_invalid_mask=missing_invalid,
        aoi_footprint_mask=aoi_mask,
        diagnostics=diagnostics,
    )
