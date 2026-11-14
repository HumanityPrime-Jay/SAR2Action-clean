"""Deterministic AOI statistics and EvidenceRecord generation (Phase 2A.6 & 2A.7).

Enforces:
- Full percentile distributions (`p10`, `p25`, `p50`, `p75`, `p90`), median/mean T0, T1,
  signed Delta, absolute change |Delta|, positive-change fraction, negative-change fraction,
  valid pixel count, valid area (`m2`, `ha`, `km2`), and missing/invalid fraction.
- `numberOfLooks` is recorded strictly as observation metadata and never converted into
  arbitrary confidence classes or confidence scores.
- Every AOI analysis generates a validated `EvidenceRecord` with mandatory `"cause_not_determined"`
  and `"provisional_product"` limitations (where applicable) and zero wildfire attribution.
"""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np

from backend.app.schemas.evidence import (
    COMBINED_RADAR_CHANGE_DISCLAIMER,
    CombinedRadarChangeMetric,
    DistributionStatsDb,
    EvidenceRecord,
    EvidenceType,
    PolarizationChannel,
    ProcessingProvenanceMetadata,
    ScienceQualityStatus,
)
from sar.change.delta import CombinedRadarChangeLayer
from sar.change.masks import MASK_RULE_SPECIFICATION, MultiTemporalMaskBundle


def compute_distribution_stats_db(
    arr_db: np.ndarray,
    valid_mask: np.ndarray,
) -> DistributionStatsDb | None:
    """Compute `DistributionStatsDb` (`mean`, `median`, `std`, `min`, `max`, `p10..p90`) on valid pixels."""
    vals = np.asarray(arr_db, dtype=np.float64)[np.asarray(valid_mask, dtype=bool)]
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return None

    p10, p25, p50, p75, p90 = (
        float(v) for v in np.percentile(vals, [10.0, 25.0, 50.0, 75.0, 90.0])
    )
    return DistributionStatsDb(
        mean=round(float(vals.mean()), 4),
        median=round(p50, 4),
        std=round(float(vals.std()), 4),
        min=round(float(vals.min()), 4),
        max=round(float(vals.max()), 4),
        p10=round(p10, 4),
        p25=round(p25, 4),
        p50=round(p50, 4),
        p75=round(p75, 4),
        p90=round(p90, 4),
    )


