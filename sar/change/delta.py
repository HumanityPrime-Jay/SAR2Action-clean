"""Multi-temporal backscatter change calculations in decibels (Phase 2A.3).

Equations:
    Delta_HH = HH_dB_T1 - HH_dB_T0
    Delta_HV = HV_dB_T1 - HV_dB_T0
    Magnitude_HH = abs(Delta_HH)
    Magnitude_HV = abs(Delta_HV)
    Combined_Radar_Change = abs(Delta_HH) + abs(Delta_HV)   (optional, only when both HH and HV exist)

Mandatory disclaimer for Combined_Radar_Change:
    "Custom visualization metric — not a hazard score, fire probability, damage score, or official burn-severity index."
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

COMBINED_RADAR_CHANGE_DISCLAIMER = (
    "Custom visualization metric — not a hazard score, fire probability, "
    "damage score, or official burn-severity index."
)


def compute_signed_delta_db(
    db_t0: np.ndarray,
    db_t1: np.ndarray,
    *,
    common_valid_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Compute signed multi-temporal change `Delta_dB = dB_T1 - dB_T0` preserving sign.

    Pixels that are invalid in either T0 or T1 (or False in `common_valid_mask`) are set to `np.nan`
    and never coerced to `0.0`.
    """
    b0 = np.asarray(db_t0, dtype=np.float64)
    b1 = np.asarray(db_t1, dtype=np.float64)
    if b0.shape != b1.shape:
        raise ValueError(f"db_t0 shape {b0.shape} does not match db_t1 shape {b1.shape}.")

    valid = np.isfinite(b0) & np.isfinite(b1)
    if common_valid_mask is not None:
        cvm = np.asarray(common_valid_mask, dtype=bool)
        if cvm.shape != b0.shape:
            raise ValueError(
                f"common_valid_mask shape {cvm.shape} does not match db shape {b0.shape}."
            )
        valid = valid & cvm

    delta = np.full(b0.shape, np.nan, dtype=np.float32)
    if np.any(valid):
        delta[valid] = (b1[valid] - b0[valid]).astype(np.float32)
    return delta


def compute_magnitude_db(
    delta_db: np.ndarray,
    *,
    common_valid_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Compute sign-agnostic change magnitude `|Delta_dB| = abs(Delta_dB)` in dB."""
    d = np.asarray(delta_db, dtype=np.float64)
    valid = np.isfinite(d)
    if common_valid_mask is not None:
        cvm = np.asarray(common_valid_mask, dtype=bool)
        if cvm.shape != d.shape:
            raise ValueError(
                f"common_valid_mask shape {cvm.shape} does not match delta_db shape {d.shape}."
            )
        valid = valid & cvm

    mag = np.full(d.shape, np.nan, dtype=np.float32)
    if np.any(valid):
        mag[valid] = np.abs(d[valid]).astype(np.float32)
    return mag


@dataclass(frozen=True)
class CombinedRadarChangeLayer:
    """Container for the optional dual-polarization visualization layer `D = |Delta_HH| + |Delta_HV|`."""

    data: np.ndarray
    metric_name: str = "Combined Radar Change"
    disclaimer: str = COMBINED_RADAR_CHANGE_DISCLAIMER


def compute_combined_radar_change(
    delta_hh_db: np.ndarray | None,
    delta_hv_db: np.ndarray | None,
    *,
    common_valid_mask: np.ndarray | None = None,
) -> CombinedRadarChangeLayer | None:
    """Compute `Combined_Radar_Change = abs(Delta_HH) + abs(Delta_HV)` when both HH and HV exist.

    Returns `None` if either `delta_hh_db` or `delta_hv_db` is `None`.
    """
    if delta_hh_db is None or delta_hv_db is None:
        return None

    d_hh = np.asarray(delta_hh_db, dtype=np.float64)
    d_hv = np.asarray(delta_hv_db, dtype=np.float64)
    if d_hh.shape != d_hv.shape:
        raise ValueError(
            f"delta_hh_db shape {d_hh.shape} does not match delta_hv_db shape {d_hv.shape}."
        )

    valid = np.isfinite(d_hh) & np.isfinite(d_hv)
    if common_valid_mask is not None:
        cvm = np.asarray(common_valid_mask, dtype=bool)
        if cvm.shape != d_hh.shape:
            raise ValueError(
                f"common_valid_mask shape {cvm.shape} does not match delta shape {d_hh.shape}."
            )
        valid = valid & cvm

    combined = np.full(d_hh.shape, np.nan, dtype=np.float32)
    if np.any(valid):
        combined[valid] = (np.abs(d_hh[valid]) + np.abs(d_hv[valid])).astype(np.float32)

    return CombinedRadarChangeLayer(
        data=combined,
        metric_name="Combined Radar Change",
        disclaimer=COMBINED_RADAR_CHANGE_DISCLAIMER,
    )
