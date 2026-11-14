"""Candidate AOI definition, official catalog search orchestration, and manifest writer for Gate A."""

from __future__ import annotations

import csv
import json
import pathlib
from dataclasses import dataclass
from typing import Any

from sar.catalog.asf_client import search_asf_nisar_gcov, search_cmr_nisar_gcov
from sar.catalog.models import NormalizedSceneMetadata, ScreenedCandidatePair
from sar.validation.pair_validator import screen_candidate_pairs

MANIFEST_CSV_COLUMNS = [
    "candidate_id",
    "aoi_name",
    "event_context",
    "scene_id",
    "product_short_name",
    "product_type",
    "acquisition_start_utc",
    "acquisition_end_utc",
    "band",
    "orbit_direction",
    "track_or_frame",
    "polarizations",
    "product_maturity",
    "crid",
    "processing_version",
    "grid_spacing_m",
    "bbox",
    "catalog_source",
    "catalog_reference",
    "approx_file_size_bytes",
    "metadata_status",
    "local_status",
    "notes",
]


@dataclass(frozen=True)
class CandidateAOISpec:
    """Definition of a Gate A candidate AOI for NISAR L2 GCOV discovery."""

    candidate_id: str
    aoi_id: str
    aoi_name: str
    bbox: list[float]  # [min_lon, min_lat, max_lon, max_lat]
    event_context: str


DEFAULT_CANDIDATE_AOIS: list[CandidateAOISpec] = [
    CandidateAOISpec(
        candidate_id="Case_A",
        aoi_id="AOI-A1",
        aoi_name="Indonesia — Riau / Central Sumatra Peatland & Forest Corridor",
        bbox=[100.80, -0.30, 103.20, 2.10],
        event_context="Sumatra tropical peatland and plantation fire-prone landscape (narrative candidate; requires Gate A verification)",
    ),
    CandidateAOISpec(
        candidate_id="Case_A",
        aoi_id="AOI-A2",
        aoi_name="Indonesia — South Sumatra (Ogan Komering Ilir) Peatland Corridor",
        bbox=[104.50, -3.80, 106.20, -2.30],
        event_context="South Sumatra peatland disturbance and seasonal burn regime",
    ),
    CandidateAOISpec(
        candidate_id="Case_B",
        aoi_id="AOI-B1",
        aoi_name="California — Northern California Forest & Foothill Wildfire Corridor",
        bbox=[-122.50, 39.60, -121.10, 40.80],
        event_context="Northern California wildfire-affected forest/chaparral landscape (methodological reference region)",
    ),
    CandidateAOISpec(
        candidate_id="Case_B",
        aoi_id="AOI-B2",
        aoi_name="California — Southern California Transverse Ranges Wildfire Corridor",
        bbox=[-119.10, 34.00, -117.40, 34.90],
        event_context="Southern California chaparral and montane wildfire-prone corridor",
    ),
    CandidateAOISpec(
        candidate_id="Case_C",
        aoi_id="AOI-C1",
        aoi_name="Lower Mississippi Alluvial Valley & Atchafalaya Basin (Wetland/Flood/Ag Surface Change)",
        bbox=[-92.00, 29.50, -90.50, 31.50],
        event_context="High-signal L-band HH/HV surface backscatter change across dynamic wetland inundation and agricultural transitions",
    ),
]


def discover_candidate_scenes(
    aoi_spec: CandidateAOISpec,
    *,
    short_name: str = "NISAR_L2_GCOV_PROVISIONAL_V1",
    max_results: int = 100,
) -> list[NormalizedSceneMetadata]:
    """Query NASA CMR (and fallback to ASF Search) for a single `CandidateAOISpec`."""
    scenes_by_id: dict[str, NormalizedSceneMetadata] = {}

    # 1. Query NASA CMR UMM-G endpoint for exact collection short_name
    try:
        cmr_scenes = search_cmr_nisar_gcov(
            short_name=short_name,
            bbox=aoi_spec.bbox,
            candidate_id=aoi_spec.candidate_id,
            aoi_id=aoi_spec.aoi_id,
            aoi_name=aoi_spec.aoi_name,
            event_context=aoi_spec.event_context,
            page_size=max_results,
        )
        for s in cmr_scenes:
            scenes_by_id[s.scene_id] = s
    except Exception:
        pass

    # 2. Enrich or fallback via asf_search if needed
    if not scenes_by_id:
        try:
            asf_scenes = search_asf_nisar_gcov(
                bbox=aoi_spec.bbox,
                candidate_id=aoi_spec.candidate_id,
                aoi_id=aoi_spec.aoi_id,
                aoi_name=aoi_spec.aoi_name,
                event_context=aoi_spec.event_context,
                max_results=max_results,
            )
            for s in asf_scenes:
                if (
                    s.product_short_name is None
                    or short_name.upper() in s.product_short_name.upper()
                ):
                    scenes_by_id[s.scene_id] = s
        except Exception:
            pass

    return sorted(
        scenes_by_id.values(),
        key=lambda x: (x.acquisition_start_utc or "", x.scene_id),
    )


def write_scene_manifest_csv(
    scenes: list[NormalizedSceneMetadata],
    csv_path: pathlib.Path,
) -> None:
    """Write real catalog scene metadata records to `data/scenes/scene_manifest.csv`."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_CSV_COLUMNS)
        writer.writeheader()
        for scene in scenes:
            writer.writerow(scene.to_manifest_row())


def write_scene_manifest_json(
    scenes: list[NormalizedSceneMetadata],
    screened_pairs: list[ScreenedCandidatePair],
    json_path: pathlib.Path,
    *,
    extra_summary: dict[str, Any] | None = None,
) -> None:
    """Write structured JSON manifest alongside `scene_manifest.csv`."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "manifest_version": "gate-a-v1.0",
        "project_mode": "PRE_COMPETITION_RND",
        "official_collection": "NISAR_L2_GCOV_PROVISIONAL_V1",
        "total_scenes": len(scenes),
        "total_screened_pairs": len(screened_pairs),
        "summary": extra_summary or {},
        "scenes": [s.model_dump(mode="json") for s in scenes],
        "screened_pairs": [p.model_dump(mode="json") for p in screened_pairs],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
