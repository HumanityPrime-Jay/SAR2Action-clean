"""Deterministic SAR layer color-mapping, WGS84 reprojection, and RGBA PNG encoding.

Strictly enforces Section 3.2 (Radar Reveal):
- Legends and color interpretations explicitly distinguish:
  1. Positive radar change (Delta > 0 dB)
  2. Negative radar change (Delta < 0 dB)
  3. Invalid / unavailable observation (mask == 0, mask == 255, or P <= 0 -> NaN)
- Never labels any color scale as wildfire, burn severity, damage, or risk.
"""

from __future__ import annotations

import pathlib
import struct
import zlib
from typing import Any

import numpy as np
import rasterio.transform
import rasterio.warp
from rasterio.crs import CRS

from backend.app.schemas.api import LayerLegendSpec, LayerMetadataResponse
from backend.app.schemas.evidence import (
    COMBINED_RADAR_CHANGE_DISCLAIMER,
    PolarizationChannel,
)
from sar.change.reader import AOIChangeResult


def encode_rgba_png(rgba: np.ndarray) -> bytes:
    """Encode a uint8 `(H, W, 4)` RGBA numpy array into a valid PNG byte stream using stdlib `zlib`."""
    arr = np.ascontiguousarray(rgba, dtype=np.uint8)
    height, width, channels = arr.shape
    if channels != 4:
        raise ValueError(f"Expected 4 RGBA channels, got {channels}")

    # Prepend filter byte 0 (None) to each scanline
    filter_col = np.zeros((height, 1), dtype=np.uint8)
    scanlines = np.hstack([filter_col, arr.reshape(height, width * 4)])
    compressed = zlib.compress(scanlines.tobytes(), level=6)

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", compressed)
        + _chunk(b"IEND", b"")
    )