def compute_polarization_aoi_statistics(
    *,
    polarization: str,
    t0_db: np.ndarray,
    t1_db: np.ndarray,
    delta_db: np.ndarray,
    magnitude_db: np.ndarray,
    common_valid_mask: np.ndarray,
    aoi_footprint_mask: np.ndarray,
    pixel_area_m2: float = 100.0,
) -> dict[str, Any]:
    """Compute all Phase 2A.6 deterministic statistics for a single polarization channel."""
    aoi_mask = np.asarray(aoi_footprint_mask, dtype=bool)
    valid_mask = np.asarray(common_valid_mask, dtype=bool) & aoi_mask

    total_aoi_pixels = int(aoi_mask.sum())
    valid_pixels = int(valid_mask.sum())
    missing_pixels = max(0, total_aoi_pixels - valid_pixels)

    coverage_ratio = round(float(valid_pixels / total_aoi_pixels), 6) if total_aoi_pixels > 0 else 0.0
    missing_fraction = round(1.0 - coverage_ratio, 6) if total_aoi_pixels > 0 else 1.0

    valid_area_m2 = round(float(valid_pixels * pixel_area_m2), 2)
    valid_area_ha = round(float(valid_area_m2 / 1e4), 4)
    valid_area_km2 = round(float(valid_area_m2 / 1e6), 6)

    t0_stats = compute_distribution_stats_db(t0_db, valid_mask)
    t1_stats = compute_distribution_stats_db(t1_db, valid_mask)
    delta_stats = compute_distribution_stats_db(delta_db, valid_mask)
    mag_stats = compute_distribution_stats_db(magnitude_db, valid_mask)

    if valid_pixels > 0 and delta_stats is not None and mag_stats is not None:
        d_vals = np.asarray(delta_db, dtype=np.float64)[valid_mask]
        d_vals = d_vals[np.isfinite(d_vals)]
        n_d = int(d_vals.size)
        pos_frac = round(float((d_vals > 0.0).sum() / n_d), 6) if n_d > 0 else 0.0
        neg_frac = round(float((d_vals < 0.0).sum() / n_d), 6) if n_d > 0 else 0.0
        zero_frac = round(float((d_vals == 0.0).sum() / n_d), 6) if n_d > 0 else 0.0

        return {
            "polarization": polarization,
            "total_aoi_pixel_count": total_aoi_pixels,
            "valid_pixel_count": valid_pixels,
            "missing_invalid_pixel_count": missing_pixels,
            "valid_area_m2": valid_area_m2,
            "valid_area_ha": valid_area_ha,
            "valid_area_km2": valid_area_km2,
            "coverage_ratio": coverage_ratio,
            "missing_invalid_fraction": missing_fraction,
            "median_t0_db": t0_stats.median if t0_stats else None,
            "mean_t0_db": t0_stats.mean if t0_stats else None,
            "median_t1_db": t1_stats.median if t1_stats else None,
            "mean_t1_db": t1_stats.mean if t1_stats else None,
            "median_delta_db": delta_stats.median,
            "mean_delta_db": delta_stats.mean,
            "p10_delta_db": delta_stats.p10,
            "p25_delta_db": delta_stats.p25,
            "p50_delta_db": delta_stats.p50,
            "p75_delta_db": delta_stats.p75,
            "p90_delta_db": delta_stats.p90,
            "median_abs_change_db": mag_stats.median,
            "mean_abs_change_db": mag_stats.mean,
            "p10_abs_change_db": mag_stats.p10,
            "p25_abs_change_db": mag_stats.p25,
            "p50_abs_change_db": mag_stats.p50,
            "p75_abs_change_db": mag_stats.p75,
            "p90_abs_change_db": mag_stats.p90,
            "positive_change_fraction": pos_frac,
            "negative_change_fraction": neg_frac,
            "zero_change_fraction": zero_frac,
            "t0_distribution_db": t0_stats.model_dump(mode="json") if t0_stats else None,
            "t1_distribution_db": t1_stats.model_dump(mode="json") if t1_stats else None,
            "delta_distribution_db": delta_stats.model_dump(mode="json"),
            "magnitude_distribution_db": mag_stats.model_dump(mode="json"),
        }

    return {
        "polarization": polarization,
        "total_aoi_pixel_count": total_aoi_pixels,
        "valid_pixel_count": 0,
        "missing_invalid_pixel_count": total_aoi_pixels,
        "valid_area_m2": 0.0,
        "valid_area_ha": 0.0,
        "valid_area_km2": 0.0,
        "coverage_ratio": 0.0,
        "missing_invalid_fraction": 1.0,
        "median_t0_db": None,
        "mean_t0_db": None,
        "median_t1_db": None,
        "mean_t1_db": None,
        "median_delta_db": None,
        "mean_delta_db": None,
        "p10_delta_db": None,
        "p25_delta_db": None,
        "p50_delta_db": None,
        "p75_delta_db": None,
        "p90_delta_db": None,
        "median_abs_change_db": None,
        "mean_abs_change_db": None,
        "p10_abs_change_db": None,
        "p25_abs_change_db": None,
        "p50_abs_change_db": None,
        "p75_abs_change_db": None,
        "p90_abs_change_db": None,
        "positive_change_fraction": None,
        "negative_change_fraction": None,
        "zero_change_fraction": None,
        "t0_distribution_db": None,
        "t1_distribution_db": None,
        "delta_distribution_db": None,
        "magnitude_distribution_db": None,
    }


def summarize_number_of_looks_metadata(
    looks_t0: np.ndarray | None,
    looks_t1: np.ndarray | None,
    common_valid_mask: np.ndarray,
) -> dict[str, Any]:
    """Summarize `numberOfLooks` strictly as observation metadata (never as a confidence score)."""
    vm = np.asarray(common_valid_mask, dtype=bool)
    out: dict[str, Any] = {
        "note": "numberOfLooks is recorded strictly as radar observation metadata and is not converted into confidence classes.",
        "t0": None,
        "t1": None,
    }
    for key, arr in (("t0", looks_t0), ("t1", looks_t1)):
        if arr is not None and vm.shape == arr.shape and np.any(vm):
            vals = np.asarray(arr, dtype=np.float64)[vm]
            vals = vals[np.isfinite(vals) & (vals > 0.0)]
            if vals.size > 0:
                p10, p50, p90 = (float(v) for v in np.percentile(vals, [10.0, 50.0, 90.0]))
                out[key] = {
                    "mean_looks": round(float(vals.mean()), 4),
                    "median_looks": round(p50, 4),
                    "min_looks": round(float(vals.min()), 4),
                    "max_looks": round(float(vals.max()), 4),
                    "p10_looks": round(p10, 4),
                    "p90_looks": round(p90, 4),
                }
    return out


