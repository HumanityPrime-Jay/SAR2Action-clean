"""Whitelisted, read-only deterministic scientific tool registry.

Wraps verified SAR2Action V3 data artifacts and deterministic checks without
modifying V3 services or allowing arbitrary code execution.
"""
from __future__ import annotations

import concurrent.futures
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from backend.app.advanced.experimentation.models import ToolSpec, ToolTraceEntry

ROOT = Path(__file__).resolve().parents[4]
VH_DIR = ROOT / "data" / "exports" / "yunlin_vh_2025_2026"
CHAMPI_DIR = ROOT / "data" / "exports" / "typhoon_champi"

EVENT_START = "2026-10-22T11:30:00+08:00"
EVENT_END = "2026-10-24T14:30:00+08:00"

FORBIDDEN_PATTERNS = ("exec(", "eval(", "__import__", "subprocess", "os.system", "open(", "write(")


class UnauthorizedToolError(ValueError):
    """Raised when a tool is not on the read-only scientific whitelist."""


class ToolExecutionTimeoutError(TimeoutError):
    """Raised when a tool exceeds its bounded execution timeout."""


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


class ScientificToolRegistry:
    """Strict whitelist registry for read-only scientific experimentation tools."""

    def __init__(self, data_root: Path | None = None, custom_handlers: dict[str, Callable[..., dict[str, Any]]] | None = None):
        self._root = data_root or ROOT
        self._vh_dir = self._root / "data" / "exports" / "yunlin_vh_2025_2026"
        self._champi_dir = self._root / "data" / "exports" / "typhoon_champi"
        self._specs: dict[str, ToolSpec] = {
            "temporal_alignment_test": ToolSpec(
                name="temporal_alignment_test",
                description="Check pre-warning, warning-window, and post-warning SAR acquisition alignment and observed delta.",
                required_inputs=["field_id", "vh_timeseries_or_comparison"],
                read_only=True,
                estimated_cost=1.0,
                source_types=["OPERA_RTC_S1", "NISAR_QA"],
            ),
            "cross_field_comparison": ToolSpec(
                name="cross_field_comparison",
                description="Compare target field VH trajectory against the five official farmland candidates.",
                required_inputs=["field_id", "field_comparison"],
                read_only=True,
                estimated_cost=1.2,
                source_types=["OPERA_RTC_S1"],
            ),
            "seasonal_reference_comparison": ToolSpec(
                name="seasonal_reference_comparison",
                description="Compare 2026 VH backscatter trajectory against matched 2025 same-orbit observations.",
                required_inputs=["field_id", "field_comparison"],
                read_only=True,
                estimated_cost=1.1,
                source_types=["OPERA_RTC_S1"],
            ),
            "cross_crid_compatibility_test": ToolSpec(
                name="cross_crid_compatibility_test",
                description="Apply deterministic NISAR cross-CRID radiometric compatibility gate (P05023 vs P05036).",
                required_inputs=["science_qa"],
                read_only=True,
                estimated_cost=0.5,
                source_types=["NISAR_QA"],
            ),
            "official_loss_scope_check": ToolSpec(
                name="official_loss_scope_check",
                description="Verify official Ministry of Agriculture loss scope (county vs parcel).",
                required_inputs=["official_loss_record"],
                read_only=True,
                estimated_cost=0.4,
                source_types=["MOA_OFFICIAL"],
            ),
            "missing_evidence_audit": ToolSpec(
                name="missing_evidence_audit",
                description="Audit missing parcel crop records, rainfall/soil moisture, and ground survey data.",
                required_inputs=["field_id"],
                read_only=True,
                estimated_cost=0.5,
                source_types=["EVIDENCE_LEDGER"],
            ),
        }
        self._handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "temporal_alignment_test": self._run_temporal_alignment_test,
            "cross_field_comparison": self._run_cross_field_comparison,
            "seasonal_reference_comparison": self._run_seasonal_reference_comparison,
            "cross_crid_compatibility_test": self._run_cross_crid_compatibility_test,
            "official_loss_scope_check": self._run_official_loss_scope_check,
            "missing_evidence_audit": self._run_missing_evidence_audit,
        }
        if custom_handlers:
            for name, fn in custom_handlers.items():
                if name in self._specs:
                    self._handlers[name] = fn

    @property
    def whitelist(self) -> set[str]:
        return set(self._specs.keys())

    def list_tools(self) -> list[ToolSpec]:
        return [self._specs[k] for k in sorted(self._specs)]

    def get_spec(self, tool_name: str) -> ToolSpec:
        if not self.is_whitelisted(tool_name):
            raise UnauthorizedToolError(f"Tool '{tool_name}' is not in the read-only scientific whitelist.")
        return self._specs[tool_name]

    def is_whitelisted(self, tool_name: str) -> bool:
        if not isinstance(tool_name, str) or not tool_name:
            return False
        lowered = tool_name.lower()
        if any(pat in lowered for pat in FORBIDDEN_PATTERNS):
            return False
        return tool_name in self._specs and self._specs[tool_name].read_only

    def execute(
        self,
        tool_name: str,
        params: dict[str, Any] | None = None,
        *,
        timeout_seconds: float = 10.0,
        experiment_id: str | None = None,
        step_index: int = 1,
    ) -> tuple[dict[str, Any], list[ToolTraceEntry]]:
        if not self.is_whitelisted(tool_name):
            raise UnauthorizedToolError(f"Rejected unauthorized or non-read-only tool: {tool_name!r}")
        params = dict(params or {})
        trace: list[ToolTraceEntry] = [
            ToolTraceEntry(
                step=step_index,
                timestamp_utc=_now_utc(),
                kind="tool_call",
                tool=tool_name,
                status="executed",
                experiment_id=experiment_id,
                source_references=[],
                detail={"params": params},
            )
        ]
        handler = self._handlers[tool_name]
        started = time.perf_counter()
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = pool.submit(handler, **params)
        try:
            output = future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            trace.append(
                ToolTraceEntry(
                    step=step_index + 1,
                    timestamp_utc=_now_utc(),
                    kind="tool_result",
                    tool=tool_name,
                    status="TIMED_OUT",
                    experiment_id=experiment_id,
                    source_references=[],
                    duration_ms=duration_ms,
                    detail={"timeout_seconds": timeout_seconds},
                )
            )
            pool.shutdown(wait=False, cancel_futures=True)
            raise ToolExecutionTimeoutError(f"Tool '{tool_name}' timed out after {timeout_seconds}s")
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            trace.append(
                ToolTraceEntry(
                    step=step_index + 1,
                    timestamp_utc=_now_utc(),
                    kind="tool_result",
                    tool=tool_name,
                    status="FAILED",
                    experiment_id=experiment_id,
                    source_references=[],
                    duration_ms=duration_ms,
                    detail={"error": str(exc)},
                )
            )
            pool.shutdown(wait=False)
            raise
        else:
            pool.shutdown(wait=True)

        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        refs = list(output.get("source_references", []))
        status = str(output.get("status", "COMPLETE"))
        trace.append(
            ToolTraceEntry(
                step=step_index + 1,
                timestamp_utc=_now_utc(),
                kind="tool_result",
                tool=tool_name,
                status=status,
                experiment_id=experiment_id,
                source_references=refs,
                duration_ms=duration_ms,
                detail={"evidence_ids": output.get("evidence_ids", [])},
            )
        )
        return output, trace

    def _load_field_comparison(self) -> dict[str, Any] | None:
        return _load_json(self._vh_dir / "field_comparison.json")

    def _run_temporal_alignment_test(self, field_id: str = "YL-CAND-03", **_: Any) -> dict[str, Any]:
        comp = self._load_field_comparison()
        if not comp:
            return {
                "status": "MISSING_EVIDENCE",
                "field_id": field_id,
                "missing_evidence": ["field_comparison.json (verified OPERA VH comparison)"],
                "evidence_ids": [],
                "source_references": [],
            }
        field_entry = next((f for f in comp.get("fields", []) if f.get("field_id") == field_id), None)
        if field_entry is None:
            return {
                "status": "MISSING_EVIDENCE",
                "field_id": field_id,
                "missing_evidence": [f"Observed VH series for field {field_id}"],
                "evidence_ids": [],
                "source_references": ["data/exports/yunlin_vh_2025_2026/field_comparison.json"],
            }
        obs_2026 = field_entry.get("observations", {}).get("2026", [])
        pre_warning = [o for o in obs_2026 if o.get("warning_relation") == "PRE_WARNING"]
        warning = [o for o in obs_2026 if o.get("warning_relation") == "WARNING_WINDOW"]
        post_warning = [o for o in obs_2026 if o.get("warning_relation") == "POST_WARNING"]
        pre_to_warn = field_entry.get("2026_pre_to_warning_window") or {}
        warn_to_post = field_entry.get("2026_warning_to_post_warning") or {}
        pre_to_post = field_entry.get("2026_pre_to_post_warning") or {}
        ev_ids = [o["evidence_id"] for o in obs_2026 if o.get("evidence_id")]
        spatial_assessment = (field_entry.get("spatial_support") or {}).get("assessment", "")
        qa_passed = spatial_assessment.startswith("PASS") and len(obs_2026) > 0
        return {
            "status": "OBSERVED",
            "field_id": field_id,
            "qa_passed": qa_passed,
            "event_window_local": [EVENT_START, EVENT_END],
            "pre_warning_count": len(pre_warning),
            "warning_window_count": len(warning),
            "post_warning_count": len(post_warning),
            "strict_pre_warning_trend_available": len(pre_warning) >= 2,
            "pre_to_warning_window_db": pre_to_warn.get("median_difference_db"),
            "warning_to_post_warning_db": warn_to_post.get("median_difference_db"),
            "pre_to_post_warning_db": pre_to_post.get("median_difference_db"),
            "warning_window_acquisition_taiwan": warning[0].get("acquisition_taiwan") if warning else None,
            "causal_attribution": "UNKNOWN",
            "evidence_ids": ev_ids,
            "source_references": ["data/exports/yunlin_vh_2025_2026/field_comparison.json"],
        }

    def _run_cross_field_comparison(self, field_id: str = "YL-CAND-03", **_: Any) -> dict[str, Any]:
        comp = self._load_field_comparison()
        if not comp:
            return {
                "status": "MISSING_EVIDENCE",
                "field_id": field_id,
                "missing_evidence": ["field_comparison.json (five-field comparison)"],
                "evidence_ids": [],
                "source_references": [],
            }
        fields = comp.get("fields", [])
        target = next((f for f in fields if f.get("field_id") == field_id), None)
        if target is None:
            return {
                "status": "MISSING_EVIDENCE",
                "field_id": field_id,
                "missing_evidence": [f"Cross-field comparison record for {field_id}"],
                "evidence_ids": [],
                "source_references": ["data/exports/yunlin_vh_2025_2026/field_comparison.json"],
            }
        per_field_deltas = {
            f["field_id"]: (f.get("2026_pre_to_warning_window") or {}).get("median_difference_db")
            for f in fields
        }
        pattern = comp.get("cross_field_pattern", {})
        ev_ids = [eid for f in fields for eid in f.get("evidence_ids", [])]
        spatial_assessment = (target.get("spatial_support") or {}).get("assessment", "")
        qa_passed = spatial_assessment.startswith("PASS") and len(fields) >= 2
        return {
            "status": "OBSERVED",
            "field_id": field_id,
            "qa_passed": qa_passed,
            "field_count": len(fields),
            "per_field_pre_to_warning_db": per_field_deltas,
            "target_field_delta_db": per_field_deltas.get(field_id),
            "pre_to_warning_increase_count": pattern.get("pre_to_warning_increase_count"),
            "nearest_other_field_m": target.get("nearest_other_field_m"),
            "crop_label": target.get("crop_label"),
            "causal_attribution": "UNKNOWN",
            "evidence_ids": ev_ids,
            "source_references": ["data/exports/yunlin_vh_2025_2026/field_comparison.json"],
        }

    def _run_seasonal_reference_comparison(self, field_id: str = "YL-CAND-03", **_: Any) -> dict[str, Any]:
        comp = self._load_field_comparison()
        if not comp:
            return {
                "status": "MISSING_EVIDENCE",
                "field_id": field_id,
                "missing_evidence": ["field_comparison.json (seasonal reference)"],
                "evidence_ids": [],
                "source_references": [],
            }
        target = next((f for f in comp.get("fields", []) if f.get("field_id") == field_id), None)
        if target is None:
            return {
                "status": "MISSING_EVIDENCE",
                "field_id": field_id,
                "missing_evidence": [f"Seasonal reference for {field_id}"],
                "evidence_ids": [],
                "source_references": ["data/exports/yunlin_vh_2025_2026/field_comparison.json"],
            }
        obs_2025 = target.get("observations", {}).get("2025", [])
        obs_2026 = target.get("observations", {}).get("2026", [])
        peak_2025 = (
            len(obs_2025) >= 3
            and obs_2025[1]["vh_median_db"] > obs_2025[0]["vh_median_db"]
            and obs_2025[1]["vh_median_db"] > obs_2025[2]["vh_median_db"]
        )
        peak_2026 = (
            len(obs_2026) >= 3
            and obs_2026[1]["vh_median_db"] > obs_2026[0]["vh_median_db"]
            and obs_2026[1]["vh_median_db"] > obs_2026[2]["vh_median_db"]
        )
        spatial_assessment = (target.get("spatial_support") or {}).get("assessment", "")
        qa_passed = spatial_assessment.startswith("PASS") and len(obs_2025) > 0 and len(obs_2026) > 0
        return {
            "status": "OBSERVED",
            "field_id": field_id,
            "qa_passed": qa_passed,
            "matched_date_pairs": target.get("matched_date_pairs", []),
            "early_to_middle_2025_db": (target.get("2025_early_to_middle") or {}).get("median_difference_db"),
            "early_to_middle_2026_db": (target.get("2026_pre_to_warning_window") or {}).get("median_difference_db"),
            "cross_year_early_to_middle_diff_db": target.get("cross_year_early_to_middle_change_difference_db"),
            "mid_season_peak_2025": peak_2025,
            "mid_season_peak_2026": peak_2026,
            "uniqueness_claim_challenged": peak_2025 and peak_2026,
            "causal_attribution": "UNKNOWN",
            "evidence_ids": target.get("evidence_ids", []),
            "source_references": ["data/exports/yunlin_vh_2025_2026/field_comparison.json"],
        }

    def _run_cross_crid_compatibility_test(self, **_: Any) -> dict[str, Any]:
        qa = _load_json(self._champi_dir / "science_qa.json")
        if not qa:
            return {
                "status": "MISSING_EVIDENCE",
                "missing_evidence": ["data/exports/typhoon_champi/science_qa.json"],
                "evidence_ids": [],
                "source_references": [],
            }
        comp = qa.get("comparability", {})
        return {
            "status": "OBSERVED",
            "qa_passed": bool(comp.get("crid_match") and comp.get("verified_typhoon_delta_allowed")),
            "crid_match": comp.get("crid_match"),
            "verified_typhoon_delta_allowed": comp.get("verified_typhoon_delta_allowed"),
            "qa_decision": comp.get("qa_decision"),
            "evidence_ids": ["E-CHAMPI-NISAR-TAIXI-PRE", "E-CHAMPI-NISAR-TAIXI-POST", "E-CHAMPI-ASF-CROSS-CRID"],
            "source_references": ["data/exports/typhoon_champi/science_qa.json"],
        }

    def _run_official_loss_scope_check(self, **_: Any) -> dict[str, Any]:
        loss = _load_json(self._champi_dir / "official_loss_record.json")
        if not loss:
            return {
                "status": "MISSING_EVIDENCE",
                "missing_evidence": ["data/exports/typhoon_champi/official_loss_record.json"],
                "evidence_ids": [],
                "source_references": [],
            }
        return {
            "status": "OBSERVED",
            "scope": "Yunlin County",
            "yunlin_county_ntd": loss.get("yunlin_county_ntd"),
            "parcel_ground_truth": False,
            "evidence_ids": ["E-CHAMPI-MOA-20261106"],
            "source_references": ["data/exports/typhoon_champi/official_loss_record.json"],
        }

    def _run_missing_evidence_audit(self, field_id: str = "YL-CAND-03", available_external_data: list[str] | None = None, **_: Any) -> dict[str, Any]:
        ext = set(available_external_data or [])
        needed = {
            "crop_and_harvest_records": "Parcel-level crop type, planting, and harvest calendar records",
            "rainfall_and_soil_moisture": "In-situ or high-resolution rainfall and soil moisture records",
            "ground_survey_or_optical": "Geolocated ground damage survey or cloud-free optical validation",
            "same_crid_nisar_reprocessing": "Reprocessed same-CRID NISAR pre/post scenes",
        }
        missing = [desc for key, desc in needed.items() if key not in ext]
        return {
            "status": "MISSING_EVIDENCE" if missing else "OBSERVED",
            "field_id": field_id,
            "missing_evidence": missing,
            "evidence_ids": [],
            "source_references": ["data/exports/yunlin_vh_2025_2026/field_comparison.json"],
        }