def _interpolate_colormap(
    norm_vals: np.ndarray,
    stops_rgb: list[tuple[float, tuple[int, int, int]]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Piecewise linear RGB interpolation on normalized `[0.0, 1.0]` values."""
    xs = np.array([s[0] for s in stops_rgb], dtype=np.float64)
    rs = np.array([s[1][0] for s in stops_rgb], dtype=np.float64)
    gs = np.array([s[1][1] for s in stops_rgb], dtype=np.float64)
    bs = np.array([s[1][2] for s in stops_rgb], dtype=np.float64)

    clipped = np.clip(norm_vals, 0.0, 1.0)
    r = np.interp(clipped, xs, rs).astype(np.uint8)
    g = np.interp(clipped, xs, gs).astype(np.uint8)
    b = np.interp(clipped, xs, bs).astype(np.uint8)
    return r, g, b


def reproject_window_to_wgs84(
    arr: np.ndarray,
    *,
    src_epsg: int,
    src_bounds_utm: tuple[float, float, float, float],
    max_dim: int = 720,
    is_mask: bool = False,
) -> tuple[np.ndarray, list[float]]:
    """Reproject a 2D UTM window array to EPSG:4326 for exact MapLibre GL JS image overlay alignment."""
    h, w = arr.shape
    if h == 0 or w == 0:
        return np.empty((1, 1), dtype=np.float32), [0.0, 0.0, 0.001, 0.001]

    min_x, min_y, max_x, max_y = src_bounds_utm
    src_transform = rasterio.transform.from_bounds(min_x, min_y, max_x, max_y, w, h)
    src_crs = CRS.from_epsg(src_epsg)
    dst_crs = CRS.from_epsg(4326)

    scale = min(1.0, float(max_dim) / float(max(h, w)))
    target_w = max(16, int(round(w * scale)))
    target_h = max(16, int(round(h * scale)))

    dst_transform, dst_w, dst_h = rasterio.warp.calculate_default_transform(
        src_crs,
        dst_crs,
        w,
        h,
        left=min_x,
        bottom=min_y,
        right=max_x,
        top=max_y,
        dst_width=target_w,
        dst_height=target_h,
    )

    src_f32 = np.asarray(arr, dtype=np.float32)
    dst_f32 = np.full((dst_h, dst_w), np.nan, dtype=np.float32)

    rasterio.warp.reproject(
        source=src_f32,
        destination=dst_f32,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=rasterio.warp.Resampling.nearest,
    )

    west, south, east, north = rasterio.transform.array_bounds(dst_h, dst_w, dst_transform)
    bbox_wgs84 = [
        round(float(west), 6),
        round(float(south), 6),
        round(float(east), 6),
        round(float(north), 6),
    ]
    return dst_f32, bbox_wgs84


def render_layer_rgba(
    arr_wgs84: np.ndarray,
    *,
    layer_type: str,
    min_val: float,
    max_val: float,
) -> np.ndarray:
    """Convert a 2D `EPSG:4326` float32 layer into an RGBA `(H, W, 4)` image."""
    h, w = arr_wgs84.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    if layer_type == "validity_mask":
        # In validity_mask: 1.0 = valid comparable observation, 0.0 = invalid inside AOI, NaN = outside
        valid_px = np.isfinite(arr_wgs84) & (arr_wgs84 >= 0.5)
        invalid_px = np.isfinite(arr_wgs84) & (arr_wgs84 < 0.5)
        # Valid comparable pixels: Emerald (#10b981)
        rgba[valid_px, 0] = 16
        rgba[valid_px, 1] = 185
        rgba[valid_px, 2] = 129
        rgba[valid_px, 3] = 200
        # Invalid / masked pixels (mask == 0, mask == 255, or P <= 0): Rose-Slate (#e11d48)
        rgba[invalid_px, 0] = 225
        rgba[invalid_px, 1] = 29
        rgba[invalid_px, 2] = 72
        rgba[invalid_px, 3] = 215
        return rgba

    finite = np.isfinite(arr_wgs84)
    if not np.any(finite):
        return rgba

    norm = np.zeros_like(arr_wgs84, dtype=np.float64)
    span = max(float(max_val - min_val), 1e-6)
    norm[finite] = (arr_wgs84[finite] - min_val) / span

    if layer_type in ("t0_hh", "t1_hh", "t0_hv", "t1_hv"):
        # Single-epoch radar gamma0 dB: Deep Navy -> Slate Teal -> Warm Bone
        stops = [
            (0.0, (12, 20, 38)),
            (0.25, (30, 64, 110)),
            (0.50, (45, 130, 145)),
            (0.75, (132, 196, 144)),
            (1.0, (245, 247, 220)),
        ]
    elif layer_type in ("delta_hh", "delta_hv"):
        # Diverging signed radar change (dB):
        # Negative change (< 0 dB): Deep Blue -> Cyan
        # Near zero (~ 0 dB): Neutral Slate/Ivory
        # Positive change (> 0 dB): Amber -> Deep Orange/Copper
        stops = [
            (0.0, (8, 47, 135)),
            (0.25, (56, 142, 230)),
            (0.50, (241, 245, 249)),
            (0.75, (245, 158, 11)),
            (1.0, (180, 52, 3)),
        ]
    elif layer_type in ("magnitude_hh", "magnitude_hv"):
        # Sign-agnostic |Delta| magnitude (dB): Dark Slate -> Teal -> Gold
        stops = [
            (0.0, (15, 23, 42)),
            (0.35, (13, 148, 136)),
            (0.70, (234, 179, 8)),
            (1.0, (254, 240, 138)),
        ]
    else:
        # Combined Radar Change D = |Delta_HH| + |Delta_HV| (dB): Deep Indigo -> Cyan -> Amber
        stops = [
            (0.0, (17, 24, 39)),
            (0.33, (37, 99, 235)),
            (0.66, (16, 185, 129)),
            (1.0, (245, 158, 11)),
        ]

    r, g, b = _interpolate_colormap(norm[finite], stops)
    rgba[finite, 0] = r
    rgba[finite, 1] = g
    rgba[finite, 2] = b
    rgba[finite, 3] = 215
    return rgba


def build_legend_for_layer(layer_type: str, polarization: PolarizationChannel | None) -> tuple[LayerLegendSpec, str]:
    """Construct the scientifically conservative `LayerLegendSpec` and color interpretation text."""
    pol_str = polarization.value if polarization else "Dual-Pol"
    if layer_type in ("t0_hh", "t1_hh"):
        epoch = "T0" if layer_type.startswith("t0") else "T1"
        spec = LayerLegendSpec(
            title=f"{epoch} HH Backscatter (γ⁰ dB)",
            units="dB",
            min_value=-24.0,
            max_value=-3.0,
            palette_type="single_epoch_db",
            stops=[
                {"value": -24.0, "color": "#0c1426", "label": "-24 dB (Low HH backscatter)"},
                {"value": -13.5, "color": "#2d8291", "label": "-13.5 dB (Moderate HH)"},
                {"value": -3.0, "color": "#f5f7dc", "label": "-3 dB (High HH backscatter)"},
            ],
        )
        interp = "Single-epoch L-band HH RTC gamma-naught backscatter power in dB (10*log10(HHHH))."
        return spec, interp

    if layer_type in ("t0_hv", "t1_hv"):
        epoch = "T0" if layer_type.startswith("t0") else "T1"
        spec = LayerLegendSpec(
            title=f"{epoch} HV Backscatter (γ⁰ dB)",
            units="dB",
            min_value=-30.0,
            max_value=-9.0,
            palette_type="single_epoch_db",
            stops=[
                {"value": -30.0, "color": "#0c1426", "label": "-30 dB (Low HV cross-pol)"},
                {"value": -19.5, "color": "#2d8291", "label": "-19.5 dB (Moderate HV volume scatter)"},
                {"value": -9.0, "color": "#f5f7dc", "label": "-9 dB (High HV cross-pol)"},
            ],
        )
        interp = "Single-epoch L-band HV RTC gamma-naught cross-polarized backscatter power in dB (10*log10(HVHV))."
        return spec, interp

    if layer_type in ("delta_hh", "delta_hv"):
        spec = LayerLegendSpec(
            title=f"Signed Δ{pol_str} (T1 − T0, dB)",
            units="dB",
            min_value=-4.0,
            max_value=4.0,
            palette_type="signed_diverging_db",
            stops=[
                {"value": -4.0, "color": "#082f87", "label": "-4.0 dB (Negative radar change: T1 < T0)"},
                {"value": -2.0, "color": "#388ee6", "label": "-2.0 dB (Backscatter decrease)"},
                {"value": 0.0, "color": "#f1f5f9", "label": "0.0 dB (No net dB shift)"},
                {"value": 2.0, "color": "#f59e0b", "label": "+2.0 dB (Backscatter increase)"},
                {"value": 4.0, "color": "#b43403", "label": "+4.0 dB (Positive radar change: T1 > T0)"},
            ],
            positive_change_meaning=f"Positive radar change (Δ{pol_str} > 0 dB): Backscatter power increased from T0 to T1.",
            negative_change_meaning=f"Negative radar change (Δ{pol_str} < 0 dB): Backscatter power decreased from T0 to T1.",
        )
        interp = (
            f"Signed multi-temporal {pol_str} radar change (B_T1 - B_T0 in dB). "
            "Blue indicates negative radar change; amber/orange indicates positive radar change; transparent/masked indicates invalid observation."
        )
        return spec, interp

    if layer_type in ("magnitude_hh", "magnitude_hv"):
        spec = LayerLegendSpec(
            title=f"Absolute Radar Change |Δ{pol_str}| (dB)",
            units="dB",
            min_value=0.0,
            max_value=5.0,
            palette_type="magnitude_sequential_db",
            stops=[
                {"value": 0.0, "color": "#0f172a", "label": "0.0 dB (Minimal magnitude)"},
                {"value": 1.75, "color": "#0d9488", "label": "1.75 dB (Moderate |Δ|)"},
                {"value": 3.5, "color": "#eab308", "label": "3.5 dB (Elevated |Δ|)"},
                {"value": 5.0, "color": "#fef08a", "label": "≥5.0 dB (Large |Δ| magnitude)"},
            ],
        )
        interp = f"Sign-agnostic {pol_str} radar change magnitude |Δ{pol_str}| = abs(B_T1 - B_T0) in dB."
        return spec, interp

    if layer_type == "combined_change":
        spec = LayerLegendSpec(
            title="Combined Radar Change (|ΔHH| + |ΔHV|, dB composite)",
            units="dB composite",
            min_value=0.0,
            max_value=8.0,
            palette_type="magnitude_sequential_db",
            stops=[
                {"value": 0.0, "color": "#111827", "label": "0.0 dB composite"},
                {"value": 2.6, "color": "#2563eb", "label": "2.6 dB composite"},
                {"value": 5.3, "color": "#10b981", "label": "5.3 dB composite"},
                {"value": 8.0, "color": "#f59e0b", "label": "≥8.0 dB composite (|ΔHH| + |ΔHV|)"},
            ],
        )
        interp = (
            "Combined Radar Change D = abs(Delta_HH) + abs(Delta_HV) [dB composite: custom change magnitude (sum of absolute dB changes)]. "
            f"{COMBINED_RADAR_CHANGE_DISCLAIMER}"
        )
        return spec, interp

    spec = LayerLegendSpec(
        title="Common Scientific Validity Mask (T0 ∩ T1)",
        units="class",
        min_value=0.0,
        max_value=1.0,
        palette_type="validity_mask",
        stops=[
            {
                "value": 1.0,
                "color": "#10b981",
                "label": "Valid comparable pixel (0 < mask < 255 & finite P > 0 in both T0 and T1)",
            },
            {
                "value": 0.0,
                "color": "#e11d48",
                "label": "Invalid / unavailable observation (mask == 0, mask == 255, or non-positive power)",
            },
        ],
    )
    interp = (
        "Official NISAR GCOV multi-temporal validity mask: Emerald (1) = valid comparable pixel; "
        "Rose (0) = rejected pixel (mask == 0 partially focused, mask == 255 outside swath, or P <= 0)."
    )
    return spec, interp


def export_analysis_png_layers(
    res: AOIChangeResult,
    *,
    case_id: str,
    png_dir: pathlib.Path,
) -> dict[str, LayerMetadataResponse]:
    """Render all available radar layers from `AOIChangeResult` into WGS84 PNGs and return metadata."""
    png_dir.mkdir(parents=True, exist_ok=True)
    ev = res.evidence_record
    src_epsg = res.grid.epsg
    src_bounds = res.window.clipped_bbox_utm or res.window.requested_bbox_utm
    prov = (
        ev.processing_metadata.model_dump()
        if hasattr(ev.processing_metadata, "model_dump")
        else dict(ev.processing_metadata)
    )
    t0_utc = str(prov.get("t0_acquisition_utc") or "")
    t1_utc = str(prov.get("t1_acquisition_utc") or "")

    raw_layers: list[tuple[str, str, PolarizationChannel | None, np.ndarray | None]] = [
        ("t0_hh", "T0 HH Backscatter (dB)", PolarizationChannel.HH, res.t0_hh_db),
        ("t1_hh", "T1 HH Backscatter (dB)", PolarizationChannel.HH, res.t1_hh_db),
        ("t0_hv", "T0 HV Backscatter (dB)", PolarizationChannel.HV, res.t0_hv_db),
        ("t1_hv", "T1 HV Backscatter (dB)", PolarizationChannel.HV, res.t1_hv_db),
        ("delta_hh", "Signed ΔHH (dB)", PolarizationChannel.HH, res.delta_hh_db),
        ("delta_hv", "Signed ΔHV (dB)", PolarizationChannel.HV, res.delta_hv_db),
        ("magnitude_hh", "Absolute Change |ΔHH| (dB)", PolarizationChannel.HH, res.magnitude_hh_db),
        ("magnitude_hv", "Absolute Change |ΔHV| (dB)", PolarizationChannel.HV, res.magnitude_hv_db),
        (
            "combined_change",
            "Combined Radar Change (|ΔHH| + |ΔHV|, dB composite)",
            None,
            res.combined_radar_change.data if res.combined_radar_change is not None else None,
        ),
        (
            "validity_mask",
            "Scientific Validity Mask (T0 ∩ T1)",
            None,
            res.mask_bundle.common_valid_mask.astype(np.float32),
        ),
    ]

    layers_out: dict[str, LayerMetadataResponse] = {}
    for ltype, title, pol, arr in raw_layers:
        if arr is None or arr.size == 0:
            continue

        legend, color_interp = build_legend_for_layer(ltype, pol)
        arr_wgs84, bbox_wgs84 = reproject_window_to_wgs84(
            arr,
            src_epsg=src_epsg,
            src_bounds_utm=src_bounds,
            is_mask=(ltype == "validity_mask"),
        )
        rgba = render_layer_rgba(
            arr_wgs84,
            layer_type=ltype,
            min_val=legend.min_value,
            max_val=legend.max_value,
        )
        png_bytes = encode_rgba_png(rgba)

        layer_id = f"{ev.evidence_id}_{ltype}"
        png_path = png_dir / f"{layer_id}.png"
        png_path.write_bytes(png_bytes)

        layers_out[ltype] = LayerMetadataResponse(
            layer_id=layer_id,
            case_id=case_id,
            evidence_id=ev.evidence_id,
            roi_id=res.roi_id,
            layer_type=ltype,  # type: ignore[arg-type]
            title=title,
            polarization=pol,
            units=legend.units,
            source_scenes=list(ev.scene_ids),
            t0_acquisition_utc=t0_utc,
            t1_acquisition_utc=t1_utc if not ltype.startswith("t0_") else None,
            bbox_wgs84=bbox_wgs84,
            crs_epsg=4326,
            width=int(rgba.shape[1]),
            height=int(rgba.shape[0]),
            image_url=f"/api/layers/{layer_id}/image.png",
            color_interpretation=color_interp,
            legend=legend,
            disclaimer=COMBINED_RADAR_CHANGE_DISCLAIMER if ltype == "combined_change" else None,
            limitations=list(ev.limitations),
        )

    return layers_out
