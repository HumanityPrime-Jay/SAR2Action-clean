"""Normalized scene metadata and candidate pair screening models for NISAR L-band Level-2 GCOV.

Follows the Metadata-First Discovery rule:
- Does not assume every metadata field exists in catalog responses.
- Missing fields are represented explicitly as `None` (`null` / unavailable).
- Catalog-stage pair screening produces `CATALOG_SCREENED` / `CONDITIONAL` / `FAIL`
  and never claims final `COMPARABLE` status before actual HDF5 grids and masks are inspected.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CatalogScreeningStatus(StrEnum):
    """Status emitted by metadata-only pair screening (`screen_candidate_pairs`)."""

    CATALOG_SCREENED = "CATALOG_SCREENED"
    CONDITIONAL = "CONDITIONAL"
    FAIL = "FAIL"


class ValidationDecision(StrEnum):
    """High-level validation outcome for `validate_scene_pair` v1."""

    PASS = "PASS"
    CONDITIONAL = "CONDITIONAL"
    FAIL = "FAIL"


class NormalizedSceneMetadata(BaseModel):
    """Normalized internal metadata record for a single NISAR GCOV scene/granule."""

    model_config = ConfigDict(extra="allow")

    candidate_id: str = Field(..., description="Candidate case identifier (e.g., 'Case_A', 'Case_B').")
    aoi_id: str = Field(..., description="AOI identifier (e.g., 'AOI-A1').")
    aoi_name: str = Field(..., description="Human-readable AOI name.")
    event_context: str = Field(
        default="",
        description="Contextual motivation (never treated as causal proof).",
    )
    scene_id: str = Field(..., description="Official granule / scene identifier.")
    product_short_name: str | None = Field(
        default=None,
        description="Collection short name (e.g., 'NISAR_L2_GCOV_PROVISIONAL_V1' or 'NISAR_L2_GCOV_BETA_V1').",
    )
    product_type: str | None = Field(
        default=None,
        description="Product level/type (e.g., 'GCOV').",
    )
    acquisition_start_utc: str | None = Field(
        default=None,
        description="ISO-8601 acquisition start UTC.",
    )
    acquisition_end_utc: str | None = Field(
        default=None,
        description="ISO-8601 acquisition end UTC.",
    )
    band: str | None = Field(
        default=None,
        description="Radar frequency band (e.g., 'L').",
    )
    polarizations: list[str] | None = Field(
        default=None,
        description="Available diagonal polarizations (e.g., ['HH', 'HV']) or None if unknown in catalog.",
    )
    orbit_direction: str | None = Field(
        default=None,
        description="Orbit pass direction ('ASCENDING', 'DESCENDING', or None).",
    )
    look_direction: str | None = Field(
        default=None,
        description="Antenna look direction ('Right', 'Left', or None).",
    )
    track_or_frame: str | None = Field(
        default=None,
        description="Relative orbit / track / frame identifier (e.g., 'T012_F2000') if available.",
    )
    relative_orbit: int | None = Field(
        default=None,
        description="Relative orbit / path / track number if available.",
    )
    frame_number: int | None = Field(
        default=None,
        description="Frame number if available.",
    )
    product_maturity: str | None = Field(
        default=None,
        description="Product maturity ('PROVISIONAL', 'BETA', 'VALIDATED', or None).",
    )
    crid: str | None = Field(
        default=None,
        description="Composite Release Identifier (CRID) parsed from granule name or attributes.",
    )
    processing_version: str | None = Field(
        default=None,
        description="Collection or PGE version string if available.",
    )
    grid_spacing_m: float | None = Field(
        default=None,
        description="Nominal grid spacing in meters if reported in metadata.",
    )
    is_full_frame: bool | None = Field(
        default=None,
        description="True if full-frame acquisition (coverage code 'F' in _<CRID>_<A>_F_<L>_ or isFullFrame=True), False if partial frame (coverage code 'P' in _<CRID>_<A>_P_<L>_ or isFullFrame=False).",
    )
    bbox: list[float] | None = Field(
        default=None,
        min_length=4,
        max_length=4,
        description="[min_lon, min_lat, max_lon, max_lat] in WGS84.",
    )
    bounding_geometry: dict[str, Any] | None = Field(
        default=None,
        description="GeoJSON Polygon/MultiPolygon footprint in EPSG:4326.",
    )
    illuminated_bbox: list[float] | None = Field(
        default=None,
        min_length=4,
        max_length=4,
        description="Verified actual illuminated SAR swath bbox [min_lon, min_lat, max_lon, max_lat] from _LATLON.kml or HDF5 boundingPolygon.",
    )
    illuminated_geometry: dict[str, Any] | None = Field(
        default=None,
        description="Verified actual illuminated SAR swath GeoJSON Polygon in EPSG:4326 from _LATLON.kml or HDF5 boundingPolygon.",
    )
    catalog_source: str = Field(
        default="NASA_CMR_ASF",
        description="Catalog source ('ASF_SEARCH' or 'NASA_CMR').",
    )
    catalog_reference: str | None = Field(
        default=None,
        description="CMR concept-id or catalog metadata URL.",
    )
    download_url: str | None = Field(
        default=None,
        description="HTTPS data download URL for the HDF5 granule.",
    )
    s3_url: str | None = Field(
        default=None,
        description="AWS S3 direct URI inside NASA Earthdata Cloud if available.",
    )
    approx_file_size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Approximate HDF5 granule size in bytes.",
    )
    metadata_status: str = Field(
        default="CATALOG_ONLY",
        description="'CATALOG_ONLY' or 'HDF5_INSPECTED'.",
    )
    local_status: str = Field(
        default="NOT_DOWNLOADED",
        description="'NOT_DOWNLOADED', 'HEADER_INSPECTED', or 'DOWNLOADED'.",
    )
    notes: str | None = Field(
        default=None,
        description="Additional scientific or provenance notes.",
    )

    def to_manifest_row(self) -> dict[str, Any]:
        """Serialize to a flat dictionary matching `data/scenes/scene_manifest.csv` columns."""
        return {
            "candidate_id": self.candidate_id,
            "aoi_name": self.aoi_name,
            "event_context": self.event_context,
            "scene_id": self.scene_id,
            "product_short_name": self.product_short_name or "",
            "product_type": self.product_type or "",
            "acquisition_start_utc": self.acquisition_start_utc or "",
            "acquisition_end_utc": self.acquisition_end_utc or "",
            "band": self.band or "",
            "orbit_direction": self.orbit_direction or "",
            "track_or_frame": self.track_or_frame or "",
            "polarizations": ";".join(self.polarizations) if self.polarizations else "",
            "product_maturity": self.product_maturity or "",
            "crid": self.crid or "",
            "processing_version": self.processing_version or "",
            "grid_spacing_m": "" if self.grid_spacing_m is None else str(self.grid_spacing_m),
            "bbox": "" if self.bbox is None else ",".join(f"{v:.5f}" for v in self.bbox),
            "catalog_source": self.catalog_source,
            "catalog_reference": self.download_url or self.catalog_reference or "",
            "approx_file_size_bytes": (
                "" if self.approx_file_size_bytes is None else str(self.approx_file_size_bytes)
            ),
            "metadata_status": self.metadata_status,
            "local_status": self.local_status,
            "notes": self.notes or "",
        }


class ScreenedCandidatePair(BaseModel):
    """Result of first-stage metadata pair screening (`screen_candidate_pairs`)."""

    model_config = ConfigDict(extra="forbid")

    pair_id: str
    candidate_id: str
    aoi_id: str
    aoi_name: str
    scene_a_id: str
    scene_b_id: str
    t0_utc: str | None
    t1_utc: str | None
    delta_days: float | None
    screening_status: CatalogScreeningStatus = Field(
        ...,
        description="CATALOG_SCREENED, CONDITIONAL, or FAIL. Never claims final COMPARABLE status.",
    )
    comparability_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Expected scientific comparability score [0-100] for ranking candidate pairs.",
    )
    shared_polarizations: list[str] = Field(default_factory=list)
    spatial_overlap_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    pair_intersection_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    same_orbit_direction: bool | None = None
    same_track_or_frame: bool | None = None
    same_product_maturity: bool | None = None
    same_crid: bool | None = None
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    approx_pair_size_bytes: int | None = None


ORBIT_FIDELITY_CODE_MAP: dict[str, str] = {
    "P": "Precise",
    "M": "Medium",
    "N": "Near Real-Time",
    "F": "Forecast",
}

COVERAGE_CODE_MAP: dict[str, str] = {
    "F": "Full",
    "P": "Partial",
}

SDS_LOCATION_CODE_MAP: dict[str, str] = {
    "J": "JPL",
    "N": "NRSC",
}


class NisarGcovFilenameMetadata(BaseModel):
    """Parsed fields from an official NISAR L2 GCOV granule identifier or filename.

    Official NISAR L2 GCOV naming convention:
    `NISAR_L2_PR_GCOV_<CCC>_<RRR>_<D>_<FFF>_<MMMM>_<PPPP>_<O>_<Start>_<End>_<CRID>_<A>_<C>_<L>_<NNN>`
    where the fields immediately following `<CRID>` are:
    - `<A>` (`orbit_pointing_fidelity_code`):
      - `P` = Precise
      - `M` = Medium
      - `N` = Near Real-Time
      - `F` = Forecast
    - `<C>` (`coverage_code`):
      - `F` = Full
      - `P` = Partial
    - `<L>` (`sds_location_code`):
      - `J` = JPL
    """

    model_config = ConfigDict(extra="forbid")

    raw_identifier: str
    scene_id: str
    mission: str
    product_level: str
    processing_type: str
    product_type: str
    cycle_number: int
    relative_orbit_number: int
    pass_direction_code: str
    pass_direction: str
    frame_number: int
    mode_code: str
    polarization_code: str
    observation_mode_code: str
    start_datetime_token: str
    end_datetime_token: str
    crid: str
    orbit_pointing_fidelity_code: str
    orbit_pointing_fidelity: str
    coverage_code: str
    coverage_indicator: str
    is_full_frame: bool
    sds_location_code: str
    sds_location: str
    product_counter: int


def parse_nisar_gcov_filename(identifier: str) -> NisarGcovFilenameMetadata:
    """Parse an official NISAR L2 GCOV granule ID or filename into structured metadata."""
    clean = identifier.strip()
    if "/" in clean or "\\" in clean:
        clean = clean.replace("\\", "/").split("/")[-1]
    for suffix in (
        "_QA_STATS.h5",
        "_QA_SUMMARY.csv",
        "_LATLON.kml",
        "_BROWSE.png",
        ".h5.iso.xml",
        ".h5.dmrpp",
        ".h5",
        ".iso.xml",
        ".json",
    ):
        if clean.endswith(suffix):
            clean = clean[: -len(suffix)]
            break

    parts = clean.split("_")
    if len(parts) != 18 or parts[0] != "NISAR" or parts[3] != "GCOV":
        raise ValueError(
            f"Identifier '{identifier}' does not match the 18-token NISAR L2 GCOV naming convention."
        )

    dir_code = parts[6].upper()
    if dir_code not in ("A", "D"):
        raise ValueError(f"Invalid pass direction code '{dir_code}' in '{identifier}'.")

    fidelity_code = parts[14].upper()
    if fidelity_code not in ORBIT_FIDELITY_CODE_MAP:
        raise ValueError(
            f"Invalid orbit/radar-pointing fidelity code '{fidelity_code}' in '{identifier}' "
            f"(expected one of {list(ORBIT_FIDELITY_CODE_MAP.keys())})."
        )

    cov_code = parts[15].upper()
    if cov_code not in COVERAGE_CODE_MAP:
        raise ValueError(
            f"Invalid coverage code '{cov_code}' in '{identifier}' "
            f"(expected one of {list(COVERAGE_CODE_MAP.keys())})."
        )

    loc_code = parts[16].upper()
    sds_loc = SDS_LOCATION_CODE_MAP.get(loc_code, loc_code)

    return NisarGcovFilenameMetadata(
        raw_identifier=identifier,
        scene_id=clean,
        mission=parts[0],
        product_level=parts[1],
        processing_type=parts[2],
        product_type=parts[3],
        cycle_number=int(parts[4]),
        relative_orbit_number=int(parts[5]),
        pass_direction_code=dir_code,
        pass_direction="ASCENDING" if dir_code == "A" else "DESCENDING",
        frame_number=int(parts[7]),
        mode_code=parts[8],
        polarization_code=parts[9],
        observation_mode_code=parts[10],
        start_datetime_token=parts[11],
        end_datetime_token=parts[12],
        crid=parts[13],
        orbit_pointing_fidelity_code=fidelity_code,
        orbit_pointing_fidelity=ORBIT_FIDELITY_CODE_MAP[fidelity_code],
        coverage_code=cov_code,
        coverage_indicator=COVERAGE_CODE_MAP[cov_code],
        is_full_frame=(cov_code == "F"),
        sds_location_code=loc_code,
        sds_location=sds_loc,
        product_counter=int(parts[17]),
    )

