"""Controlled Acquisition Controller (Phase C3).

Strictly allows only SEARCH, VALIDATE, PLAN, REQUEST_APPROVAL.
Unapproved bulk satellite downloads are forbidden.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class AcquisitionAction(str, Enum):
    SEARCH = "SEARCH"
    VALIDATE = "VALIDATE"
    PLAN = "PLAN"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"


class UnauthorizedAcquisitionError(PermissionError):
    """Raised when attempting an unapproved download or disallowed action."""


@dataclass
class AcquisitionPlan:
    action: str
    status: str
    approved_for_download: bool
    candidate_scenes: list[dict[str, Any]] = field(default_factory=list)
    validation_summary: str = ""
    approval_request_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AcquisitionController:
    """Enforce controlled SEARCH -> VALIDATE -> PLAN -> REQUEST_APPROVAL workflow."""

    ALLOWED_ACTIONS = {a.value for a in AcquisitionAction}

    def execute_action(
        self,
        action: str,
        *,
        scenes: list[dict[str, Any]] | None = None,
        reason: str = "",
    ) -> AcquisitionPlan:
        upper = action.upper()
        if upper == "DOWNLOAD":
            raise UnauthorizedAcquisitionError(
                "Bulk satellite data download is forbidden without explicit human approval (REQUEST_APPROVAL)."
            )
        if upper not in self.ALLOWED_ACTIONS:
            raise UnauthorizedAcquisitionError(f"Acquisition action '{action}' is not allowed.")

        scenes = list(scenes or [])
        compatible = [s for s in scenes if s.get("compatible", False)]

        if upper == AcquisitionAction.SEARCH.value:
            return AcquisitionPlan(
                action=upper,
                status="SEARCH_COMPLETED",
                approved_for_download=False,
                candidate_scenes=scenes,
                validation_summary=f"Found {len(scenes)} candidate scenes.",
            )
        if upper == AcquisitionAction.VALIDATE.value:
            return AcquisitionPlan(
                action=upper,
                status="VALIDATED",
                approved_for_download=False,
                candidate_scenes=compatible,
                validation_summary=f"{len(compatible)}/{len(scenes)} scenes passed compatibility validation.",
            )
        if upper == AcquisitionAction.PLAN.value:
            return AcquisitionPlan(
                action=upper,
                status="PLANNED_AWAITING_APPROVAL",
                approved_for_download=False,
                candidate_scenes=compatible,
                validation_summary=f"Prepared acquisition plan for {len(compatible)} compatible scenes.",
            )
        return AcquisitionPlan(
            action=AcquisitionAction.REQUEST_APPROVAL.value,
            status="APPROVAL_REQUIRED",
            approved_for_download=False,
            candidate_scenes=compatible,
            validation_summary=f"{len(compatible)} compatible scenes staged for human approval.",
            approval_request_reason=reason or "Fill missing temporal/CRID satellite evidence gap.",
        )
