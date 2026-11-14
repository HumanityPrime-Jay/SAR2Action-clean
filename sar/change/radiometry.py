"""Radiometric linear gamma-naught power to decibel conversion (Phase 2A.3).

Equation:
    B = 10 * log10(P)   [dB]

Strictly enforced rules:
- Computed ONLY where pixel passes both the official GCOV product mask (`0 < mask < 255`)
  and radiometric domain validity (`np.isfinite(P) & (P > 0.0)`).
- Any invalid, masked, non-positive (`P <= 0`), `NaN`, or `±Inf` pixel is set to `np.nan`
  (`float32`) — never coerced to `0.0`.
"""

from __future__ import annotations

import numpy as np

from sar.change.masks import compute_valid_pixel_mask, is_valid_radiometric_power


def linear_power_to_db(
    power: np.ndarray,
    *,
    mask: np.ndarray | None = None,
    valid_mask: np.ndarray | None = None,
    aoi_polygon_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Convert linear gamma-naught backscatter power `P` into decibels `10 * log10(P)`.

    Parameters
    ----------
    power:
        2D array of linear gamma-naught power (`HHHH`, `HVHV`, `VVVV`, etc.).
    mask:
        Optional 2D `uint8` GCOV subswath mask (`0 < mask < 255` valid; `0` and `255` invalid).
    valid_mask:
        Optional pre-computed boolean validity mask. Even if provided, `np.isfinite(power) & (power > 0)`
        is additionally enforced so `log10` is never evaluated on non-positive or non-finite values.
    aoi_polygon_mask:
        Optional 2D boolean mask restricting valid output to the AOI polygon.

    Returns
    -------
    np.ndarray
        2D `float32` array in dB with `np.nan` at all invalid or masked pixels.
    """
    p = np.asarray(power, dtype=np.float64)
    if mask is not None:
        eff_valid = compute_valid_pixel_mask(mask, p, aoi_polygon_mask=aoi_polygon_mask)
    else:
        eff_valid = is_valid_radiometric_power(p)
        if aoi_polygon_mask is not None:
            poly = np.asarray(aoi_polygon_mask, dtype=bool)
            if poly.shape != p.shape:
                raise ValueError(
                    f"aoi_polygon_mask shape {poly.shape} does not match power shape {p.shape}."
                )
            eff_valid = eff_valid & poly

    if valid_mask is not None:
        vm = np.asarray(valid_mask, dtype=bool)
        if vm.shape != p.shape:
            raise ValueError(
                f"valid_mask shape {vm.shape} does not match power shape {p.shape}."
            )
        eff_valid = eff_valid & vm

    out_db = np.full(p.shape, np.nan, dtype=np.float32)
    if np.any(eff_valid):
        out_db[eff_valid] = (10.0 * np.log10(p[eff_valid])).astype(np.float32)
    return out_db
