"""Hypothesis-specific falsification strategies and strict epistemic evaluation."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from backend.app.advanced.experimentation.models import (
    EvidenceItem,
    ExperimentEvaluation,
    ExperimentResult,
    ExperimentStatus,
    HypothesisCategory,
    HypothesisState,
    HypothesisStatus,
)


def default_hypotheses() -> list[HypothesisState]:
    """Build the five canonical SAR2Action competing hypotheses with falsification specs."""
    return [
        HypothesisState(
            hypothesis_id="typhoon_surface_change",
            category=HypothesisCategory.TYPHOON_SURFACE_CHANGE,
            statement="Typhoon CHAMPI altered vegetation structure or surface conditions in the candidate field.",
            necessary_evidence=[
                "Event-aligned SAR acquisition bracketing the typhoon warning window",
                "Spatial consistency or anomaly relative to non-impacted reference fields",
                "Parcel-level ground survey or cloud-free optical confirmation of storm disturbance",
            ],
            expected_observation="Post-warning or warning-window backscatter shift consistent with storm exposure.",
            possible_contradiction=(
                "Verified QA-passed observations showing zero surface change during/after the storm, "
                "or verified ground survey confirming intact, undisturbed crop canopy."
            ),
            executable_tests=[
                "temporal_alignment_test",
                "cross_field_comparison",
                "seasonal_reference_comparison",
                "official_loss_scope_check",
            ],
            missing_tests=[
                "parcel_ground_damage_survey",
                "cloud_free_optical_damage_check",
            ],
            stop_conditions=[
                "All executable temporal, cross-field, and seasonal tests completed without parcel ground truth",
                "Necessary external ground/optical evidence is missing",
            ],
            untested_checks=[
                "temporal_alignment_test",
                "cross_field_comparison",
                "seasonal_reference_comparison",
                "official_loss_scope_check",
                "parcel_ground_damage_survey",
                "cloud_free_optical_damage_check",
            ],
        ),
        HypothesisState(
            hypothesis_id="agricultural_harvest",
            category=HypothesisCategory.AGRICULTURAL_HARVEST,
            statement="Routine agricultural harvest or field management caused the observed VH change.",
            necessary_evidence=[
                "Parcel-level crop type, planting, and harvest calendar records",
                "Cross-field heterogeneity consistent with staggered field management",
                "Seasonal phenology comparison against 2025 same-orbit acquisitions",
            ],
            expected_observation="Field-specific backscatter shifts aligned with harvest/tillage dates rather than uniform storm timing.",
            possible_contradiction=(
                "Verified parcel management log confirming fallow or unmanaged status with no field operations during the window."
            ),
            executable_tests=[
                "cross_field_comparison",
                "seasonal_reference_comparison",
                "missing_evidence_audit",
            ],
            missing_tests=[
                "crop_calendar_verification",
                "farmer_or_co_op_harvest_log",
            ],
            stop_conditions=[
                "Crop and harvest records are unavailable (MISSING_EVIDENCE)",
            ],
            untested_checks=[
                "cross_field_comparison",
                "seasonal_reference_comparison",
                "missing_evidence_audit",
                "crop_calendar_verification",
                "farmer_or_co_op_harvest_log",
            ],
        ),
        HypothesisState(
            hypothesis_id="moisture_variation",
            category=HypothesisCategory.MOISTURE_VARIATION,
            statement="Surface soil moisture, standing water, or rainfall variation altered VH backscatter.",
            necessary_evidence=[
                "In-situ or high-resolution rainfall and soil moisture time series",
                "Temporal alignment between precipitation peaks and VH increase (+7.553 dB)",
                "Cross-field spatial coherence across nearby parcels",
            ],
            expected_observation="Transient VH increase during wet/warning period followed by post-event drainage decline.",
            possible_contradiction=(
                "Verified meteorological and soil-moisture records showing zero precipitation and dry surface conditions."
            ),
            executable_tests=[
                "temporal_alignment_test",
                "cross_field_comparison",
                "missing_evidence_audit",
            ],
            missing_tests=[
                "rainfall_gauge_correlation",
                "soil_moisture_ancillary_check",
            ],
            stop_conditions=[
                "Rainfall and soil moisture records are unavailable (MISSING_EVIDENCE)",
            ],
            untested_checks=[
                "temporal_alignment_test",
                "cross_field_comparison",
                "missing_evidence_audit",
                "rainfall_gauge_correlation",
                "soil_moisture_ancillary_check",
            ],
        ),
        HypothesisState(
            hypothesis_id="observation_artifact",
            category=HypothesisCategory.OBSERVATION_ARTIFACT,
            statement="Processing version (CRID), incidence angle, or sensor geometry differences explain the observed change.",
            necessary_evidence=[
                "NISAR cross-CRID compatibility check (P05023 vs P05036)",
                "OPERA Sentinel-1 orbit/track/product-version/platform consistency check",
            ],
            expected_observation="Mismatched CRID, orbit, platform, or processing conventions coinciding with apparent backscatter shifts.",
            possible_contradiction=(
                "Same-platform, same-orbit, same-CRID, QA-passed acquisitions with verified incidence-angle normalization "
                "show zero processing discrepancy."
            ),
            executable_tests=[
                "cross_crid_compatibility_test",
                "seasonal_reference_comparison",
            ],
            missing_tests=[
                "reprocessed_same_crid_nisar_comparison",
                "local_incidence_angle_normalization_check",
            ],
            stop_conditions=[
                "Cross-CRID NISAR delta remains blocked until same-CRID reprocessing",
            ],
            untested_checks=[
                "cross_crid_compatibility_test",
                "seasonal_reference_comparison",
                "reprocessed_same_crid_nisar_comparison",
                "local_incidence_angle_normalization_check",
            ],
        ),
        HypothesisState(
            hypothesis_id="insufficient_evidence",
            category=HypothesisCategory.INSUFFICIENT_EVIDENCE,
            statement="Current evidence is insufficient to attribute the observed SAR change to a single causal mechanism.",
            necessary_evidence=[
                "Audit of missing crop, rainfall, soil moisture, and ground-truth records",
            ],
            expected_observation="Critical causal discriminators remain unobserved or blocked by QA gates.",
            possible_contradiction=(
                "All necessary parcel-level crop, moisture, and ground-truth records are present and QA-verified."
            ),
            executable_tests=[
                "missing_evidence_audit",
            ],
            missing_tests=[],
            stop_conditions=[
                "Missing evidence audit confirms required external records are absent",
            ],
            untested_checks=[
                "missing_evidence_audit",
            ],
        ),
    ]


def _extract_observed_measurements(outputs: dict[str, Any]) -> list[dict[str, Any]]:
    measurements: list[dict[str, Any]] = []
    for tool_name, payload in outputs.items():
        if not isinstance(payload, dict) or payload.get("status") != "OBSERVED":
            continue
        if "pre_to_warning_window_db" in payload and payload["pre_to_warning_window_db"] is not None:
            measurements.append({
                "tool": tool_name,
                "field_id": payload.get("field_id"),
                "metric": "pre_to_warning_window_db",
                "value": payload["pre_to_warning_window_db"],
                "unit": "dB",
            })
        if "early_to_middle_2025_db" in payload and payload["early_to_middle_2025_db"] is not None:
            measurements.append({
                "tool": tool_name,
                "field_id": payload.get("field_id"),
                "metric": "early_to_middle_2025_db",
                "value": payload["early_to_middle_2025_db"],
                "unit": "dB",
            })
        if "pre_to_warning_increase_count" in payload and payload["pre_to_warning_increase_count"] is not None:
            measurements.append({
                "tool": tool_name,
                "field_id": payload.get("field_id"),
                "metric": "pre_to_warning_increase_count",
                "value": payload["pre_to_warning_increase_count"],
                "field_count": payload.get("field_count"),
            })
    return measurements


def evaluate_experiment_against_hypothesis(
    result: ExperimentResult,
    hypothesis: HypothesisState,
    evidence_ledger: list[EvidenceItem],
) -> ExperimentEvaluation:
    """Deterministically evaluate an experiment result against a hypothesis's falsification rules.

    Epistemic rules:
    1. Separate Observed Measurement, Supporting Evidence, Alternative Explanation,
       Direct Contradicting Evidence, and Missing Evidence.
    2. Store per-experiment test outcomes separately from overall HypothesisState.status.
    3. Similar historical patterns are Alternative Explanations, NOT Direct Contradicting
       Evidence—they challenge uniqueness, NOT causal possibility.
    4. Only explicit, testable predictions violated by QA-passed direct contradicting evidence
       can set HypothesisStatus.CONTRADICTED.
    5. Failed quality checks (qa_passed == False) prevent any scientific conclusion promotion.
    6. Non-discriminating tests and absence of refutation NEVER promote a hypothesis to SUPPORTED.
    7. Missing ground truth NEVER confirms crop damage.
    """
    if result.status in (ExperimentStatus.FAILED, ExperimentStatus.TIMED_OUT, ExperimentStatus.REJECTED):
        return ExperimentEvaluation(
            experiment_id=result.experiment_id,
            hypothesis_id=hypothesis.hypothesis_id,
            verdict="FAILED",
            falsification_triggered=False,
            qa_passed=False,
            discriminating=False,
            observed_measurements=[],
            supporting_evidence_ids=[],
            alternative_explanations=[],
            direct_contradicting_evidence_ids=[],
            missing_evidence=list(result.missing_evidence),
            executed_tests=[],
            untested_checks=list(hypothesis.untested_checks),
            hypothesis_status_after=hypothesis.status,
            rationale=f"Experiment did not complete ({result.status.value}); hypothesis remains unchanged.",
            limitations=["Incomplete or failed tool execution cannot falsify or support any hypothesis."],
        )

    executed_tool_names = [
        entry.tool for entry in result.tool_trace if entry.kind == "tool_result" and entry.status != "FAILED"
    ]
    outputs = result.outputs
    observed_measurements = _extract_observed_measurements(outputs)
    supporting_ids: list[str] = []
    alternative_explanations: list[str] = []
    direct_contradicting_ids: list[str] = []
    missing = list(result.missing_evidence)
    limitations: list[str] = []

    # Check QA gate across all tool outputs
    qa_flags = [
        payload.get("qa_passed")
        for payload in outputs.values()
        if isinstance(payload, dict) and "qa_passed" in payload
    ]
    qa_passed = all(flag is True for flag in qa_flags) if qa_flags else True

    if not qa_passed:
        limitations.append("One or more tool outputs failed data quality checks (qa_passed=False); conclusion promotion blocked.")

    # Check if experiment returned MISSING_EVIDENCE
    has_missing_status = result.status == ExperimentStatus.MISSING_EVIDENCE or any(
        isinstance(v, dict) and v.get("status") == "MISSING_EVIDENCE" for v in outputs.values()
    )
    if has_missing_status:
        for v in outputs.values():
            if isinstance(v, dict):
                missing.extend(v.get("missing_evidence", []))
        missing = list(dict.fromkeys(missing))

    falsification_triggered = False
    discriminating = False
    verdict = "NON_DISCRIMINATING"
    next_status = hypothesis.status
    rationale_parts: list[str] = []

    if not qa_passed:
        verdict = "QA_FAILED"
        next_status = hypothesis.status if hypothesis.status != HypothesisStatus.SUPPORTED else HypothesisStatus.UNRESOLVED
        rationale_parts.append("Quality assurance checks failed; cannot promote or falsify hypothesis.")

    elif has_missing_status:
        verdict = "MISSING_EVIDENCE"
        if hypothesis.category == HypothesisCategory.INSUFFICIENT_EVIDENCE:
            next_status = HypothesisStatus.PLAUSIBLE_UNCONFIRMED
            rationale_parts.append(
                "Missing evidence audit confirmed required crop, rainfall, and ground-truth records are absent."
            )
        else:
            next_status = HypothesisStatus.INSUFFICIENT_EVIDENCE
            rationale_parts.append(
                "Required external or observational data is missing; cannot falsify or confirm."
            )

    elif hypothesis.category == HypothesisCategory.TYPHOON_SURFACE_CHANGE:
        seasonal = outputs.get("seasonal_reference_comparison", {})
        temporal = outputs.get("temporal_alignment_test", {})
        cross_field = outputs.get("cross_field_comparison", {})

        # Explicit direct contradiction check (only if QA passed and direct contradicting evidence exists)
        if temporal.get("direct_contradiction_detected") and qa_passed:
            falsification_triggered = True
            discriminating = True
            verdict = "DIRECT_CONTRADICTION"
            next_status = HypothesisStatus.CONTRADICTED
            direct_contradicting_ids.extend(temporal.get("evidence_ids", []))
            rationale_parts.append("QA-passed direct contradicting evidence violated the typhoon timing prediction.")
        else:
            if seasonal.get("uniqueness_claim_challenged"):
                # Scientific correction: 2025 similar peak/decline is an Alternative Explanation,
                # NOT direct contradicting evidence against typhoon surface change.
                verdict = "UNIQUENESS_CHALLENGED_NOT_FALSIFIED"
                alternative_explanations.append(
                    "2025 same-orbit observations also exhibit a mid-season VH peak followed by decline "
                    f"({seasonal.get('early_to_middle_2025_db')} dB vs {seasonal.get('early_to_middle_2026_db')} dB in 2026); "
                    "this provides an alternative seasonal phenology explanation and challenges uniqueness, "
                    "but does NOT falsify typhoon-related surface change."
                )
                rationale_parts.append(
                    "Similar 2025 historical pattern recorded as an alternative explanation; "
                    "typhoon hypothesis is NOT contradicted and remains UNRESOLVED pending ground truth."
                )
            if temporal.get("status") == "OBSERVED":
                delta = temporal.get("pre_to_warning_window_db")
                if delta is not None:
                    rationale_parts.append(
                        f"Observed pre-to-warning VH shift of {delta} dB is consistent with storm timing "
                        "but non-discriminating without a multi-point pre-warning trend or ground truth."
                    )
                    limitations.append("Only one 2026 acquisition precedes the typhoon land warning.")
            if cross_field.get("status") == "OBSERVED":
                inc_count = cross_field.get("pre_to_warning_increase_count")
                field_count = cross_field.get("field_count")
                alternative_explanations.append(
                    f"Cross-field comparison shows {inc_count}/{field_count} fields increased into the warning window; "
                    "shared temporal signal may reflect regional moisture or synchronized phenology."
                )
                rationale_parts.append(
                    "Cross-field signal is non-discriminating between storm disturbance and regional moisture/phenology."
                )
            # Without parcel ground truth, cannot promote to SUPPORTED
            if next_status == HypothesisStatus.SUPPORTED:
                next_status = HypothesisStatus.UNRESOLVED

    elif hypothesis.category == HypothesisCategory.OBSERVATION_ARTIFACT:
        crid = outputs.get("cross_crid_compatibility_test", {})
        seasonal = outputs.get("seasonal_reference_comparison", {})
        if crid and crid.get("crid_match") is False:
            verdict = "QA_FAILED"
            alternative_explanations.append(
                "NISAR pre/post scenes have mismatched CRIDs (P05023 vs P05036); cross-CRID delta is blocked."
            )
            rationale_parts.append("NISAR cross-CRID QA failed; processing artifact cannot be ruled out for NISAR.")
        elif seasonal.get("status") == "OBSERVED":
            verdict = "NON_DISCRIMINATING"
            alternative_explanations.append(
                "OPERA Sentinel-1 uses consistent orbit/product-version conventions, yet cross-platform "
                "(S1A/S1C) incidence-angle normalization remains untested."
            )
            rationale_parts.append(
                "Same-orbit S1 convention weakens pure version-artifact explanation, but untested platform/incidence checks prevent CONTRADICTED."
            )

    elif hypothesis.category in (HypothesisCategory.AGRICULTURAL_HARVEST, HypothesisCategory.MOISTURE_VARIATION):
        verdict = "NON_DISCRIMINATING"
        rationale_parts.append(
            "Observed SAR backscatter alone is non-discriminating without parcel crop/harvest or rainfall/soil moisture records."
        )

    # Never mark untested checks as passed
    remaining_untested = [c for c in hypothesis.untested_checks if c not in executed_tool_names]

    # Strict rule: non-discriminating or failed-QA tests can NEVER promote to SUPPORTED
    if (not discriminating or not qa_passed) and next_status == HypothesisStatus.SUPPORTED:
        next_status = HypothesisStatus.UNRESOLVED

    if not rationale_parts:
        rationale_parts.append("Executed checks are non-discriminating; absence of refutation is not confirmation.")

    return ExperimentEvaluation(
        experiment_id=result.experiment_id,
        hypothesis_id=hypothesis.hypothesis_id,
        verdict=verdict,
        falsification_triggered=falsification_triggered,
        qa_passed=qa_passed,
        discriminating=discriminating,
        observed_measurements=observed_measurements,
        supporting_evidence_ids=list(dict.fromkeys(supporting_ids)),
        alternative_explanations=list(dict.fromkeys(alternative_explanations)),
        direct_contradicting_evidence_ids=list(dict.fromkeys(direct_contradicting_ids)),
        missing_evidence=list(dict.fromkeys(missing)),
        executed_tests=executed_tool_names,
        untested_checks=remaining_untested,
        hypothesis_status_after=next_status,
        rationale=" ".join(rationale_parts),
        limitations=limitations,
    )


def apply_evaluations_to_hypotheses(
    hypotheses: list[HypothesisState],
    evaluations: list[ExperimentEvaluation],
    results: list[ExperimentResult],
) -> list[HypothesisState]:
    """Return revised HypothesisState objects, keeping test outcomes separate from overall status."""
    del results  # Evaluations carry verified evidence IDs and QA status
    revised: list[HypothesisState] = []
    for hyp in hypotheses:
        matching_evals = [e for e in evaluations if e.hypothesis_id == hyp.hypothesis_id]
        if not matching_evals:
            revised.append(replace(hyp))
            continue

        new_executed = list(hyp.executed_tests)
        new_untested = list(hyp.untested_checks)
        new_observed = list(hyp.observed_measurements)
        new_supporting = list(hyp.supporting_evidence_ids)
        new_alternatives = list(hyp.alternative_explanations)
        new_contra = list(hyp.direct_contradicting_evidence_ids)
        new_missing = list(hyp.missing_evidence)
        new_outcomes = list(hyp.test_outcomes)
        new_notes = list(hyp.notes)
        status = hyp.status

        for ev in matching_evals:
            for t in ev.executed_tests:
                if t not in new_executed:
                    new_executed.append(t)
                if t in new_untested:
                    new_untested.remove(t)

            new_observed.extend(ev.observed_measurements)
            for eid in ev.supporting_evidence_ids:
                if eid not in new_supporting:
                    new_supporting.append(eid)
            for alt in ev.alternative_explanations:
                if alt not in new_alternatives:
                    new_alternatives.append(alt)
            for eid in ev.direct_contradicting_evidence_ids:
                if eid not in new_contra:
                    new_contra.append(eid)
            for m in ev.missing_evidence:
                if m not in new_missing:
                    new_missing.append(m)

            # Store experiment test outcome separately from overall hypothesis status
            new_outcomes.append({
                "experiment_id": ev.experiment_id,
                "verdict": ev.verdict,
                "qa_passed": ev.qa_passed,
                "discriminating": ev.discriminating,
                "falsification_triggered": ev.falsification_triggered,
                "executed_tests": list(ev.executed_tests),
                "rationale": ev.rationale,
            })

            # Deterministic status transition guard
            if not ev.qa_passed:
                # Failed QA prevents promotion
                status = hyp.status if hyp.status != HypothesisStatus.SUPPORTED else HypothesisStatus.UNRESOLVED
            elif ev.hypothesis_status_after == HypothesisStatus.SUPPORTED and not ev.discriminating:
                status = HypothesisStatus.UNRESOLVED
            elif ev.hypothesis_status_after == HypothesisStatus.CONTRADICTED and not (ev.falsification_triggered and ev.direct_contradicting_evidence_ids):
                status = HypothesisStatus.UNRESOLVED
            else:
                status = ev.hypothesis_status_after

            new_notes.append(f"[{ev.experiment_id}] {ev.verdict}: {ev.rationale}")

        revised.append(
            replace(
                hyp,
                status=status,
                observed_measurements=new_observed,
                supporting_evidence_ids=new_supporting,
                alternative_explanations=new_alternatives,
                direct_contradicting_evidence_ids=new_contra,
                missing_evidence=new_missing,
                test_outcomes=new_outcomes,
                executed_tests=new_executed,
                untested_checks=new_untested,
                notes=new_notes,
            )
        )
    return revised
