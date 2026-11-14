"""Execute Phase 1 Gate A Metadata-First Discovery against NASA Earthdata CMR / ASF.

Does NOT download any HDF5 science granules.
Populates:
- `data/scenes/scene_manifest.csv`
- `data/scenes/scene_manifest.json`
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter, defaultdict

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sar.catalog.asf_client import CMR_COLLECTIONS_JSON_URL, search_cmr_nisar_gcov
from sar.catalog.candidate_search import (
    DEFAULT_CANDIDATE_AOIS,
    CandidateAOISpec,
    discover_candidate_scenes,
    write_scene_manifest_csv,
    write_scene_manifest_json,
)
from sar.catalog.models import CatalogScreeningStatus, NormalizedSceneMetadata, ScreenedCandidatePair
from sar.validation.pair_validator import screen_candidate_pairs


def inspect_cmr_nisar_collections() -> list[dict]:
    """Query NASA CMR for all NISAR GCOV collections and their granule counts."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            CMR_COLLECTIONS_JSON_URL,
            params={"keyword": "NISAR GCOV", "page_size": 50},
            headers={"Client-Id": "SAR2Action-GateA"},
        )
        resp.raise_for_status()
        entries = resp.json().get("feed", {}).get("entry", [])

    collections = []
    for entry in entries:
        short_name = entry.get("short_name")
        if not short_name or "GCOV" not in short_name.upper():
            continue
        collections.append(
            {
                "short_name": short_name,
                "version_id": entry.get("version_id"),
                "concept_id": entry.get("id"),
                "title": entry.get("title"),
                "time_start": entry.get("time_start"),
                "time_end": entry.get("time_end"),
            }
        )
    return collections


def main() -> None:
    print("=== Step 1: Querying NASA CMR for official NISAR GCOV collections ===")
    collections = inspect_cmr_nisar_collections()
    for c in collections:
        print(f"  Collection: {c['short_name']} (v{c['version_id']}) | {c['title']} | start={c['time_start']}")

    target_short_name = "NISAR_L2_GCOV_PROVISIONAL_V1"
    all_scenes: list[NormalizedSceneMetadata] = []
    all_pairs: list[ScreenedCandidatePair] = []
    per_aoi_summary: dict[str, dict] = {}

    print(f"\n=== Step 2: Querying {target_short_name} across Candidate AOIs ===")
    for aoi_spec in DEFAULT_CANDIDATE_AOIS:
        print(f"\n--- {aoi_spec.candidate_id} / {aoi_spec.aoi_id}: {aoi_spec.aoi_name} ---")
        print(f"    BBox: {aoi_spec.bbox}")
        scenes = discover_candidate_scenes(
            aoi_spec,
            short_name=target_short_name,
            max_results=200,
        )
        print(f"    Scenes found in {target_short_name}: {len(scenes)}")

        # Group by track_or_frame & polarization to select up to 8 representative repeat-pass scenes per AOI
        # if more than 30 granules are returned, keeping the best repeat-pass stack intact
        by_track: dict[str, list[NormalizedSceneMetadata]] = defaultdict(list)
        for s in scenes:
            key = f"{s.track_or_frame}_{s.orbit_direction}_{';'.join(s.polarizations or [])}"
            by_track[key].append(s)

        print(f"    Distinct (track_frame, orbit, pol) stacks: {len(by_track)}")
        for k, stack in sorted(by_track.items(), key=lambda kv: len(kv[1]), reverse=True)[:5]:
            dates = [s.acquisition_start_utc[:10] if s.acquisition_start_utc else "?" for s in stack]
            sizes_gb = [
                round(s.approx_file_size_bytes / (1024**3), 2)
                for s in stack
                if s.approx_file_size_bytes
            ]
            avg_gb = round(sum(sizes_gb) / len(sizes_gb), 2) if sizes_gb else None
            print(f"      Stack {k}: {len(stack)} scenes | dates={dates} | avg_size_gb={avg_gb}")

        pairs = screen_candidate_pairs(scenes, aoi_bbox=aoi_spec.bbox)
        valid_pairs = [
            p for p in pairs if p.screening_status != CatalogScreeningStatus.FAIL
        ]
        screened_top = [
            p for p in pairs if p.screening_status == CatalogScreeningStatus.CATALOG_SCREENED
        ]
        print(
            f"    Total pairs evaluated: {len(pairs)} | "
            f"CATALOG_SCREENED: {len(screened_top)} | "
            f"Viable (CATALOG_SCREENED + CONDITIONAL): {len(valid_pairs)}"
        )
        for p in valid_pairs[:3]:
            size_gb = (
                round(p.approx_pair_size_bytes / (1024**3), 2)
                if p.approx_pair_size_bytes
                else None
            )
            print(
                f"      Best Pair {p.pair_id}: {p.scene_a_id} -> {p.scene_b_id}\n"
                f"        status={p.screening_status} | score={p.comparability_score} | "
                f"dt={p.delta_days}d | pols={p.shared_polarizations} | "
                f"aoi_overlap={p.spatial_overlap_ratio:.3f} | pair_overlap={p.pair_intersection_ratio:.3f} | "
                f"pair_size_gb={size_gb}"
            )

        all_scenes.extend(scenes)
        all_pairs.extend(valid_pairs[:10])
        per_aoi_summary[aoi_spec.aoi_id] = {
            "candidate_id": aoi_spec.candidate_id,
            "aoi_name": aoi_spec.aoi_name,
            "bbox": aoi_spec.bbox,
            "scene_count": len(scenes),
            "stack_count": len(by_track),
            "catalog_screened_pair_count": len(screened_top),
            "viable_pair_count": len(valid_pairs),
            "top_pair": valid_pairs[0].model_dump(mode="json") if valid_pairs else None,
        }

    csv_path = ROOT / "data" / "scenes" / "scene_manifest.csv"
    json_path = ROOT / "data" / "scenes" / "scene_manifest.json"
    write_scene_manifest_csv(all_scenes, csv_path)
    write_scene_manifest_json(
        all_scenes,
        all_pairs,
        json_path,
        extra_summary={"collections": collections, "per_aoi": per_aoi_summary},
    )
    print(f"\n=== Wrote {len(all_scenes)} scenes to {csv_path} and {json_path} ===")


if __name__ == "__main__":
    main()
