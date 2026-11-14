"""Deterministic NISAR L2 GCOV Change Engine package (`sar/change`)."""

from sar.change.delta import (
    COMBINED_RADAR_CHANGE_DISCLAIMER,
    CombinedRadarChangeLayer,
    compute_combined_radar_change,
    compute_magnitude_db,
    compute_signed_delta_db,
)
from sar.change.masks import (
    MASK_RULE_SPECIFICATION,
    MultiTemporalMaskBundle,
    build_multitemporal_valid_masks,
    compute_valid_pixel_mask,
    is_valid_gcov_product_mask,
    is_valid_radiometric_power,
)
from sar.change.radiometry import linear_power_to_db
from sar.change.reader import (
    AOIChangeResult,
    GCOVSceneWindow,
    read_gcov_grid_and_metadata,
    read_gcov_window,
    run_aoi_change_analysis,
    run_in_memory_change_analysis,
)
from sar.change.statistics import (
    build_aoi_evidence_record,
    compute_distribution_stats_db,
    compute_polarization_aoi_statistics,
    determine_quality_status,
    summarize_number_of_looks_metadata,
)
from sar.change.windows import (
    GridDefinition,
    GridMismatchError,
    WindowSlice,
    aoi_to_window,
    verify_grids_compatible,
)

__all__ = [
    "AOIChangeResult",
    "COMBINED_RADAR_CHANGE_DISCLAIMER",
    "CombinedRadarChangeLayer",
    "GCOVSceneWindow",
    "GridDefinition",
    "GridMismatchError",
    "MASK_RULE_SPECIFICATION",
    "MultiTemporalMaskBundle",
    "WindowSlice",
    "aoi_to_window",
    "build_aoi_evidence_record",
    "build_multitemporal_valid_masks",
    "compute_combined_radar_change",
    "compute_distribution_stats_db",
    "compute_magnitude_db",
    "compute_polarization_aoi_statistics",
    "compute_signed_delta_db",
    "compute_valid_pixel_mask",
    "determine_quality_status",
    "is_valid_gcov_product_mask",
    "is_valid_radiometric_power",
    "linear_power_to_db",
    "read_gcov_grid_and_metadata",
    "read_gcov_window",
    "run_aoi_change_analysis",
    "run_in_memory_change_analysis",
    "summarize_number_of_looks_metadata",
    "verify_grids_compatible",
]