def determine_quality_status(
    *,
    valid_pixel_count: int,
    coverage_ratio: float,
    available_polarizations: list[str],
    partly_outside_grid: bool,
    fully_outside_grid: bool,
) -> ScienceQualityStatus:
    """Assign the mandatory Unknown-Aware epistemic state (`COMPARABLE`, `LIMITED`, `INSUFFICIENT_EVIDENCE`)."""
    if fully_outside_grid or valid_pixel_count == 0 or len(available_polarizations) == 0:
        return ScienceQualityStatus.INSUFFICIENT_EVIDENCE
    if coverage_ratio < 0.10:
        return ScienceQualityStatus.INSUFFICIENT_EVIDENCE
    if (
        coverage_ratio < 0.50
        or partly_outside_grid
        or not ({"HH", "HV"}.issubset(set(available_polarizations)))
    ):
        return ScienceQualityStatus.LIMITED
    return ScienceQualityStatus.COMPARABLE


def build_aoi_evidence_record(
    *,
    evidence_id: str,
    roi_id: str,
    scene_ids: list[str],
    t0_acquisition_utc: str,
    t1_acquisition_utc: str,
    aoi_geometry_wgs84: dict[str, Any],
    mask_bundle: MultiTemporalMaskBundle,
    per_pol_stats: dict[str, dict[str, Any]],
    combined_layer: CombinedRadarChangeLayer | None,
    looks_metadata: dict[str, Any],
    pixel_area_m2: float,
    requested_pixel_count: int,
    partly_outside_grid: bool,
    fully_outside_grid: bool,
    crs_epsg: int,
    pixel_spacing_m: tuple[float, float],
    orbit_pass_direction: str | None,
    look_direction: str | None,
    t0_crid: str | None,
    t1_crid: str | None,
    data_maturity: str = "PROVISIONAL",
    product_type: str = "NISAR_L2_GCOV",
    frequency_band: str = "L",
    frequency_group: str = "frequencyA",
    algorithm_version: str = "sar2action-change-engine-v1.0.0",
) -> EvidenceRecord:
    """Construct a fully populated, Science-Contract-compliant `EvidenceRecord` (Phase 2A.7)."""
    avail_pols_enum = [
        PolarizationChannel(p)
        for p in mask_bundle.available_polarizations
        if p in PolarizationChannel.__members__
    ]

    window_aoi_pixels = int(mask_bundle.aoi_footprint_mask.sum())
    # If AOI was partly or fully outside the scene grid, the denominator for total AOI coverage
    # uses max(requested_pixel_count, window_aoi_pixels) so out-of-frame pixels count toward missing_data_ratio.
    effective_total_aoi_pixels = max(int(requested_pixel_count), window_aoi_pixels)
    common_valid_pixels = int(mask_bundle.common_valid_mask.sum())

    if effective_total_aoi_pixels > 0 and not fully_outside_grid:
        coverage_ratio = round(
            min(1.0, max(0.0, float(common_valid_pixels / effective_total_aoi_pixels))), 6
        )
        missing_data_ratio = round(1.0 - coverage_ratio, 6)
    else:
        coverage_ratio = 0.0
        missing_data_ratio = 1.0

    valid_area_m2 = round(float(common_valid_pixels * pixel_area_m2), 2)
    valid_area_ha = round(float(valid_area_m2 / 1e4), 4)
    valid_area_km2 = round(float(valid_area_m2 / 1e6), 6)

    quality_status = determine_quality_status(
        valid_pixel_count=common_valid_pixels,
        coverage_ratio=coverage_ratio,
        available_polarizations=mask_bundle.available_polarizations,
        partly_outside_grid=partly_outside_grid,
        fully_outside_grid=fully_outside_grid,
    )

    t0_db_map: dict[PolarizationChannel, DistributionStatsDb] = {}
    t1_db_map: dict[PolarizationChannel, DistributionStatsDb] = {}
    delta_db_map: dict[PolarizationChannel, DistributionStatsDb] = {}
    mag_db_map: dict[PolarizationChannel, DistributionStatsDb] = {}

    for pol_enum in avail_pols_enum:
        pstat = per_pol_stats.get(pol_enum.value)
        if pstat and pstat.get("valid_pixel_count", 0) > 0:
            t0_db_map[pol_enum] = DistributionStatsDb.model_validate(pstat["t0_distribution_db"])
            t1_db_map[pol_enum] = DistributionStatsDb.model_validate(pstat["t1_distribution_db"])
            delta_db_map[pol_enum] = DistributionStatsDb.model_validate(
                pstat["delta_distribution_db"]
            )
            mag_db_map[pol_enum] = DistributionStatsDb.model_validate(
                pstat["magnitude_distribution_db"]
            )

    combined_metric: CombinedRadarChangeMetric | None = None
    if (
        combined_layer is not None
        and {PolarizationChannel.HH, PolarizationChannel.HV}.issubset(set(avail_pols_enum))
        and common_valid_pixels > 0
    ):
        c_stats = compute_distribution_stats_db(combined_layer.data, mask_bundle.common_valid_mask)
        if c_stats is not None:
            combined_metric = CombinedRadarChangeMetric(
                metric_name="Combined Radar Change",
                disclaimer=COMBINED_RADAR_CHANGE_DISCLAIMER,
                stats=c_stats,
            )

    limitations: list[str] = ["cause_not_determined", "not_burn_severity_or_fire_damage"]
    if "PROVISIONAL" in (data_maturity or "").upper() or (
        (t0_crid and t0_crid.startswith("P")) or (t1_crid and t1_crid.startswith("P"))
    ):
        limitations.append("provisional_product")
    if "HH" in mask_bundle.unavailable_polarizations:
        limitations.append("hh_polarization_unavailable")
    if "HV" in mask_bundle.unavailable_polarizations:
        limitations.append("hv_polarization_unavailable")
    if fully_outside_grid:
        limitations.append("aoi_fully_outside_coverage")
    elif partly_outside_grid:
        limitations.append("aoi_partly_outside_coverage")
    if 0.0 < coverage_ratio < 0.80:
        limitations.append("partial_valid_coverage")

    summary_statistics: dict[str, Any] = {
        "mask_rule": MASK_RULE_SPECIFICATION,
        "data_maturity": data_maturity,
        "requested_pixel_count": effective_total_aoi_pixels,
        "window_aoi_pixel_count": window_aoi_pixels,
        "valid_pixel_count": common_valid_pixels,
        "missing_invalid_pixel_count": max(0, effective_total_aoi_pixels - common_valid_pixels),
        "valid_area_m2": valid_area_m2,
        "valid_area_ha": valid_area_ha,
        "valid_area_km2": valid_area_km2,
        "missing_invalid_fraction": missing_data_ratio,
        "partly_outside_grid": partly_outside_grid,
        "fully_outside_grid": fully_outside_grid,
        "per_polarization": per_pol_stats,
        "mask_diagnostics": mask_bundle.diagnostics,
        "number_of_looks_metadata": looks_metadata,
    }
    if combined_metric is not None:
        summary_statistics["combined_radar_change"] = {
            "metric_name": combined_metric.metric_name,
            "disclaimer": combined_metric.disclaimer,
            "stats_db": combined_metric.stats.model_dump(mode="json"),
        }

    prov = ProcessingProvenanceMetadata(
        t0_acquisition_utc=t0_acquisition_utc,
        t1_acquisition_utc=t1_acquisition_utc,
        product_type=product_type,
        frequency_band="L" if frequency_band.upper() == "L" else "S",
        frequency_group=frequency_group,
        orbit_pass_direction=orbit_pass_direction,
        look_direction=look_direction,
        t0_crid=t0_crid,
        t1_crid=t1_crid,
        crs_epsg=crs_epsg,
        pixel_spacing_m=(abs(float(pixel_spacing_m[0])), abs(float(pixel_spacing_m[1]))),
        computed_at_utc=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        data_maturity=data_maturity,
        mask_rule=MASK_RULE_SPECIFICATION,
        valid_area_m2=valid_area_m2,
        valid_area_km2=valid_area_km2,
    )

    return EvidenceRecord(
        evidence_id=evidence_id,
        evidence_type=EvidenceType.RADAR_CHANGE,
        scene_ids=scene_ids,
        roi_id=roi_id,
        geometry=aoi_geometry_wgs84,
        polarizations=avail_pols_enum,
        t0_db=t0_db_map,
        t1_db=t1_db_map,
        delta_db=delta_db_map,
        magnitude_db=mag_db_map,
        combined_change_db=combined_metric,
        summary_statistics=summary_statistics,
        valid_pixel_count=common_valid_pixels,
        coverage_ratio=coverage_ratio,
        missing_data_ratio=missing_data_ratio,
        quality_status=quality_status,
        algorithm_version=algorithm_version,
        processing_metadata=prov,
        limitations=limitations,
    )
