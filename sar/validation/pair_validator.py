"""Deterministic Scene Pair Compatibility Gate (`validate_scene_pair` v1) & Metadata Pair Screener.

Implements:
- `validate_scene_pair(scene_a, scene_b, aoi)` -> `ScenePairValidationResult`
  Distinguishes:
  - `PASS` (`compatible=True`, `science_status="COMPARABLE"`)
  - `CONDITIONAL` (`compatible=True`, `science_status="LIMITED"`, with explicit `warnings`)
  - `FAIL` (`compatible=False`, `science_status="INSUFFICIENT_EVIDENCE"`, with explicit `reasons`)
- `screen_candidate_pairs(scenes, aoi_bbox)` -> `list[ScreenedCandidatePair]`
  First-stage catalog metadata screening labeled `CATALOG_SCREENED` / `CONDITIONAL` / `FAIL`
  (never claiming final `COMPARABLE` before HDF5 grid/mask verification).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from shapely.geometry import box, shape
from shapely.geometry.base import BaseGeometry

from backend.app.schemas.evidence import (
    PolarizationChannel,
    ScenePairValidationResult,
    ScienceQualityStatus,
)
from sar.catalog.models import (
    CatalogScreeningStatus,
    NormalizedSceneMetadata,
    ScreenedCandidatePair,
)

MIN_SPATIAL_OVERLAP_RATIO = 0.10
COMPARABLE_OVERLAP_RATIO = 0.50


def _coerce_scene(scene: NormalizedSceneMetadata | dict[str, Any]) -> NormalizedSceneMetadata:
    if isinstance(scene, NormalizedSceneMetadata):
        return scene
    return NormalizedSceneMetadata.model_validate(scene)


def _parse_iso_utc(ts: str | None) -> datetime | None:
    if not ts:
        return None
    clean = ts.strip()
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(clean)
    except ValueError:
        return None


def _scene_to_geometry(scene: NormalizedSceneMetadata) -> BaseGeometry | None:
    if scene.illuminated_geometry:
        try:
            geom = shape(scene.illuminated_geometry)
            if geom.is_valid and not geom.is_empty:
                return geom
        except Exception:
            pass
    if scene.illuminated_bbox and len(scene.illuminated_bbox) == 4:
        w, s, e, n = scene.illuminated_bbox
        if w < e and s < n:
            return box(w, s, e, n)
    if scene.bounding_geometry:
        try:
            geom = shape(scene.bounding_geometry)
            if geom.is_valid and not geom.is_empty:
                return geom
        except Exception:
            pass
    if scene.bbox and len(scene.bbox) == 4:
        w, s, e, n = scene.bbox
        if w < e and s < n:
            return box(w, s, e, n)
    return None


def _aoi_to_geometry(aoi: list[float] | dict[str, Any] | BaseGeometry | None) -> BaseGeometry | None:
    if aoi is None:
        return None
    if isinstance(aoi, BaseGeometry):
        return aoi
    if isinstance(aoi, (list, tuple)) and len(aoi) == 4:
        w, s, e, n = (float(v) for v in aoi)
        if w < e and s < n:
            return box(w, s, e, n)
    if isinstance(aoi, dict):
        if "type" in aoi and "coordinates" in aoi:
            return shape(aoi)
        if "bbox" in aoi and len(aoi["bbox"]) == 4:
            w, s, e, n = (float(v) for v in aoi["bbox"])
            return box(w, s, e, n)
    return None


def compute_spatial_overlap_ratios(
    scene_a: NormalizedSceneMetadata,
    scene_b: NormalizedSceneMetadata,
    aoi: list[float] | dict[str, Any] | BaseGeometry | None = None,
) -> tuple[float | None, float | None]:
    """Compute (pair_intersection_ratio, aoi_overlap_ratio) in [0.0, 1.0].

    - `pair_intersection_ratio`: intersection(A, B).area / min(A.area, B.area)
    - `aoi_overlap_ratio`: intersection(A, B, AOI).area / AOI.area (or equal to pair_intersection_ratio if AOI is None)
    """
    geom_a = _scene_to_geometry(scene_a)
    geom_b = _scene_to_geometry(scene_b)
    if geom_a is None or geom_b is None:
        return None, None

    inter_ab = geom_a.intersection(geom_b)
    min_scene_area = min(geom_a.area, geom_b.area)
    if min_scene_area <= 0.0:
        return 0.0, 0.0
    pair_ratio = max(0.0, min(1.0, float(inter_ab.area / min_scene_area)))

    geom_aoi = _aoi_to_geometry(aoi)
    if geom_aoi is None or geom_aoi.area <= 0.0:
        return pair_ratio, pair_ratio

    inter_aoi = inter_ab.intersection(geom_aoi)
    aoi_ratio = max(0.0, min(1.0, float(inter_aoi.area / geom_aoi.area)))
    return pair_ratio, aoi_ratio


def validate_scene_pair(
    scene_a: NormalizedSceneMetadata | dict[str, Any],
    scene_b: NormalizedSceneMetadata | dict[str, Any],
    aoi: list[float] | dict[str, Any] | BaseGeometry | None = None,
) -> ScenePairValidationResult:
    """Deterministically evaluate scientific comparability between two NISAR GCOV scenes.

    Distinguishes:
    - `PASS`: All mandatory and optional compatibility metadata checks succeed.
    - `CONDITIONAL`: No hard scientific violation, but missing metadata (e.g., unknown polarization,
      null CRID, missing track/frame) or maturity mismatch (e.g., BETA vs PROVISIONAL) requires
      inspection/caveats (`science_status = "LIMITED"`).
    - `FAIL`: Violates mandatory Science Contract rules (same date, wrong band/product, no spatial
      overlap, disjoint polarizations, or opposite orbit pass/look direction). Stops change computation.
    """
    sa = _coerce_scene(scene_a)
    sb = _coerce_scene(scene_b)

    reasons: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    # 1. Temporal distinctness check
    dt_a = _parse_iso_utc(sa.acquisition_start_utc)
    dt_b = _parse_iso_utc(sb.acquisition_start_utc)
    delta_days: float | None = None
    if sa.scene_id == sb.scene_id:
        reasons.append("Identical scene_id provided for both T0 and T1.")
        checks["temporal_distinct"] = "FAIL"
    elif dt_a is not None and dt_b is not None:
        delta_seconds = abs((dt_b - dt_a).total_seconds())
        delta_days = round(delta_seconds / 86400.0, 4)
        if delta_seconds < 60.0:
            reasons.append(
                f"Scenes have identical or near-simultaneous acquisition timestamps ({sa.acquisition_start_utc})."
            )
            checks["temporal_distinct"] = "FAIL"
        else:
            checks["temporal_distinct"] = "PASS"
            checks["delta_days"] = delta_days
    elif sa.acquisition_start_utc and sb.acquisition_start_utc:
        if sa.acquisition_start_utc == sb.acquisition_start_utc:
            reasons.append(f"Scenes share identical acquisition timestamp ({sa.acquisition_start_utc}).")
            checks["temporal_distinct"] = "FAIL"
        else:
            checks["temporal_distinct"] = "PASS"
    else:
        warnings.append("Acquisition UTC timestamp is missing on one or both scenes; requires HDF5 check.")
        checks["temporal_distinct"] = "CONDITIONAL"

    # 2. Product type & radar frequency band check
    prod_a = (sa.product_type or "").upper()
    prod_b = (sb.product_type or "").upper()
    if prod_a != "GCOV" or prod_b != "GCOV":
        reasons.append(
            f"Product type mismatch or non-GCOV product ({sa.product_type!r} vs {sb.product_type!r}); "
            "SAR2Action MVP requires NISAR L-band Level-2 GCOV."
        )
        checks["product_type_check"] = "FAIL"
    else:
        checks["product_type_check"] = "PASS"

    band_a = (sa.band or "").upper()
    band_b = (sb.band or "").upper()
    if band_a != "L" or band_b != "L":
        reasons.append(
            f"Radar band mismatch or non-L-band scene ({sa.band!r} vs {sb.band!r}); "
            "NISAR L-band GCOV is required."
        )
        checks["band_check"] = "FAIL"
    else:
        checks["band_check"] = "PASS"

    # 3. Spatial overlap check
    pair_overlap, aoi_overlap = compute_spatial_overlap_ratios(sa, sb, aoi)
    effective_spatial_overlap = aoi_overlap if aoi is not None else pair_overlap
    if effective_spatial_overlap is None:
        warnings.append("Spatial footprint/bbox metadata missing; spatial overlap requires HDF5 grid check.")
        checks["spatial_overlap"] = "CONDITIONAL"
        spatial_overlap_val = 0.0
    else:
        spatial_overlap_val = effective_spatial_overlap
        checks["pair_footprint_overlap_ratio"] = round(pair_overlap or 0.0, 4)
        checks["effective_spatial_overlap_ratio"] = round(effective_spatial_overlap, 4)
        if (pair_overlap is not None and pair_overlap <= 0.0) or (
            effective_spatial_overlap < MIN_SPATIAL_OVERLAP_RATIO
        ):
            reasons.append(
                f"Insufficient spatial overlap ({effective_spatial_overlap:.1%} < {MIN_SPATIAL_OVERLAP_RATIO:.0%} minimum)."
            )
            checks["spatial_overlap"] = "FAIL"
        elif effective_spatial_overlap < COMPARABLE_OVERLAP_RATIO:
            warnings.append(
                f"Partial spatial overlap with target region ({effective_spatial_overlap:.1%}); "
                "valid coverage will be limited."
            )
            checks["spatial_overlap"] = "CONDITIONAL"
        else:
            checks["spatial_overlap"] = "PASS"

    # 3b. Actual SAR illumination check (Phase 2B.1 / Gate A.2 rule: CMR frame bbox != actual illumination)
    for label, sc in (("T0", sa), ("T1", sb)):
        if sc.is_full_frame is False and sc.illuminated_geometry is None and sc.illuminated_bbox is None:
            warnings.append(
                f"{label} ({sc.scene_id}) is a partial-frame acquisition (isFullFrame=False) without verified "
                "_LATLON.kml / boundingPolygon illuminated footprint; CMR frame-grid bbox alone is insufficient."
            )
            checks["illumination_check"] = "CONDITIONAL"
    if "illumination_check" not in checks:
        checks["illumination_check"] = "PASS"

    # 4. Polarization availability check (Null-safe: never invent missing polarizations)
    avail_pols: list[PolarizationChannel] = []
    if sa.polarizations is None or sb.polarizations is None:
        warnings.append(
            "Polarization list is missing in catalog metadata for one or both scenes; "
            "must verify `/science/LSAR/GCOV/grids/frequencyA/listOfPolarizations` in HDF5."
        )
        checks["polarization_check"] = "CONDITIONAL"
    else:
        set_a = {p.upper() for p in sa.polarizations}
        set_b = {p.upper() for p in sb.polarizations}
        shared = sorted(set_a.intersection(set_b))
        for p in shared:
            if p in PolarizationChannel.__members__:
                avail_pols.append(PolarizationChannel(p))
        if not avail_pols:
            reasons.append(
                f"No shared usable polarization between T0 ({sa.polarizations}) and T1 ({sb.polarizations})."
            )
            checks["polarization_check"] = "FAIL"
        else:
            checks["polarization_check"] = "PASS"
            if set_a != set_b:
                warnings.append(
                    f"Partial polarization match: T0 has {sorted(set_a)}, T1 has {sorted(set_b)}; "
                    f"restricting comparison to shared channels {[p.value for p in avail_pols]}."
                )

    # 5. Orbit pass direction & viewing geometry check
    same_orbit_pass: bool | None = None
    if sa.orbit_direction and sb.orbit_direction:
        same_orbit_pass = sa.orbit_direction.upper() == sb.orbit_direction.upper()
        if not same_orbit_pass:
            reasons.append(
                f"Incompatible orbit pass direction ({sa.orbit_direction} vs {sb.orbit_direction})."
            )
            checks["orbit_direction_check"] = "FAIL"
        else:
            checks["orbit_direction_check"] = "PASS"
    else:
        warnings.append("Orbit pass direction metadata missing on one or both scenes.")
        checks["orbit_direction_check"] = "CONDITIONAL"

    same_look_dir: bool | None = None
    if sa.look_direction and sb.look_direction:
        same_look_dir = sa.look_direction.upper() == sb.look_direction.upper()
        if not same_look_dir:
            reasons.append(
                f"Incompatible antenna look direction ({sa.look_direction} vs {sb.look_direction})."
            )
            checks["look_direction_check"] = "FAIL"
        else:
            checks["look_direction_check"] = "PASS"
    else:
        warnings.append("Look direction not specified in catalog metadata (NISAR LSAR nominal is Right-looking).")
        checks["look_direction_check"] = "CONDITIONAL"

    # Track / frame repeat-pass geometry check
    if sa.track_or_frame and sb.track_or_frame:
        if sa.track_or_frame != sb.track_or_frame:
            warnings.append(
                f"Different track/frame identifiers ({sa.track_or_frame} vs {sb.track_or_frame}); "
                "incidence angle differences may exist across adjacent tracks."
            )
            checks["track_frame_check"] = "CONDITIONAL"
        else:
            checks["track_frame_check"] = "PASS"
    else:
        warnings.append("Track/frame identifier missing in metadata.")
        checks["track_frame_check"] = "CONDITIONAL"

    # 6. Product maturity check (e.g. BETA vs PROVISIONAL)
    if sa.product_maturity and sb.product_maturity:
        if sa.product_maturity.upper() != sb.product_maturity.upper():
            warnings.append(
                f"Product maturity mismatch ({sa.product_maturity} vs {sb.product_maturity}); "
                "calibration or algorithm differences may affect backscatter comparisons."
            )
            checks["maturity_check"] = "CONDITIONAL"
        else:
            checks["maturity_check"] = "PASS"
    else:
        warnings.append("Product maturity metadata missing on one or both scenes.")
        checks["maturity_check"] = "CONDITIONAL"

    # 7. CRID & processing version check
    if sa.crid and sb.crid:
        if sa.crid != sb.crid:
            warnings.append(
                f"CRID version difference between T0 ({sa.crid}) and T1 ({sb.crid})."
            )
            checks["crid_check"] = "CONDITIONAL"
        else:
            checks["crid_check"] = "PASS"
    else:
        warnings.append("CRID is null/unknown in metadata for one or both scenes.")
        checks["crid_check"] = "CONDITIONAL"

    if sa.processing_version and sb.processing_version:
        if sa.processing_version != sb.processing_version:
            warnings.append(
                f"Processing version difference ({sa.processing_version} vs {sb.processing_version})."
            )
            checks["processing_version_check"] = "CONDITIONAL"
        else:
            checks["processing_version_check"] = "PASS"
    else:
        warnings.append("Processing version is null/unknown in metadata for one or both scenes.")
        checks["processing_version_check"] = "CONDITIONAL"

    # 8. Grid spacing check (optional metadata)
    if sa.grid_spacing_m is not None and sb.grid_spacing_m is not None:
        if abs(sa.grid_spacing_m - sb.grid_spacing_m) > 1e-3:
            warnings.append(
                f"Nominal grid spacing differs ({sa.grid_spacing_m} m vs {sb.grid_spacing_m} m); "
                "grid resampling will be required."
            )
            checks["grid_spacing_check"] = "CONDITIONAL"
        else:
            checks["grid_spacing_check"] = "PASS"
    else:
        warnings.append("Nominal grid spacing not present in catalog metadata; requires HDF5 grid check.")
        checks["grid_spacing_check"] = "CONDITIONAL"

    # Final decision synthesis
    if reasons:
        return ScenePairValidationResult(
            compatible=False,
            validation_decision="FAIL",
            science_status=ScienceQualityStatus.INSUFFICIENT_EVIDENCE,
            scene_ids=[sa.scene_id, sb.scene_id],
            available_polarizations=avail_pols,
            valid_overlap_ratio=None,
            spatial_overlap_ratio=spatial_overlap_val,
            t0_utc=sa.acquisition_start_utc,
            t1_utc=sb.acquisition_start_utc,
            frequency_band=sa.band,
            same_orbit_pass=same_orbit_pass,
            same_look_direction=same_look_dir,
            reasons=reasons,
            warnings=warnings,
            metadata_checks=checks,
        )

    has_conditional = any(v == "CONDITIONAL" for v in checks.values())
    if has_conditional:
        return ScenePairValidationResult(
            compatible=True,
            validation_decision="CONDITIONAL",
            science_status=ScienceQualityStatus.LIMITED,
            scene_ids=[sa.scene_id, sb.scene_id],
            available_polarizations=avail_pols,
            valid_overlap_ratio=None,
            spatial_overlap_ratio=spatial_overlap_val,
            t0_utc=sa.acquisition_start_utc,
            t1_utc=sb.acquisition_start_utc,
            frequency_band=sa.band,
            same_orbit_pass=same_orbit_pass,
            same_look_direction=same_look_dir,
            reasons=[],
            warnings=warnings,
            metadata_checks=checks,
        )

    return ScenePairValidationResult(
        compatible=True,
        validation_decision="PASS",
        science_status=ScienceQualityStatus.COMPARABLE,
        scene_ids=[sa.scene_id, sb.scene_id],
        available_polarizations=avail_pols,
        valid_overlap_ratio=spatial_overlap_val,
        spatial_overlap_ratio=spatial_overlap_val,
        t0_utc=sa.acquisition_start_utc,
        t1_utc=sb.acquisition_start_utc,
        frequency_band=sa.band,
        same_orbit_pass=same_orbit_pass,
        same_look_direction=same_look_dir,
        reasons=[],
        warnings=warnings,
        metadata_checks=checks,
    )


def screen_candidate_pairs(
    scenes: list[NormalizedSceneMetadata],
    aoi_bbox: list[float] | None = None,
) -> list[ScreenedCandidatePair]:
    """First-stage catalog pair screener.

    Evaluates all chronologically ordered pairs `(scene_a, scene_b)` within `scenes`,
    computes an expected scientific comparability score `[0, 100]`, and labels viable pairs
    as `CATALOG_SCREENED` or `CONDITIONAL` (never `COMPARABLE`).
    """
    sorted_scenes = sorted(
        scenes,
        key=lambda s: (s.acquisition_start_utc or "", s.scene_id),
    )
    screened: list[ScreenedCandidatePair] = []
    pair_idx = 0

    for i in range(len(sorted_scenes)):
        for j in range(i + 1, len(sorted_scenes)):
            sa = sorted_scenes[i]
            sb = sorted_scenes[j]
            pair_idx += 1

            val = validate_scene_pair(sa, sb, aoi=aoi_bbox)
            pair_overlap, aoi_overlap = compute_spatial_overlap_ratios(sa, sb, aoi_bbox)

            dt_a = _parse_iso_utc(sa.acquisition_start_utc)
            dt_b = _parse_iso_utc(sb.acquisition_start_utc)
            delta_days: float | None = None
            if dt_a and dt_b:
                delta_days = round(abs((dt_b - dt_a).total_seconds()) / 86400.0, 2)

            same_track = (
                sa.track_or_frame == sb.track_or_frame
                if (sa.track_or_frame and sb.track_or_frame)
                else None
            )
            same_maturity = (
                sa.product_maturity == sb.product_maturity
                if (sa.product_maturity and sb.product_maturity)
                else None
            )
            same_crid = sa.crid == sb.crid if (sa.crid and sb.crid) else None

            if not val.compatible:
                status = CatalogScreeningStatus.FAIL
                score = 0.0
            else:
                # Score calculation [0..100] based on scientific comparability criteria
                score = 40.0 * (val.spatial_overlap_ratio or 0.0)
                if same_track is True:
                    score += 20.0
                elif same_track is None:
                    score += 5.0

                if val.same_orbit_pass is True:
                    score += 15.0

                pol_names = {p.value for p in val.available_polarizations}
                if {"HH", "HV"}.issubset(pol_names):
                    score += 15.0
                elif len(pol_names) >= 1:
                    score += 10.0

                if same_maturity is True:
                    score += 5.0
                if same_crid is True:
                    score += 5.0

                score = round(min(100.0, max(0.0, score)), 2)
                if same_track is True and len(pol_names) >= 1 and (val.spatial_overlap_ratio or 0.0) >= 0.50:
                    status = CatalogScreeningStatus.CATALOG_SCREENED
                else:
                    status = CatalogScreeningStatus.CONDITIONAL

            approx_pair_bytes: int | None = None
            if sa.approx_file_size_bytes is not None and sb.approx_file_size_bytes is not None:
                approx_pair_bytes = sa.approx_file_size_bytes + sb.approx_file_size_bytes

            screened.append(
                ScreenedCandidatePair(
                    pair_id=f"{sa.aoi_id}_P{pair_idx:03d}",
                    candidate_id=sa.candidate_id,
                    aoi_id=sa.aoi_id,
                    aoi_name=sa.aoi_name,
                    scene_a_id=sa.scene_id,
                    scene_b_id=sb.scene_id,
                    t0_utc=sa.acquisition_start_utc,
                    t1_utc=sb.acquisition_start_utc,
                    delta_days=delta_days,
                    screening_status=status,
                    comparability_score=score,
                    shared_polarizations=[p.value for p in val.available_polarizations],
                    spatial_overlap_ratio=aoi_overlap,
                    pair_intersection_ratio=pair_overlap,
                    same_orbit_direction=val.same_orbit_pass,
                    same_track_or_frame=same_track,
                    same_product_maturity=same_maturity,
                    same_crid=same_crid,
                    reasons=val.reasons,
                    warnings=val.warnings,
                    approx_pair_size_bytes=approx_pair_bytes,
                )
            )

    screened.sort(
        key=lambda p: (
            p.screening_status != CatalogScreeningStatus.FAIL,
            p.screening_status == CatalogScreeningStatus.CATALOG_SCREENED,
            p.comparability_score,
            p.delta_days or 0.0,
        ),
        reverse=True,
    )
    return screened
