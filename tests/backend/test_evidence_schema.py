"""Unit tests for SAR2Action Phase 0 Evidence, Pair Validation, Fingerprint, and Story schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.evidence import (
    CombinedRadarChangeMetric,
    DistributionStatsDb,
    EvidenceClaim,
    EvidenceRecord,
    EvidenceStory,
    EvidenceType,
    PolarizationChangeBreakdown,
    PolarizationChannel,
    RadarFingerprint,
    ScenePairValidationResult,
    ScienceQualityStatus,
    StoryScene,
    StorySceneKey,
)


def _sample_stats(mean: float = -3.1, median: float = -3.0, std: float = 0.8) -> DistributionStatsDb:
    return DistributionStatsDb(
        mean=mean,
        median=median,
        std=std,
        min=mean - 2.5,
        max=mean + 2.5,
        p10=mean - 1.2,
        p90=mean + 1.2,
    )


def test_scene_pair_validation_compatible_pair() -> None:
    res = ScenePairValidationResult(
        compatible=True,
        reasons=[],
        warnings=[],
        valid_overlap_ratio=0.91,
        spatial_overlap_ratio=0.99,
        available_polarizations=[PolarizationChannel.HH, PolarizationChannel.HV],
        scene_ids=["SCENE_T0", "SCENE_T1"],
        science_status=ScienceQualityStatus.COMPARABLE,
    )
    assert res.compatible is True
    assert res.science_status == ScienceQualityStatus.COMPARABLE


def test_scene_pair_validation_rejects_inconsistent_status() -> None:
    with pytest.raises(ValidationError, match="INSUFFICIENT_EVIDENCE"):
        ScenePairValidationResult(
            compatible=False,
            reasons=["Opposite orbit pass direction"],
            valid_overlap_ratio=0.0,
            available_polarizations=[],
            scene_ids=["SCENE_T0", "SCENE_T1"],
            science_status=ScienceQualityStatus.COMPARABLE,
        )

    with pytest.raises(ValidationError, match="at least one blocking reason"):
        ScenePairValidationResult(
            compatible=False,
            reasons=[],
            valid_overlap_ratio=0.0,
            available_polarizations=[],
            scene_ids=["SCENE_T0", "SCENE_T1"],
            science_status=ScienceQualityStatus.INSUFFICIENT_EVIDENCE,
        )


def test_evidence_record_enforces_cause_not_determined_and_dual_pol_rule() -> None:
    rec = EvidenceRecord(
        evidence_id="E-001",
        evidence_type=EvidenceType.RADAR_CHANGE,
        scene_ids=["SCENE_T0", "SCENE_T1"],
        roi_id="ROI-01",
        polarizations=[PolarizationChannel.HH, PolarizationChannel.HV],
        delta_db={
            PolarizationChannel.HH: _sample_stats(-1.5),
            PolarizationChannel.HV: _sample_stats(-3.1),
        },
        combined_change_db=CombinedRadarChangeMetric(stats=_sample_stats(4.6)),
        valid_pixel_count=12500,
        coverage_ratio=0.88,
        quality_status=ScienceQualityStatus.COMPARABLE,
        limitations=[],
    )
    assert "cause_not_determined" in rec.limitations
    assert rec.combined_change_db is not None
    assert (
        rec.combined_change_db.disclaimer
        == "Custom visualization metric — not a hazard score, fire probability, damage score, or official burn-severity index."
    )


def test_evidence_record_forbids_combined_change_when_hv_missing() -> None:
    with pytest.raises(ValidationError, match="unless both HH and HV"):
        EvidenceRecord(
            evidence_id="E-002",
            evidence_type=EvidenceType.RADAR_CHANGE,
            scene_ids=["SCENE_T0", "SCENE_T1"],
            roi_id="ROI-01",
            polarizations=[PolarizationChannel.HH],
            delta_db={PolarizationChannel.HH: _sample_stats(-1.5)},
            combined_change_db=CombinedRadarChangeMetric(stats=_sample_stats(1.5)),
            valid_pixel_count=1000,
            coverage_ratio=0.75,
            quality_status=ScienceQualityStatus.LIMITED,
        )


def test_radar_fingerprint_null_safe_missing_polarization() -> None:
    pair_qa = ScenePairValidationResult(
        compatible=True,
        reasons=[],
        warnings=["HV polarization unavailable in T1; restricting comparison to HH."],
        valid_overlap_ratio=0.82,
        available_polarizations=[PolarizationChannel.HH],
        scene_ids=["SCENE_T0", "SCENE_T1"],
        science_status=ScienceQualityStatus.LIMITED,
    )
    fp = RadarFingerprint(
        fingerprint_id="FP-001",
        evidence_id="E-003",
        roi_id="ROI-02",
        t0_acquisition_utc="2026-08-01T11:20:00Z",
        t1_acquisition_utc="2026-08-13T11:20:02Z",
        available_polarizations=[PolarizationChannel.HH],
        hh=PolarizationChangeBreakdown(
            polarization=PolarizationChannel.HH,
            t0_mean_db=-7.5,
            t1_mean_db=-9.1,
            delta_mean_db=-1.6,
            magnitude_mean_db=1.6,
        ),
        hv=None,
        combined_radar_change_db=None,
        valid_pixel_count=4200,
        valid_coverage_ratio=0.82,
        missing_data_ratio=0.18,
        pair_compatibility=pair_qa,
        quality_status=ScienceQualityStatus.LIMITED,
    )
    assert fp.hv is None
    assert fp.combined_radar_change_db is None

    # Attempting to populate HV when HV is not in available_polarizations must fail
    with pytest.raises(ValidationError, match="HV is not in available_polarizations"):
        RadarFingerprint(
            fingerprint_id="FP-002",
            evidence_id="E-004",
            roi_id="ROI-02",
            t0_acquisition_utc="2026-08-01T11:20:00Z",
            t1_acquisition_utc="2026-08-13T11:20:02Z",
            available_polarizations=[PolarizationChannel.HH],
            hh=fp.hh,
            hv=PolarizationChangeBreakdown(
                polarization=PolarizationChannel.HV,
                t0_mean_db=-13.0,
                t1_mean_db=-15.0,
                delta_mean_db=-2.0,
                magnitude_mean_db=2.0,
            ),
            valid_pixel_count=4200,
            valid_coverage_ratio=0.82,
            missing_data_ratio=0.18,
            pair_compatibility=pair_qa,
            quality_status=ScienceQualityStatus.LIMITED,
        )


def test_evidence_story_requires_exact_five_scene_sequence() -> None:
    claim = EvidenceClaim(
        claim_id="C-001",
        statement="Mean HV backscatter changed by -3.10 dB.",
        evidence_ids=["E-001"],
        target_roi_id="ROI-01",
        target_scene_ids=["SCENE_T0", "SCENE_T1"],
        target_polarization=PolarizationChannel.HV,
        target_layer_mode="delta",
    )
    scenes = [
        StoryScene(scene_number=1, scene_key=StorySceneKey.BEFORE, title="Before", narrative="T0"),
        StoryScene(
            scene_number=2, scene_key=StorySceneKey.THE_SHIFT, title="The Shift", narrative="Delta"
        ),
        StoryScene(
            scene_number=3,
            scene_key=StorySceneKey.INVESTIGATE,
            title="Investigate",
            narrative="Fingerprint",
            claims=[claim],
        ),
        StoryScene(
            scene_number=4,
            scene_key=StorySceneKey.WHAT_WE_KNOW,
            title="What We Know / What We Don't Know",
            narrative="Boundaries",
        ),
        StoryScene(
            scene_number=5,
            scene_key=StorySceneKey.EVIDENCE_STORY,
            title="Evidence Story",
            narrative="Summary",
            claims=[claim],
        ),
    ]
    story = EvidenceStory(
        story_id="STORY-001",
        title="When Fire Becomes Hard to See",
        aoi_id="AOI-A1",
        quality_status=ScienceQualityStatus.COMPARABLE,
        scenes=scenes,
        evidence_ledger_ids=["E-001"],
    )
    assert len(story.scenes) == 5
    assert story.scenes[2].claims[0].evidence_ids == ["E-001"]
