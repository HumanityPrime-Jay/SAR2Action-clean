"""Offline test suite for Workstream A: Autonomous Experimentation & Falsification."""
from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.advanced.experimentation import (
    BoundedInvestigationResult,
    EvidenceItem,
    ExperimentPlan,
    ExperimentResult,
    ExperimentStatus,
    FeasibilityStatus,
    HypothesisCategory,
    HypothesisStatus,
    InvestigationContext,
    ScientificToolRegistry,
    UnauthorizedToolError,
    build_v3_context,
    default_hypotheses,
    design_experiments,
    evaluate_experiment,
    execute_experiment,
    rank_experiments,
    revise_hypotheses,
    run_bounded_investigation,
    to_v3_adapter_payload,
)
from backend.app.advanced.experimentation.designer import compute_signature


class FakeModel:
    """Offline fake model for testing LLM-assisted experiment planning without Gemini."""

    def __init__(self, proposals: list[dict]):
        self._proposals = proposals

    def propose_experiments(self, context_dict: dict) -> list[dict]:
        return list(self._proposals)


class TestAutonomousExperimentation(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ScientificToolRegistry(data_root=ROOT)
        self.yl03_context = build_v3_context(field_id="YL-CAND-03", data_root=ROOT)

    def test_experiment_planning_with_fake_model_and_real_yl03(self) -> None:
        # 1. Deterministic planning on real YL-CAND-03 includes the three core experiments
        plans = design_experiments(self.yl03_context, tool_registry=self.registry)
        exp_types = {p.experiment_type for p in plans}
        self.assertTrue(
            {"temporal_alignment", "cross_field_comparison", "seasonal_reference"} <= exp_types
        )
        self.assertTrue(all(p.feasibility_status == FeasibilityStatus.EXECUTABLE for p in plans))

        # 2. FakeModel proposals still undergo deterministic validation
        fake = FakeModel([
            {
                "experiment_id": "EXP-FAKE-01",
                "experiment_type": "temporal_alignment",
                "hypothesis_id": "typhoon_surface_change",
                "objective": "Check temporal alignment with FakeModel proposal",
                "required_inputs": ["field_id"],
                "selected_tools": ["temporal_alignment_test"],
                "testable_prediction": "Pre-to-warning shift observed.",
                "falsification_criterion": "Single pre-warning point limits trend test.",
                "expected_evidence": ["OPERA VH timestamps"],
                "scientific_limitations": ["FakeModel test proposal"],
            }
        ])
        llm_plans = design_experiments(self.yl03_context, model=fake, tool_registry=self.registry)
        self.assertEqual(len(llm_plans), 1)
        self.assertEqual(llm_plans[0].experiment_id, "EXP-FAKE-01")
        self.assertEqual(llm_plans[0].feasibility_status, FeasibilityStatus.EXECUTABLE)

    def test_tool_whitelist_and_invalid_tool_rejection(self) -> None:
        self.assertIn("temporal_alignment_test", self.registry.whitelist)
        self.assertFalse(self.registry.is_whitelisted("exec('import os')"))
        self.assertFalse(self.registry.is_whitelisted("delete_database"))

        with self.assertRaises(UnauthorizedToolError):
            self.registry.execute("arbitrary_python_exec", {})

        bad_model = FakeModel([
            {
                "experiment_id": "EXP-BAD-TOOL",
                "experiment_type": "malicious",
                "hypothesis_id": "typhoon_surface_change",
                "selected_tools": ["subprocess.run('rm -rf /')"],
            }
        ])
        plans = design_experiments(self.yl03_context, model=bad_model, tool_registry=self.registry)
        self.assertEqual(plans[0].feasibility_status, FeasibilityStatus.BLOCKED_UNSAFE_TOOL)
        res = execute_experiment(plans[0], self.registry)
        self.assertEqual(res.status, ExperimentStatus.REJECTED)

    def test_hypothesis_falsification_and_epistemic_integrity(self) -> None:
        hyps = default_hypotheses()
        categories = {h.category for h in hyps}
        self.assertEqual(
            categories,
            {
                HypothesisCategory.TYPHOON_SURFACE_CHANGE,
                HypothesisCategory.AGRICULTURAL_HARVEST,
                HypothesisCategory.MOISTURE_VARIATION,
                HypothesisCategory.OBSERVATION_ARTIFACT,
                HypothesisCategory.INSUFFICIENT_EVIDENCE,
            },
        )
        # Every hypothesis must define the 6 required falsification fields
        for h in hyps:
            self.assertTrue(h.necessary_evidence)
            self.assertTrue(h.expected_observation)
            self.assertTrue(h.possible_contradiction)
            self.assertTrue(h.executable_tests or h.missing_tests)
            self.assertTrue(h.stop_conditions)

        # Run seasonal_reference_comparison on YL-CAND-03: 2025 also peaks mid-season.
        # Scientifically, a similar historical pattern is an Alternative Explanation, NOT a falsification.
        plans = design_experiments(self.yl03_context, tool_registry=self.registry)
        seasonal_plan = next(p for p in plans if p.experiment_type == "seasonal_reference")
        res = execute_experiment(seasonal_plan, self.registry)
        ev = evaluate_experiment(res, self.yl03_context.existing_evidence, self.yl03_context)
        self.assertFalse(ev.falsification_triggered)
        self.assertEqual(ev.verdict, "UNIQUENESS_CHALLENGED_NOT_FALSIFIED")
        self.assertEqual(ev.hypothesis_status_after, HypothesisStatus.UNRESOLVED)
        self.assertTrue(len(ev.alternative_explanations) >= 1)
        self.assertEqual(ev.direct_contradicting_evidence_ids, [])
        # Untested checks (e.g., parcel_ground_damage_survey) must remain in untested_checks
        self.assertIn("parcel_ground_damage_survey", ev.untested_checks)

        # Absence of refutation must NEVER confirm or support a hypothesis; test_outcomes stored separately
        revised = revise_hypotheses(self.yl03_context, [res], [ev])
        typhoon_h = next(h for h in revised if h.hypothesis_id == "typhoon_surface_change")
        self.assertEqual(typhoon_h.status, HypothesisStatus.UNRESOLVED)
        self.assertEqual(len(typhoon_h.test_outcomes), 1)
        self.assertEqual(typhoon_h.test_outcomes[0]["verdict"], "UNIQUENESS_CHALLENGED_NOT_FALSIFIED")
        for h in revised:
            self.assertNotIn(h.status, (HypothesisStatus.SUPPORTED, HypothesisStatus.CONTRADICTED))

    def test_evidence_integrity_and_json_serializable(self) -> None:
        result = run_bounded_investigation(self.yl03_context, tool_registry=self.registry)
        self.assertIsInstance(result, BoundedInvestigationResult)
        payload = to_v3_adapter_payload(result)
        serialized = json.dumps(payload, allow_nan=False)
        self.assertIn("YL-CAND-03", serialized)
        # Every evidence ID in executed experiments must be registered in evidence_ledger
        ledger_ids = {e.evidence_id for e in result.evidence_ledger}
        for exp in result.experiments_executed:
            self.assertTrue(set(exp.evidence_ids) <= ledger_ids)

    def test_missing_evidence_and_no_fabricated_results(self) -> None:
        # Unknown field ID must return MISSING_EVIDENCE and NEVER fabricate dB numbers
        missing_ctx = InvestigationContext(
            research_question="Check VH change on missing field",
            study_aoi="Taixi Township (10009160)",
            field_id="YL-CAND-999",
            observations=[],
        )
        out, _ = self.registry.execute("temporal_alignment_test", {"field_id": "YL-CAND-999"})
        self.assertEqual(out["status"], "MISSING_EVIDENCE")
        self.assertIsNone(out.get("pre_to_warning_window_db"))

        # Audit missing external crop/rainfall/ground evidence on YL-CAND-03
        audit_out, _ = self.registry.execute("missing_evidence_audit", {"field_id": "YL-CAND-03"})
        self.assertEqual(audit_out["status"], "MISSING_EVIDENCE")
        self.assertTrue(len(audit_out["missing_evidence"]) >= 3)

        # Bounded investigation on missing_ctx stops safely with MISSING_EVIDENCE
        missing_res = run_bounded_investigation(missing_ctx, tool_registry=self.registry)
        self.assertTrue(len(missing_res.missing_evidence) > 0)

    def test_real_yl_cand_03_observed_delta(self) -> None:
        out, _ = self.registry.execute("temporal_alignment_test", {"field_id": "YL-CAND-03"})
        self.assertEqual(out["status"], "OBSERVED")
        self.assertAlmostEqual(out["pre_to_warning_window_db"], 7.55336, places=3)

    def test_stop_conditions_max_3_experiments(self) -> None:
        result = run_bounded_investigation(self.yl03_context, tool_registry=self.registry)
        self.assertLessEqual(len(result.experiments_executed), 3)
        self.assertGreater(len(result.tool_trace), 0)
        for exp in result.experiments_executed:
            tool_calls = [t for t in exp.tool_trace if t.kind == "tool_call"]
            self.assertLessEqual(len(tool_calls), 5)

    def test_experiment_ranking_no_probability(self) -> None:
        plans = design_experiments(self.yl03_context, tool_registry=self.registry)
        ranked = rank_experiments(plans, self.yl03_context, tool_registry=self.registry)
        self.assertTrue(len(ranked) >= 3)
        for p in ranked:
            self.assertIsNotNone(p.score)
            self.assertFalse(p.score.is_statistical_probability)
            self.assertIn("relevance", p.score.rationale)
            self.assertIn("duplication_risk", p.score.rationale)
        # Scores must be descending for executable plans
        exec_scores = [p.score.total_priority_score for p in ranked if p.feasibility_status == FeasibilityStatus.EXECUTABLE]
        self.assertEqual(exec_scores, sorted(exec_scores, reverse=True))

    def test_duplicate_prevention(self) -> None:
        sig = compute_signature("temporal_alignment", "YL-CAND-03", ["temporal_alignment_test"], {"field_id": "YL-CAND-03"})
        ctx = InvestigationContext(
            research_question=self.yl03_context.research_question,
            study_aoi=self.yl03_context.study_aoi,
            field_id="YL-CAND-03",
            observations=self.yl03_context.observations,
            executed_experiment_signatures=[sig],
        )
        plans = design_experiments(ctx, tool_registry=self.registry)
        dup = next(p for p in plans if p.experiment_type == "temporal_alignment")
        self.assertEqual(dup.feasibility_status, FeasibilityStatus.DUPLICATE_EXPERIMENT)
        ranked = rank_experiments(plans, ctx, tool_registry=self.registry)
        dup_ranked = next(p for p in ranked if p.experiment_type == "temporal_alignment")
        self.assertGreater(dup_ranked.score.duplication_risk_penalty, 0.0)

    def test_timeout_handling(self) -> None:
        def slow_tool(**kwargs):
            time.sleep(0.5)
            return {"status": "OBSERVED", "evidence_ids": []}

        slow_reg = ScientificToolRegistry(
            data_root=ROOT,
            custom_handlers={"temporal_alignment_test": slow_tool},
        )
        plans = design_experiments(self.yl03_context, tool_registry=slow_reg)
        temporal = next(p for p in plans if p.experiment_type == "temporal_alignment")
        res = execute_experiment(temporal, slow_reg, timeout_seconds=0.05)
        self.assertEqual(res.status, ExperimentStatus.TIMED_OUT)
        self.assertTrue(res.timed_out)

    def test_deterministic_replay(self) -> None:
        res1 = run_bounded_investigation(self.yl03_context, tool_registry=self.registry)
        res2 = run_bounded_investigation(self.yl03_context, tool_registry=self.registry)
        self.assertEqual(res1.investigation_id, res2.investigation_id)
        self.assertEqual(
            [e.experiment_id for e in res1.experiments_executed],
            [e.experiment_id for e in res2.experiments_executed],
        )
        self.assertEqual(
            [(h.hypothesis_id, h.status.value) for h in res1.revised_hypotheses],
            [(h.hypothesis_id, h.status.value) for h in res2.revised_hypotheses],
        )

    def test_similar_historical_pattern_does_not_falsify_typhoon_real_yl03(self) -> None:
        """Real YL-CAND-03: 2025 seasonal peak/decline is an alternative explanation, not CONTRADICTED."""
        result = run_bounded_investigation(self.yl03_context, tool_registry=self.registry)
        typhoon_h = next(h for h in result.revised_hypotheses if h.hypothesis_id == "typhoon_surface_change")
        self.assertNotEqual(typhoon_h.status, HypothesisStatus.CONTRADICTED)
        self.assertEqual(typhoon_h.direct_contradicting_evidence_ids, [])
        self.assertTrue(len(typhoon_h.alternative_explanations) >= 1)
        self.assertTrue(len(typhoon_h.observed_measurements) >= 1)

    def test_missing_ground_truth_cannot_confirm_crop_damage_real_yl03(self) -> None:
        """Real YL-CAND-03: without parcel ground truth, crop_damage_confirmed must remain False."""
        result = run_bounded_investigation(self.yl03_context, tool_registry=self.registry)
        self.assertFalse(result.crop_damage_confirmed)
        self.assertFalse(to_v3_adapter_payload(result)["crop_damage_confirmed"])
        for h in result.revised_hypotheses:
            self.assertNotEqual(h.status, HypothesisStatus.SUPPORTED)

    def test_non_discriminating_test_never_promotes_to_supported_synthetic(self) -> None:
        """Synthetic test: a non-discriminating test must never promote a hypothesis to SUPPORTED."""
        syn_result = ExperimentResult(
            experiment_id="EXP-SYN-NONDISC",
            experiment_type="cross_field_comparison",
            hypothesis_id="agricultural_harvest",
            status=ExperimentStatus.EXECUTED,
            outputs={
                "cross_field_comparison": {
                    "status": "OBSERVED",
                    "field_id": "YL-CAND-03",
                    "qa_passed": True,
                    "pre_to_warning_increase_count": 4,
                    "field_count": 5,
                }
            },
            evidence_ids=["E-SYN-01"],
        )
        ev = evaluate_experiment(syn_result, [EvidenceItem("E-SYN-01", "synthetic", "test")], self.yl03_context)
        self.assertFalse(ev.discriminating)
        self.assertNotEqual(ev.hypothesis_status_after, HypothesisStatus.SUPPORTED)

    def test_failed_qa_prevents_scientific_conclusion_promotion_synthetic(self) -> None:
        """Synthetic test: qa_passed=False blocks CONTRADICTED/SUPPORTED even if contradiction flag is set."""
        syn_result = ExperimentResult(
            experiment_id="EXP-SYN-QA-FAIL",
            experiment_type="temporal_alignment",
            hypothesis_id="typhoon_surface_change",
            status=ExperimentStatus.EXECUTED,
            outputs={
                "temporal_alignment_test": {
                    "status": "OBSERVED",
                    "field_id": "YL-CAND-03",
                    "qa_passed": False,
                    "direct_contradiction_detected": True,
                    "evidence_ids": ["E-SYN-QA-BAD"],
                }
            },
            evidence_ids=["E-SYN-QA-BAD"],
        )
        ev = evaluate_experiment(syn_result, [EvidenceItem("E-SYN-QA-BAD", "synthetic", "bad qa")], self.yl03_context)
        self.assertFalse(ev.qa_passed)
        self.assertEqual(ev.verdict, "QA_FAILED")
        self.assertFalse(ev.falsification_triggered)
        self.assertNotIn(ev.hypothesis_status_after, (HypothesisStatus.SUPPORTED, HypothesisStatus.CONTRADICTED))

    def test_direct_contradiction_with_qa_passed_synthetic(self) -> None:
        """Synthetic test: ONLY QA-passed direct contradicting evidence can set CONTRADICTED."""
        syn_result = ExperimentResult(
            experiment_id="EXP-SYN-CONTRA",
            experiment_type="temporal_alignment",
            hypothesis_id="typhoon_surface_change",
            status=ExperimentStatus.EXECUTED,
            outputs={
                "temporal_alignment_test": {
                    "status": "OBSERVED",
                    "field_id": "YL-CAND-03",
                    "qa_passed": True,
                    "direct_contradiction_detected": True,
                    "evidence_ids": ["E-SYN-CONTRA-01"],
                }
            },
            evidence_ids=["E-SYN-CONTRA-01"],
        )
        ev = evaluate_experiment(syn_result, [EvidenceItem("E-SYN-CONTRA-01", "synthetic", "direct contra")], self.yl03_context)
        self.assertTrue(ev.qa_passed)
        self.assertTrue(ev.falsification_triggered)
        self.assertEqual(ev.verdict, "DIRECT_CONTRADICTION")
        self.assertEqual(ev.hypothesis_status_after, HypothesisStatus.CONTRADICTED)
        self.assertEqual(ev.direct_contradicting_evidence_ids, ["E-SYN-CONTRA-01"])


if __name__ == "__main__":
    unittest.main()
