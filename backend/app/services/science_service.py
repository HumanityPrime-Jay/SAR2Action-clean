"""Deterministic Science, Case, Evidence, and Layer service for SAR2Action Phase 3A.

All quantitative values returned by this service originate strictly from:
1. Official NISAR L-band Level-2 GCOV HDF5 granules and companion metadata
2. The deterministic Change Engine (`sar/change/`)
3. The persisted Evidence Store (`data/cache/evidence_store.json`)
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
from typing import Any, Literal

from fastapi import HTTPException

from backend.app.schemas.api import (
    AnalyzeChangeRequest,
    AnalyzeChangeResponse,
    CaseObservationsResponse,
    CaseSummary,
    DeterministicClaim,
    EpistemicSummaryPanel,
    HealthResponse,
    LayerMetadataResponse,
    ObservationRecord,
    PolarizationFingerprintDetail,
    PresetAOI,
    RadarFingerprintRequest,
    RadarFingerprintResponse,
    ValidatePairRequest,
    ValidatePairResponse,
)
from backend.app.schemas.evidence import (
    COMBINED_RADAR_CHANGE_DISCLAIMER,
    DistributionStatsDb,
    EvidenceRecord,
    PolarizationChangeBreakdown,
    PolarizationChannel,
    ProcessingProvenanceMetadata,
    RadarFingerprint,
    ScenePairValidationResult,
    ScienceQualityStatus,
)
from backend.app.services.layer_renderer import export_analysis_png_layers
from sar.catalog.models import NormalizedSceneMetadata
from sar.change import GCOVSceneWindow, aoi_to_window, read_gcov_window, run_in_memory_change_analysis
from sar.validation.pair_validator import validate_scene_pair

ROOT = pathlib.Path(__file__).resolve().parents[3]
SCENES_DIR = ROOT / "data" / "raw" / "scenes"
MANIFEST_PATH = ROOT / "data" / "scenes" / "scene_manifest.json"
EVIDENCE_STORE_PATH = ROOT / "data" / "cache" / "evidence_store.json"
LAYER_STORE_PATH = ROOT / "data" / "cache" / "layer_store.json"
ANALYSIS_STORE_PATH = ROOT / "data" / "cache" / "analysis_store.json"
FINGERPRINT_STORE_PATH = ROOT / "data" / "cache" / "fingerprint_store.json"
PNG_CACHE_DIR = ROOT / "data" / "cache" / "layer_pngs"


def raise_science_error(
    status_code: int,
    *,
    error_code: str,
    message: str,
    science_status: ScienceQualityStatus = ScienceQualityStatus.INSUFFICIENT_EVIDENCE,
    details: dict[str, Any] | None = None,
) -> None:
    """Raise a structured FastAPI HTTPException preserving `science_status` and `error_code`."""
    raise HTTPException(
        status_code=status_code,
        detail={
            "error_code": error_code,
            "message": message,
            "science_status": science_status.value,
            "details": details or {},
        },
    )


class ScienceService:
    """Orchestrates cases, observations, pair validation, change analysis, fingerprints, and evidence."""

    def __init__(self) -> None:
        self._manifest_scenes: list[dict[str, Any]] = []
        self._evidence_map: dict[str, EvidenceRecord] = {}
        self._layer_map: dict[str, LayerMetadataResponse] = {}
        self._analysis_map: dict[str, AnalyzeChangeResponse] = {}
        self._fingerprint_map: dict[str, RadarFingerprintResponse] = {}
        env_mode = os.environ.get("SAR2ACTION_DEMO_MODE", "LIVE").strip().upper()
        self.demo_mode: Literal["LIVE", "CACHED_REAL_DATA"] = (
            "CACHED_REAL_DATA" if env_mode == "CACHED_REAL_DATA" else "LIVE"
        )
        self._load_manifest()
        self._load_stores()

    def set_demo_mode(self, mode: Literal["LIVE", "CACHED_REAL_DATA"]) -> Literal["LIVE", "CACHED_REAL_DATA"]:
        if mode not in ("LIVE", "CACHED_REAL_DATA"):
            raise ValueError(f"Unsupported demo_mode: {mode}")
        self.demo_mode = mode
        return self.demo_mode

    def _load_manifest(self) -> None:
        if MANIFEST_PATH.exists():
            data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            self._manifest_scenes = data.get("scenes", [])

    def _load_stores(self) -> None:
        if EVIDENCE_STORE_PATH.exists():
            try:
                raw = json.loads(EVIDENCE_STORE_PATH.read_text(encoding="utf-8"))
                for rec_dict in raw.get("records", []):
                    rec = EvidenceRecord.model_validate(rec_dict)
                    self._evidence_map[rec.evidence_id] = rec
            except Exception:
                pass
        if LAYER_STORE_PATH.exists():
            try:
                raw_l = json.loads(LAYER_STORE_PATH.read_text(encoding="utf-8"))
                for l_dict in raw_l.get("layers", []):
                    l_obj = LayerMetadataResponse.model_validate(l_dict)
                    self._layer_map[l_obj.layer_id] = l_obj
            except Exception:
                pass
        if ANALYSIS_STORE_PATH.exists():
            try:
                raw_a = json.loads(ANALYSIS_STORE_PATH.read_text(encoding="utf-8"))
                for k, v in raw_a.get("analyses", {}).items():
                    self._analysis_map[k] = AnalyzeChangeResponse.model_validate(v)
            except Exception:
                pass
        if FINGERPRINT_STORE_PATH.exists():
            try:
                raw_f = json.loads(FINGERPRINT_STORE_PATH.read_text(encoding="utf-8"))
                for k, v in raw_f.get("fingerprints", {}).items():
                    self._fingerprint_map[k] = RadarFingerprintResponse.model_validate(v)
            except Exception:
                pass

    def _save_evidence(self, record: EvidenceRecord) -> None:
        self._evidence_map[record.evidence_id] = record
        EVIDENCE_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "evidence-schema-v1.0",
            "records": [r.model_dump(mode="json") for r in self._evidence_map.values()],
        }
        EVIDENCE_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _save_layers(self, layers: dict[str, LayerMetadataResponse]) -> None:
        for l_obj in layers.values():
            self._layer_map[l_obj.layer_id] = l_obj
        LAYER_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "layers": [l.model_dump(mode="json") for l in self._layer_map.values()],
        }
        LAYER_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _save_analysis_cache(self, evidence_id: str, resp: AnalyzeChangeResponse) -> None:
        self._analysis_map[evidence_id] = resp
        ANALYSIS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "analyses": {k: v.model_dump(mode="json") for k, v in self._analysis_map.items()},
        }
        ANALYSIS_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _save_fingerprint_cache(self, evidence_id: str, resp: RadarFingerprintResponse) -> None:
        self._fingerprint_map[evidence_id] = resp
        FINGERPRINT_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "fingerprints": {k: v.model_dump(mode="json") for k, v in self._fingerprint_map.items()},
        }
        FINGERPRINT_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get_scene_h5_path(self, scene_id: str) -> pathlib.Path | None:
        p = SCENES_DIR / f"{scene_id}.h5"
        if p.exists() and p.stat().st_size > 100_000_000:
            return p
        return None

    def get_cases(self) -> list[CaseSummary]:
        """Return available flagship and engineering validation cases."""
        f2_t0 = "NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001"
        f2_t1 = "NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001"
        f2_ready = (self.get_scene_h5_path(f2_t0) is not None) and (
            self.get_scene_h5_path(f2_t1) is not None
        )

        eng_t0 = "NISAR_L2_PR_GCOV_026_047_D_087_4005_DHDH_A_20260723T112605_20260723T112610_P05023_N_P_J_001"
        eng_t1 = "NISAR_L2_PR_GCOV_031_047_D_087_4005_DHDH_A_20260921T112603_20260921T112609_P05023_N_P_J_001"
        eng_ready = (self.get_scene_h5_path(eng_t0) is not None) and (
            self.get_scene_h5_path(eng_t1) is not None
        )

        return [
            CaseSummary(
                case_id="case-flagship-oki-f2",
                title="Primary Flagship — South Sumatra / Ogan Komering Ilir Peatland Corridor (T010_F176)",
                case_role="PRIMARY_FLAGSHIP",
                region_name="Ogan Komering Ilir (OKI), South Sumatra, Indonesia",
                track_number=10,
                frame_number=176,
                orbit_pass_direction="ASCENDING",
                look_direction="LEFT",
                polarizations=[PolarizationChannel.HH, PolarizationChannel.HV],
                product_maturity="PROVISIONAL",
                crid="P05023",
                is_full_frame=True,
                default_t0_scene_id=f2_t0,
                default_t1_scene_id=f2_t1,
                t0_acquisition_utc="2026-09-06T22:40:25Z",
                t1_acquisition_utc="2026-09-18T22:40:25Z",
                t0_orbit_pointing_fidelity="Near Real-Time",
                t1_orbit_pointing_fidelity="Forecast",
                rfi_comparison_status="UNRELIABLE_METADATA",
                default_aoi_bbox_wgs84=[105.28, -3.28, 105.48, -3.08],
                illuminated_bbox_wgs84=[104.21, -4.41, 106.90, -1.79],
                crs_epsg=32748,
                pixel_spacing_m=[10.0, 10.0],
                local_hdf5_ready=f2_ready,
                scientific_scope_note=(
                    "Locked Primary Flagship Pair (Candidate F2, 12-day repeat pass 2026-09-06 -> 2026-09-18, "
                    "05:40 WIB dawn acquisition, 100.0% illumination of OKI core peatland corridor, "
                    "PROVISIONAL CRID P05023, T0 fidelity=Near Real-Time, T1 fidelity=Forecast, "
                    "rfi_comparison_status=UNRELIABLE_METADATA, CAUSE NOT DETERMINED)."
                ),
                preset_aois=[
                    PresetAOI(
                        aoi_id="AOI-OKI-01",
                        name="AOI-OKI-01 — Tulung Selapan / Cengal Peatland Transition",
                        description="20 km × 20 km geographic sub-district window across the Tulung Selapan – Cengal drained peat dome corridor in Ogan Komering Ilir.",
                        bbox_wgs84=[105.28, -3.28, 105.48, -3.08],
                        default_evidence_id="E-FLAGSHIP-OKI-001",
                        selection_method="PREDEFINED_GEOGRAPHIC_AOI",
                        selection_time="PRE_ANALYSIS",
                        selection_basis="Predefined 20 km x 20 km sub-district corridor spanning Tulung Selapan and Cengal in Ogan Komering Ilir (SRC-BPBD-01).",
                    ),
                    PresetAOI(
                        aoi_id="AOI-OKI-02",
                        name="AOI-OKI-02 — Pangkalan Lampam / Pedamaran Peatland Belt",
                        description="18 km × 18 km geographic sub-district window over Pangkalan Lampam and Pedamaran Timur peatlands.",
                        bbox_wgs84=[104.98, -3.32, 105.16, -3.14],
                        default_evidence_id="E-FLAGSHIP-OKI-002",
                        selection_method="PREDEFINED_GEOGRAPHIC_AOI",
                        selection_time="PRE_ANALYSIS",
                        selection_basis="Predefined 18 km x 18 km sub-district corridor spanning Pangkalan Lampam and Pedamaran Timur in Ogan Komering Ilir (SRC-BPBD-01).",
                    ),
                    PresetAOI(
                        aoi_id="AOI-OKI-03",
                        name="AOI-OKI-03 — Eastern Cengal Coastal Peat Corridor",
                        description="18 km × 18 km geographic sub-district window in eastern Cengal sub-district.",
                        bbox_wgs84=[105.55, -3.42, 105.73, -3.24],
                        default_evidence_id="E-FLAGSHIP-OKI-003",
                        selection_method="PREDEFINED_GEOGRAPHIC_AOI",
                        selection_time="PRE_ANALYSIS",
                        selection_basis="Predefined 18 km x 18 km sub-district corridor in eastern Cengal, Ogan Komering Ilir (SRC-BPBD-01).",
                    ),
                    PresetAOI(
                        aoi_id="AOI-OKI-04",
                        name="AOI-OKI-04 — Padang Sugihan Peatland Reserve & Buffer (Predefined Event-Context AOI)",
                        description="17.8 km × 17.7 km predefined external event-context window over southern Suaka Margasatwa Padang Sugihan & Sebokor peat buffer (defined prior to radar change inspection; SRC-ANTARA-01, SRC-BMKG-01).",
                        bbox_wgs84=[105.08, -2.92, 105.24, -2.76],
                        default_evidence_id="E-FLAGSHIP-OKI-004",
                        selection_method="PREDEFINED_EXTERNAL_CONTEXT",
                        selection_time="2026-10-24T01:55:00+08:00 (PRE_ANALYSIS)",
                        selection_basis="Predefined from external ANTARA/Polda Sumsel/BPBD and BMKG reports documenting September 2026 peatland fire suppression in Padang Sugihan (Suaka Margasatwa Padang Sugihan), defined strictly before inspecting radar change statistics.",
                    ),
                ],
            ),
            CaseSummary(
                case_id="case-engineering-riau-t047",
                title="Engineering Validation — Riau Archipelago / Bintan & Singapore Strait (T047_F087)",
                case_role="ENGINEERING_VALIDATION",
                region_name="Riau Archipelago (Bintan / Batam), Indonesia",
                track_number=47,
                frame_number=87,
                orbit_pass_direction="DESCENDING",
                look_direction="LEFT",
                polarizations=[PolarizationChannel.HH, PolarizationChannel.HV],
                product_maturity="PROVISIONAL",
                crid="P05023",
                is_full_frame=False,
                default_t0_scene_id=eng_t0,
                default_t1_scene_id=eng_t1,
                t0_acquisition_utc="2026-07-23T11:26:05Z",
                t1_acquisition_utc="2026-09-21T11:26:03Z",
                t0_orbit_pointing_fidelity="Near Real-Time",
                t1_orbit_pointing_fidelity="Near Real-Time",
                rfi_comparison_status="UNRELIABLE_METADATA",
                default_aoi_bbox_wgs84=[104.20, 1.90, 104.35, 2.05],
                illuminated_bbox_wgs84=[103.12, 1.59, 105.41, 2.50],
                crs_epsg=32648,
                pixel_spacing_m=[10.0, 10.0],
                local_hdf5_ready=eng_ready,
                scientific_scope_note=(
                    "Approved Gate A.2 Engineering Validation Dataset. Partial-frame swath (~6.0 s, _N_P_J_) covers "
                    "the Riau Archipelago / Singapore Strait rather than mainland Riau."
                ),
                preset_aois=[
                    PresetAOI(
                        aoi_id="AOI-ENG-01",
                        name="AOI-ENG-01 — Interior Full-Valid Swath Window",
                        description="15 km × 15 km full-coverage interior window (100.0% valid pixels, COMPARABLE).",
                        bbox_wgs84=[104.20, 1.90, 104.35, 2.05],
                        default_evidence_id="E-PHASE2A-ENG-001",
                        selection_method="PREDEFINED_GEOGRAPHIC_AOI",
                        selection_time="PRE_ANALYSIS",
                        selection_basis="Predefined interior engineering validation window inside the illuminated T047_F087 swath.",
                    ),
                    PresetAOI(
                        aoi_id="AOI-ENG-02",
                        name="AOI-ENG-02 — Swath-Edge Boundary Window (mask == 0 Test)",
                        description="Swath-edge window demonstrating rejection of >1.36M finite-positive-power pixels with mask == 0 (LIMITED, 48.01% valid).",
                        bbox_wgs84=[103.12, 2.08, 103.30, 2.25],
                        default_evidence_id="E-PHASE2A-ENG-002",
                        selection_method="PREDEFINED_GEOGRAPHIC_AOI",
                        selection_time="PRE_ANALYSIS",
                        selection_basis="Predefined swath-edge boundary engineering window testing GCOV mask == 0 rejection.",
                    ),
                ],
            ),
        ]

    def get_case(self, case_id: str) -> CaseSummary:
        for c in self.get_cases():
            if c.case_id == case_id:
                return c
        raise_science_error(
            404,
            error_code="CASE_NOT_FOUND",
            message=f"Unknown case_id '{case_id}'.",
        )
        raise AssertionError("unreachable")

    def get_case_observations(self, case_id: str) -> CaseObservationsResponse:
        case = self.get_case(case_id)
        target_aoi = "AOI-A2" if case_id == "case-flagship-oki-f2" else "AOI-A1"
        preferred_tf = "T010_F176" if case_id == "case-flagship-oki-f2" else "T047_F087"

        obs_list: list[ObservationRecord] = []
        for s in self._manifest_scenes:
            if s.get("aoi_id") != target_aoi:
                continue
            tf = s.get("track_or_frame") or ""
            if case_id == "case-flagship-oki-f2" and tf not in ("T010_F176", "T119_F090"):
                continue
            if case_id == "case-engineering-riau-t047" and tf not in ("T047_F087", "T148_F088"):
                continue

            sid = s["scene_id"]
            h5_path = self.get_scene_h5_path(sid)
            pols = [
                PolarizationChannel(p)
                for p in (s.get("polarizations") or [])
                if p in PolarizationChannel.__members__
            ]
            notes = s.get("notes") or ""
            is_ff = "_N_F_J_" in sid or "_F_F_J_" in sid or "full_frame=TRUE" in notes.upper()

            obs_list.append(
                ObservationRecord(
                    scene_id=sid,
                    case_id=case_id,
                    acquisition_start_utc=s.get("acquisition_start_utc") or "",
                    acquisition_end_utc=s.get("acquisition_end_utc") or "",
                    acquisition_date=(s.get("acquisition_start_utc") or "")[:10],
                    track_or_frame=tf,
                    orbit_pass_direction=s.get("orbit_direction") or case.orbit_pass_direction,
                    look_direction=s.get("look_direction") or "LEFT",
                    polarizations=pols,
                    product_maturity=s.get("product_maturity") or "PROVISIONAL",
                    crid=s.get("crid") or "P05023",
                    processing_version=s.get("processing_version"),
                    is_full_frame=is_ff,
                    approx_file_size_bytes=s.get("approx_file_size_bytes"),
                    bbox_wgs84=s.get("bbox"),
                    local_hdf5_available=(h5_path is not None),
                    local_hdf5_path=str(h5_path) if h5_path is not None else None,
                    source_metadata={
                        "collection_short_name": s.get("collection_short_name"),
                        "granule_ur": s.get("granule_ur"),
                        "download_url": s.get("download_url"),
                        "metadata_source": s.get("metadata_source"),
                    },
                )
            )

        return CaseObservationsResponse(
            case_id=case_id,
            default_t0_scene_id=case.default_t0_scene_id,
            default_t1_scene_id=case.default_t1_scene_id,
            observations=obs_list,
        )

    def _find_manifest_scene(self, scene_id: str) -> NormalizedSceneMetadata | None:
        for s in self._manifest_scenes:
            if s.get("scene_id") == scene_id:
                return NormalizedSceneMetadata.model_validate(s)
        return None

    def validate_pair(self, req: ValidatePairRequest) -> ValidatePairResponse:
        """Run actual product-level or catalog-level pair validation (`POST /api/validate-pair`)."""
        p0 = self.get_scene_h5_path(req.scene_t0_id)
        p1 = self.get_scene_h5_path(req.scene_t1_id)

        default_bbox = req.aoi_bbox_wgs84
        if default_bbox is None:
            if req.case_id:
                default_bbox = self.get_case(req.case_id).default_aoi_bbox_wgs84
            else:
                default_bbox = [104.20, 1.90, 104.35, 2.05]

        # If identical scene IDs or incompatible metadata, run validate_scene_pair first
        m0 = self._find_manifest_scene(req.scene_t0_id)
        m1 = self._find_manifest_scene(req.scene_t1_id)

        if p0 is not None and p1 is not None and req.scene_t0_id != req.scene_t1_id:
            # Fast windowed product check on the actual HDF5 files
            try:
                w0 = read_gcov_window(p0, default_bbox)
                w1 = read_gcov_window(p1, default_bbox)
                res = run_in_memory_change_analysis(
                    win_t0=w0,
                    win_t1=w1,
                    roi_id="PAIR-VAL-CHECK",
                    evidence_id="E-PAIR-VAL-TEMP",
                )
                ev = res.evidence_record
                compatible = ev.quality_status in (
                    ScienceQualityStatus.COMPARABLE,
                    ScienceQualityStatus.LIMITED,
                )
                reasons = (
                    []
                    if compatible
                    else [
                        f"Insufficient valid comparable pixel coverage ({ev.coverage_ratio * 100:.2f}%) in AOI {default_bbox}."
                    ]
                )
                warnings = list(ev.limitations)
                val_res = ScenePairValidationResult(
                    compatible=compatible,
                    validation_decision="PASS" if compatible else "FAIL",
                    reasons=reasons,
                    warnings=warnings,
                    valid_overlap_ratio=ev.coverage_ratio,
                    spatial_overlap_ratio=1.0 if not w0.window.fully_outside_grid else 0.0,
                    available_polarizations=ev.polarizations,
                    scene_ids=[req.scene_t0_id, req.scene_t1_id],
                    t0_utc=w0.acquisition_start_utc,
                    t1_utc=w1.acquisition_start_utc,
                    frequency_band="L",
                    frequency_group=w0.frequency_group,
                    same_orbit_pass=(w0.orbit_pass_direction == w1.orbit_pass_direction),
                    same_look_direction=(w0.look_direction == w1.look_direction),
                    crs_compatible=(w0.grid.epsg == w1.grid.epsg),
                    grid_aligned=True,
                    metadata_checks={
                        "crs_epsg": w0.grid.epsg,
                        "valid_pixel_count": ev.valid_pixel_count,
                        "valid_area_km2": ev.summary_statistics.get("valid_area_km2"),
                        "is_full_frame_t0": w0.is_full_frame,
                        "is_full_frame_t1": w1.is_full_frame,
                    },
                    science_status=ev.quality_status,
                )
                return ValidatePairResponse(
                    validation_level="PRODUCT_HDF5",
                    result=val_res,
                    product_validation_summary={
                        "valid_pixel_count": ev.valid_pixel_count,
                        "coverage_ratio": ev.coverage_ratio,
                        "missing_data_ratio": ev.missing_data_ratio,
                        "crs_epsg": w0.grid.epsg,
                    },
                )
            except Exception as exc:
                val_res = ScenePairValidationResult(
                    compatible=False,
                    validation_decision="FAIL",
                    reasons=[str(exc)],
                    warnings=[],
                    valid_overlap_ratio=0.0,
                    spatial_overlap_ratio=0.0,
                    available_polarizations=[],
                    scene_ids=[req.scene_t0_id, req.scene_t1_id],
                    science_status=ScienceQualityStatus.INSUFFICIENT_EVIDENCE,
                )
                return ValidatePairResponse(
                    validation_level="PRODUCT_HDF5",
                    result=val_res,
                    product_validation_summary={"error": str(exc)},
                )

        if m0 is None or m1 is None:
            raise_science_error(
                404,
                error_code="SCENE_NOT_FOUND",
                message=f"Scene metadata not found for '{req.scene_t0_id}' or '{req.scene_t1_id}'.",
            )
            raise AssertionError("unreachable")

        val_res = validate_scene_pair(m0, m1, aoi=default_bbox)
        return ValidatePairResponse(
            validation_level="CATALOG_METADATA",
            result=val_res,
            product_validation_summary=None,
        )

    def _validate_bbox_coords(self, bbox: list[float]) -> None:
        min_lon, min_lat, max_lon, max_lat = bbox
        if min_lon >= max_lon or min_lat >= max_lat:
            raise_science_error(
                422,
                error_code="INVALID_AOI_BOUNDS",
                message=f"Invalid AOI bounding box {bbox}: min_lon < max_lon and min_lat < max_lat required.",
            )

    def _build_deterministic_claims(
        self,
        *,
        case_id: str,
        ev: EvidenceRecord,
        aoi_bbox: list[float],
    ) -> list[DeterministicClaim]:
        """Generate deterministic Claim-to-Evidence statements (Section 3.5)."""
        claims: list[DeterministicClaim] = []
        valid_area_km2 = float(ev.summary_statistics.get("valid_area_km2", 0.0))
        per_pol = ev.summary_statistics.get("per_polarization", {})

        for pol in ev.polarizations:
            ps = per_pol.get(pol.value, {})
            med_delta = ps.get("median_delta_db")
            med_t0 = ps.get("median_t0_db")
            med_t1 = ps.get("median_t1_db")
            med_abs = ps.get("median_abs_change_db")
            if med_delta is not None and med_t0 is not None and med_t1 is not None:
                sign_prefix = "+" if med_delta > 0 else ""
                claims.append(
                    DeterministicClaim(
                        claim_id=f"{ev.evidence_id}-CLAIM-DELTA-{pol.value}",
                        statement=(
                            f"Median {pol.value} backscatter changed by {sign_prefix}{med_delta:.4f} dB "
                            f"(from {med_t0:.4f} dB at T0 to {med_t1:.4f} dB at T1) across "
                            f"{ev.valid_pixel_count:,} valid comparable 10 m pixels ({valid_area_km2:.3f} km²)."
                        ),
                        evidence_id=ev.evidence_id,
                        case_id=case_id,
                        roi_id=ev.roi_id,
                        scene_ids=list(ev.scene_ids),
                        aoi_bbox_wgs84=aoi_bbox,
                        polarization=pol,
                        metric_name=f"median_delta_{pol.value.lower()}_db",
                        metric_value=float(med_delta),
                        unit="dB",
                        valid_pixel_count=ev.valid_pixel_count,
                        valid_area_km2=valid_area_km2,
                        algorithm_version=ev.algorithm_version,
                        calculation_formula=f"median(10*log10({pol.value}_T1) - 10*log10({pol.value}_T0)) where 0 < mask < 255 and P > 0",
                        target_layer_type=f"delta_{pol.value.lower()}",
                    )
                )
            if med_abs is not None:
                claims.append(
                    DeterministicClaim(
                        claim_id=f"{ev.evidence_id}-CLAIM-MAG-{pol.value}",
                        statement=(
                            f"Median absolute |Δ{pol.value}| change magnitude is {med_abs:.4f} dB "
                            f"(p90 = {ps.get('p90_abs_change_db', 0.0):.4f} dB) across {ev.valid_pixel_count:,} valid pixels."
                        ),
                        evidence_id=ev.evidence_id,
                        case_id=case_id,
                        roi_id=ev.roi_id,
                        scene_ids=list(ev.scene_ids),
                        aoi_bbox_wgs84=aoi_bbox,
                        polarization=pol,
                        metric_name=f"median_abs_change_{pol.value.lower()}_db",
                        metric_value=float(med_abs),
                        unit="dB",
                        valid_pixel_count=ev.valid_pixel_count,
                        valid_area_km2=valid_area_km2,
                        algorithm_version=ev.algorithm_version,
                        calculation_formula=f"median(abs(Delta_{pol.value})) where 0 < mask < 255 and P > 0",
                        target_layer_type=f"magnitude_{pol.value.lower()}",
                    )
                )

        if ev.combined_change_db is not None:
            c_med = ev.combined_change_db.stats.median
            c_p90 = ev.combined_change_db.stats.p90 or 0.0
            claims.append(
                DeterministicClaim(
                    claim_id=f"{ev.evidence_id}-CLAIM-COMBINED",
                    statement=(
                        f"Combined Radar Change (|ΔHH| + |ΔHV|) has median {c_med:.4f} dB composite "
                        f"[custom change magnitude: sum of absolute dB changes] "
                        f"(p90 = {c_p90:.4f} dB composite) across {ev.valid_pixel_count:,} valid comparable pixels "
                        f"({COMBINED_RADAR_CHANGE_DISCLAIMER})"
                    ),
                    evidence_id=ev.evidence_id,
                    case_id=case_id,
                    roi_id=ev.roi_id,
                    scene_ids=list(ev.scene_ids),
                    aoi_bbox_wgs84=aoi_bbox,
                    polarization=None,
                    metric_name="median_combined_radar_change_db",
                    metric_value=float(c_med),
                    unit="dB composite",
                    valid_pixel_count=ev.valid_pixel_count,
                    valid_area_km2=valid_area_km2,
                    algorithm_version=ev.algorithm_version,
                    calculation_formula="abs(Delta_HH) + abs(Delta_HV)",
                    target_layer_type="combined_change",
                )
            )

        return claims

    def _build_epistemic_panel(self, ev: EvidenceRecord) -> EpistemicSummaryPanel:
        """Build deterministic 'What We Observed / What May Explain It / What We Do Not Know' content (Section 3.4)."""
        prov = (
            ev.processing_metadata.model_dump()
            if hasattr(ev.processing_metadata, "model_dump")
            else dict(ev.processing_metadata)
        )
        t0_utc = prov.get("t0_acquisition_utc", "")
        t1_utc = prov.get("t1_acquisition_utc", "")
        valid_km2 = float(ev.summary_statistics.get("valid_area_km2", 0.0))
        valid_ha = float(ev.summary_statistics.get("valid_area_ha", 0.0))
        per_pol = ev.summary_statistics.get("per_polarization", {})

        is_flagship = t0_utc.startswith("2026-09-06") and t1_utc.startswith("2026-09-18")
        observed: list[str] = []
        if is_flagship:
            observed.append(
                "NISAR observed radar backscatter change between 6 Sep and 18 Sep 2026."
            )
        observed.append(
            f"Multi-temporal NISAR L-band Level-2 GCOV comparison between T0 ({t0_utc}) and T1 ({t1_utc}) evaluated {ev.valid_pixel_count:,} common valid 10 m pixels ({valid_km2:.3f} km² / {valid_ha:,.1f} ha; valid coverage = {ev.coverage_ratio * 100:.2f}%, missing/invalid = {ev.missing_data_ratio * 100:.2f}%) [{ev.evidence_id}]."
        )
        for pol in ev.polarizations:
            ps = per_pol.get(pol.value, {})
            if ps.get("median_delta_db") is not None:
                sign_p = "+" if ps["median_delta_db"] > 0 else ""
                observed.append(
                    f"{pol.value} backscatter: T0 median = {ps['median_t0_db']:.4f} dB, T1 median = {ps['median_t1_db']:.4f} dB, signed median Δ{pol.value} = {sign_p}{ps['median_delta_db']:.4f} dB (p10 = {ps['p10_delta_db']:.4f} dB, p90 = {ps['p90_delta_db']:.4f} dB), median |Δ{pol.value}| = {ps['median_abs_change_db']:.4f} dB ({ps['positive_change_fraction'] * 100:.1f}% positive change, {ps['negative_change_fraction'] * 100:.1f}% negative change) [{ev.evidence_id}]."
                )
        if ev.combined_change_db is not None:
            cs = ev.combined_change_db.stats
            observed.append(
                f"Combined Radar Change (|ΔHH| + |ΔHV|): median = {cs.median:.4f} dB composite [custom change magnitude: sum of absolute dB changes], mean = {cs.mean:.4f} dB composite, p90 = {cs.p90:.4f} dB composite ({COMBINED_RADAR_CHANGE_DISCLAIMER}) [{ev.evidence_id}]."
            )

        may_explain: list[str] = []
        if is_flagship:
            may_explain.append(
                "Independent records document wildfire activity in South Sumatra / OKI during this period (BMKG ~10 Sep 2026 hotspot/smoke bulletin; BNPB ~17 Sep 2026 karhutla emergency response)."
            )
        may_explain.extend(
            [
                "Canopy & Woody Structure (L-band ~24 cm wavelength): Decreases in HV cross-polarized backscatter (ΔHV < 0 dB) are physically consistent with a reduction in depolarizing woody canopy volume or scrub structure.",
                "Dielectric Moisture & Water-Table Shifts: Decreases in HH and HV backscatter can reflect surface drying of peat/mineral soil or foliage during dry-season drawdown, whereas increases (ΔHH > 0 dB) can reflect surface wetting or double-bounce scattering.",
                "Surface Roughness & Clearing: Changes in decimeter-scale surface roughness from land clearing, agricultural tillage, or post-disturbance exposure alter co-polarized HH return.",
            ]
        )

        do_not_know: list[str] = [
            "The radar observation alone does not prove that wildfire caused every observed change (limitation: cause_not_determined).",
            "Not a burn-severity index, fire-damage classifier, or underground peat-fire detector (limitation: not_burn_severity_or_fire_damage).",
            f"Exact timing of surface change within the interval between T0 ({t0_utc[:10]}) and T1 ({t1_utc[:10]}) cannot be pinpointed from two acquisitions alone.",
            "Provisional NISAR L2 GCOV product maturity (CRID P05023): radiometric calibration is provisional, and _QA_STATS.h5 rfiLikelihood metadata is marked rfi_comparison_status = UNRELIABLE_METADATA (isce-framework/isce3#294).",
        ]
        if "partial_valid_coverage" in ev.limitations:
            do_not_know.append(
                f"Partial valid coverage ({ev.coverage_ratio * 100:.2f}%): {ev.missing_data_ratio * 100:.2f}% of pixels in this AOI were excluded due to GCOV mask == 0 (partially focused), mask == 255 (outside swath), or non-positive power."
            )

        return EpistemicSummaryPanel(
            what_we_observed=observed,
            what_may_explain_it=may_explain,
            what_we_do_not_know=do_not_know,
        )

    def _resolve_aoi_provenance(
        self,
        case: CaseSummary,
        req_aoi_id: str | None,
        req_bbox: list[float],
        requested_polarizations: list[PolarizationChannel] | None,
        t0_id: str,
        t1_id: str,
    ) -> tuple[str, str, str, str, str]:
        """Resolve (roi_id, evidence_id, selection_method, selection_time, selection_basis)."""
        for preset in case.preset_aois:
            if (
                req_aoi_id == preset.aoi_id
                or [round(x, 4) for x in req_bbox] == [round(x, 4) for x in preset.bbox_wgs84]
            ) and (
                requested_polarizations is None
                or set(requested_polarizations) == {PolarizationChannel.HH, PolarizationChannel.HV}
            ):
                return (
                    preset.aoi_id,
                    preset.default_evidence_id or f"E-{preset.aoi_id}",
                    preset.selection_method,
                    preset.selection_time,
                    preset.selection_basis,
                )

        bbox_hash = hashlib.sha1(
            json.dumps([round(x, 5) for x in req_bbox]).encode("utf-8")
        ).hexdigest()[:6].upper()
        roi_id = req_aoi_id or f"AOI-CUSTOM-{bbox_hash}"

        pol_tag = (
            "-".join(sorted(p.value for p in requested_polarizations))
            if requested_polarizations
            else "DUAL"
        )
        sig = f"{case.case_id}:{t0_id}:{t1_id}:{[round(x, 5) for x in req_bbox]}:{pol_tag}"
        ev_hash = hashlib.sha1(sig.encode("utf-8")).hexdigest()[:8].upper()
        evidence_id = f"E-AOI-{ev_hash}"
        return (
            roi_id,
            evidence_id,
            "EXPLORATORY_POST_HOC_RADAR_CHANGE",
            "POST_HOC_INSPECTION",
            f"User-defined / interactive AOI box {req_bbox} selected on the map during exploratory radar inspection.",
        )

    def analyze_change(self, req: AnalyzeChangeRequest) -> AnalyzeChangeResponse:
        """Run deterministic windowed Change Engine analysis (`POST /api/change/analyze`)."""
        self._validate_bbox_coords(req.aoi_bbox_wgs84)
        case = self.get_case(req.case_id)
        t0_id = req.scene_t0_id or case.default_t0_scene_id
        t1_id = req.scene_t1_id or case.default_t1_scene_id

        if t0_id == t1_id:
            raise_science_error(
                422,
                error_code="INCOMPATIBLE_PAIR",
                message="Scene T0 and Scene T1 cannot be identical.",
            )

        # Check metadata pair compatibility (pair-level first, then AOI coverage)
        m0 = self._find_manifest_scene(t0_id)
        m1 = self._find_manifest_scene(t1_id)
        if m0 is not None and m1 is not None:
            pair_only_check = validate_scene_pair(m0, m1, aoi=None)
            if not pair_only_check.compatible:
                raise_science_error(
                    422,
                    error_code="INCOMPATIBLE_PAIR",
                    message="; ".join(pair_only_check.reasons),
                    science_status=pair_only_check.science_status,
                    details=pair_only_check.model_dump(mode="json"),
                )
            aoi_check = validate_scene_pair(m0, m1, aoi=req.aoi_bbox_wgs84)
            if not aoi_check.compatible:
                raise_science_error(
                    422,
                    error_code="AOI_OUTSIDE_COVERAGE",
                    message="; ".join(aoi_check.reasons),
                    science_status=ScienceQualityStatus.INSUFFICIENT_EVIDENCE,
                    details=aoi_check.model_dump(mode="json"),
                )

        # Check requested polarizations
        if req.requested_polarizations is not None:
            if len(req.requested_polarizations) == 0:
                raise_science_error(
                    422,
                    error_code="UNAVAILABLE_POLARIZATION",
                    message="At least one polarization must be requested.",
                )
            for pol in req.requested_polarizations:
                if pol not in case.polarizations:
                    raise_science_error(
                        422,
                        error_code="UNAVAILABLE_POLARIZATION",
                        message=f"Requested polarization '{pol.value}' is unavailable in this NISAR scene pair (available: {[p.value for p in case.polarizations]}).",
                    )

        roi_id, evidence_id, sel_method, sel_time, sel_basis = self._resolve_aoi_provenance(
            case,
            req.aoi_id,
            req.aoi_bbox_wgs84,
            req.requested_polarizations,
            t0_id,
            t1_id,
        )

        p0 = self.get_scene_h5_path(t0_id)
        p1 = self.get_scene_h5_path(t1_id)

        # Serve from persisted real-NISAR cache if already computed and all PNGs exist on disk
        if evidence_id in self._analysis_map:
            cached_resp = self._analysis_map[evidence_id]
            all_pngs_exist = all(
                (PNG_CACHE_DIR / f"{l_meta.layer_id}.png").exists()
                for l_meta in cached_resp.layers.values()
            )
            if all_pngs_exist:
                return cached_resp.model_copy(
                    update={
                        "demo_mode": "CACHED_REAL_DATA",
                        "cache_hit": True,
                    }
                )

        if self.demo_mode == "CACHED_REAL_DATA" and (p0 is None or p1 is None):
            raise_science_error(
                422,
                error_code="CACHED_AOI_NOT_FOUND",
                message=(
                    f"DEMO_MODE is CACHED_REAL_DATA and AOI '{roi_id}' ({evidence_id}) is not in the pre-generated "
                    "real NISAR cache while local HDF5 granules are offline."
                ),
            )

        if p0 is None or p1 is None:
            raise_science_error(
                422,
                error_code="LOCAL_HDF5_UNAVAILABLE",
                message=f"Local HDF5 files are not available for pair ({t0_id}, {t1_id}).",
            )
            raise AssertionError("unreachable")

        # Read windowed HDF5 slices
        w0 = read_gcov_window(p0, req.aoi_bbox_wgs84)
        w1 = read_gcov_window(p1, req.aoi_bbox_wgs84)

        # If caller explicitly restricted polarizations (e.g. ['HH'] only to test missing HV), apply restriction
        if req.requested_polarizations is not None:
            req_set = {p.value for p in req.requested_polarizations}
            w0_pols = [p for p in w0.available_polarizations if p in req_set]
            w1_pols = [p for p in w1.available_polarizations if p in req_set]
            w0 = GCOVSceneWindow(
                **{
                    **w0.__dict__,
                    "available_polarizations": w0_pols,
                    "power": {k: (v if k in req_set else None) for k, v in w0.power.items()},
                }
            )
            w1 = GCOVSceneWindow(
                **{
                    **w1.__dict__,
                    "available_polarizations": w1_pols,
                    "power": {k: (v if k in req_set else None) for k, v in w1.power.items()},
                }
            )

        res = run_in_memory_change_analysis(
            win_t0=w0,
            win_t1=w1,
            roi_id=roi_id,
            evidence_id=evidence_id,
        )
        ev = res.evidence_record
        ev.selection_method = sel_method
        ev.selection_time = sel_time
        ev.selection_basis = sel_basis
        ev.summary_statistics["aoi_selection_provenance"] = {
            "selection_method": sel_method,
            "selection_time": sel_time,
            "selection_basis": sel_basis,
        }
        if isinstance(ev.processing_metadata, dict):
            ev.processing_metadata["rfi_comparison_status"] = "UNRELIABLE_METADATA"
            ev.processing_metadata["t0_orbit_pointing_fidelity"] = case.t0_orbit_pointing_fidelity
            ev.processing_metadata["t1_orbit_pointing_fidelity"] = case.t1_orbit_pointing_fidelity
        else:
            ev.processing_metadata = ProcessingProvenanceMetadata.model_validate(
                {
                    **ev.processing_metadata.model_dump(),
                    "rfi_comparison_status": "UNRELIABLE_METADATA",
                    "t0_orbit_pointing_fidelity": case.t0_orbit_pointing_fidelity,
                    "t1_orbit_pointing_fidelity": case.t1_orbit_pointing_fidelity,
                }
            )

        if ev.quality_status == ScienceQualityStatus.INSUFFICIENT_EVIDENCE or ev.valid_pixel_count == 0:
            raise_science_error(
                422,
                error_code="AOI_OUTSIDE_COVERAGE",
                message=(
                    f"Selected AOI {req.aoi_bbox_wgs84} has insufficient valid comparable radar observations "
                    f"(valid_pixel_count={ev.valid_pixel_count}, coverage_ratio={ev.coverage_ratio:.4f})."
                ),
                science_status=ScienceQualityStatus.INSUFFICIENT_EVIDENCE,
                details={
                    "evidence_id": ev.evidence_id,
                    "valid_pixel_count": ev.valid_pixel_count,
                    "coverage_ratio": ev.coverage_ratio,
                    "missing_data_ratio": ev.missing_data_ratio,
                    "limitations": ev.limitations,
                },
            )

        layers = export_analysis_png_layers(
            res,
            case_id=case.case_id,
            png_dir=PNG_CACHE_DIR,
        )
        self._save_evidence(ev)
        self._save_layers(layers)

        claims = self._build_deterministic_claims(
            case_id=case.case_id,
            ev=ev,
            aoi_bbox=req.aoi_bbox_wgs84,
        )

        unavail_pols = [
            PolarizationChannel(p)
            for p in res.unavailable_polarizations
            if p in PolarizationChannel.__members__
        ]

        out_resp = AnalyzeChangeResponse(
            job_id=f"JOB-{ev.evidence_id}",
            status="completed",
            case_id=case.case_id,
            roi_id=roi_id,
            evidence_id=ev.evidence_id,
            quality_status=ev.quality_status,
            scene_t0_id=t0_id,
            scene_t1_id=t1_id,
            t0_acquisition_utc=w0.acquisition_start_utc,
            t1_acquisition_utc=w1.acquisition_start_utc,
            aoi_bbox_wgs84=req.aoi_bbox_wgs84,
            available_polarizations=ev.polarizations,
            unavailable_polarizations=unavail_pols,
            valid_pixel_count=ev.valid_pixel_count,
            valid_area_km2=float(ev.summary_statistics["valid_area_km2"]),
            valid_area_ha=float(ev.summary_statistics["valid_area_ha"]),
            coverage_ratio=ev.coverage_ratio,
            missing_data_ratio=ev.missing_data_ratio,
            layers=layers,
            claims=claims,
            evidence_record=ev,
            selection_method=sel_method,
            selection_time=sel_time,
            selection_basis=sel_basis,
            demo_mode=self.demo_mode,
            cache_hit=False,
        )
        self._save_analysis_cache(ev.evidence_id, out_resp)
        return out_resp

    def compute_radar_fingerprint(self, req: RadarFingerprintRequest) -> RadarFingerprintResponse:
        """Compute deterministic AOI Radar Fingerprint (`POST /api/radar-fingerprint`)."""
        analysis = self.analyze_change(
            AnalyzeChangeRequest(
                case_id=req.case_id,
                scene_t0_id=req.scene_t0_id,
                scene_t1_id=req.scene_t1_id,
                aoi_id=req.aoi_id,
                aoi_bbox_wgs84=req.aoi_bbox_wgs84,
                requested_polarizations=req.requested_polarizations,
            )
        )
        ev = analysis.evidence_record
        if analysis.cache_hit and ev.evidence_id in self._fingerprint_map:
            return self._fingerprint_map[ev.evidence_id].model_copy(
                update={
                    "demo_mode": "CACHED_REAL_DATA",
                    "cache_hit": True,
                }
            )
        per_pol = ev.summary_statistics.get("per_polarization", {})

        def _make_pol_detail(pol: PolarizationChannel) -> tuple[PolarizationFingerprintDetail, PolarizationChangeBreakdown | None]:
            if pol not in ev.polarizations or pol.value not in per_pol:
                return (
                    PolarizationFingerprintDetail(
                        polarization=pol,
                        available=False,
                        status_label="Unavailable",
                    ),
                    None,
                )
            ps = per_pol[pol.value]
            if ps.get("valid_pixel_count", 0) == 0 or ps.get("delta_distribution_db") is None:
                return (
                    PolarizationFingerprintDetail(
                        polarization=pol,
                        available=False,
                        status_label="Unavailable",
                    ),
                    None,
                )
            d_dist = DistributionStatsDb.model_validate(ps["delta_distribution_db"])
            m_dist = DistributionStatsDb.model_validate(ps["magnitude_distribution_db"])
            detail = PolarizationFingerprintDetail(
                polarization=pol,
                available=True,
                status_label="Available",
                t0_median_db=ps["median_t0_db"],
                t0_mean_db=ps["mean_t0_db"],
                t1_median_db=ps["median_t1_db"],
                t1_mean_db=ps["mean_t1_db"],
                delta_median_db=ps["median_delta_db"],
                delta_mean_db=ps["mean_delta_db"],
                delta_distribution_db=d_dist,
                magnitude_median_db=ps["median_abs_change_db"],
                magnitude_mean_db=ps["mean_abs_change_db"],
                magnitude_distribution_db=m_dist,
                positive_change_fraction=ps["positive_change_fraction"],
                negative_change_fraction=ps["negative_change_fraction"],
            )
            breakdown = PolarizationChangeBreakdown(
                polarization=pol,
                t0_mean_db=ps["mean_t0_db"],
                t1_mean_db=ps["mean_t1_db"],
                delta_mean_db=ps["mean_delta_db"],
                magnitude_mean_db=ps["mean_abs_change_db"],
                t0_median_db=ps["median_t0_db"],
                t1_median_db=ps["median_t1_db"],
                delta_median_db=ps["median_delta_db"],
            )
            return detail, breakdown

        hh_detail, hh_breakdown = _make_pol_detail(PolarizationChannel.HH)
        hv_detail, hv_breakdown = _make_pol_detail(PolarizationChannel.HV)

        epistemic_panel = self._build_epistemic_panel(ev)

        pair_compat = ScenePairValidationResult(
            compatible=True,
            validation_decision="PASS",
            reasons=[],
            warnings=list(ev.limitations),
            valid_overlap_ratio=ev.coverage_ratio,
            spatial_overlap_ratio=1.0,
            available_polarizations=ev.polarizations,
            scene_ids=list(ev.scene_ids),
            t0_utc=analysis.t0_acquisition_utc,
            t1_utc=analysis.t1_acquisition_utc,
            frequency_band="L",
            frequency_group="frequencyA",
            same_orbit_pass=True,
            same_look_direction=True,
            crs_compatible=True,
            grid_aligned=True,
            science_status=ev.quality_status,
        )

        fp = RadarFingerprint(
            fingerprint_id=f"FP-{ev.evidence_id}",
            evidence_id=ev.evidence_id,
            roi_id=analysis.roi_id,
            t0_acquisition_utc=analysis.t0_acquisition_utc,
            t1_acquisition_utc=analysis.t1_acquisition_utc,
            available_polarizations=ev.polarizations,
            hh=hh_breakdown,
            hv=hv_breakdown,
            combined_radar_change_db=(
                ev.combined_change_db.stats.mean if ev.combined_change_db is not None else None
            ),
            valid_pixel_count=ev.valid_pixel_count,
            valid_coverage_ratio=ev.coverage_ratio,
            missing_data_ratio=ev.missing_data_ratio,
            pair_compatibility=pair_compat,
            quality_status=ev.quality_status,
            processing_metadata=ev.processing_metadata,
            what_we_observed=epistemic_panel.what_we_observed,
            possible_interpretations=epistemic_panel.what_may_explain_it,
            what_we_do_not_know=epistemic_panel.what_we_do_not_know,
        )

        combined_detail = (
            {
                "formula": "abs(Delta_HH) + abs(Delta_HV)",
                "unit": "dB composite",
                "unit_description": "custom change magnitude (sum of absolute dB changes)",
                **ev.combined_change_db.model_dump(mode="json"),
            }
            if ev.combined_change_db is not None
            else None
        )

        fp_resp = RadarFingerprintResponse(
            fingerprint=fp,
            case_id=req.case_id,
            roi_id=analysis.roi_id,
            evidence_id=ev.evidence_id,
            quality_status=ev.quality_status,
            t0_acquisition_utc=analysis.t0_acquisition_utc,
            t1_acquisition_utc=analysis.t1_acquisition_utc,
            aoi_bbox_wgs84=req.aoi_bbox_wgs84,
            available_polarizations=ev.polarizations,
            unavailable_polarizations=analysis.unavailable_polarizations,
            hh_detail=hh_detail,
            hv_detail=hv_detail,
            combined_radar_change_detail=combined_detail,
            valid_pixel_count=ev.valid_pixel_count,
            valid_area_m2=float(ev.summary_statistics["valid_area_m2"]),
            valid_area_ha=float(ev.summary_statistics["valid_area_ha"]),
            valid_area_km2=float(ev.summary_statistics["valid_area_km2"]),
            coverage_ratio=ev.coverage_ratio,
            missing_invalid_fraction=ev.missing_data_ratio,
            epistemic_panel=epistemic_panel,
            claims=analysis.claims,
            layers=analysis.layers,
            evidence_record=ev,
            selection_method=analysis.selection_method,
            selection_time=analysis.selection_time,
            selection_basis=analysis.selection_basis,
            demo_mode=self.demo_mode,
            cache_hit=analysis.cache_hit,
        )
        self._save_fingerprint_cache(ev.evidence_id, fp_resp)
        return fp_resp

    def get_evidence(self, evidence_id: str) -> EvidenceRecord:
        self._load_stores()
        if evidence_id not in self._evidence_map:
            raise_science_error(
                404,
                error_code="EVIDENCE_NOT_FOUND",
                message=f"EvidenceRecord '{evidence_id}' not found in Evidence Store.",
            )
        return self._evidence_map[evidence_id]

    def get_layer_metadata(self, layer_id: str) -> LayerMetadataResponse:
        self._load_stores()
        if layer_id not in self._layer_map:
            raise_science_error(
                404,
                error_code="LAYER_NOT_FOUND",
                message=f"Layer '{layer_id}' not found.",
            )
        return self._layer_map[layer_id]

    def get_layer_png_bytes(self, layer_id: str) -> bytes:
        png_path = PNG_CACHE_DIR / f"{layer_id}.png"
        if not png_path.exists():
            raise_science_error(
                404,
                error_code="LAYER_IMAGE_NOT_FOUND",
                message=f"PNG overlay for layer '{layer_id}' not found on disk.",
            )
        return png_path.read_bytes()

    def get_health(self) -> HealthResponse:
        self._load_stores()
        cases = self.get_cases()
        return HealthResponse(
            demo_mode=self.demo_mode,
            rfi_comparison_status="UNRELIABLE_METADATA",
            evidence_count=len(self._evidence_map),
            available_cases=[c.case_id for c in cases],
        )
