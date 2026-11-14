"""Dual-Mode Platform (FARMER / AUTHORITY) & Security Separation."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class UserMode(str, Enum):
    FARMER = "FARMER"
    AUTHORITY = "AUTHORITY"


@dataclass
class ModeCapabilityRegistry:
    """Authoritative capabilities available per mode (public data unless authorized)."""

    CAPABILITIES: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "FARMER": {
                "mode": "FARMER",
                "label_zh_tw": "農民模式",
                "label_en": "Farmer Mode",
                "features": [
                    "natural_conversation",
                    "field_selection",
                    "field_area_calculation",
                    "farmer_reported_damage_area",
                    "satellite_change_explanation",
                    "loss_estimation_when_supported",
                    "relief_information",
                    "potential_relief_estimation",
                    "application_guidance",
                ],
                "indicator_level": "FARMER",
                "requires_government_auth_for_private_data": True,
            },
            "AUTHORITY": {
                "mode": "AUTHORITY",
                "label_zh_tw": "農政專業模式",
                "label_en": "Agricultural Authority / Analyst Mode",
                "features": [
                    "advanced_gis_analysis",
                    "sar_observation_exploration",
                    "multi_layer_map_analysis",
                    "spatial_statistics",
                    "field_comparison",
                    "scientific_investigation",
                    "quality_assessment",
                    "evidence_verification",
                    "research_reporting",
                    "legal_decision_support",
                ],
                "indicator_level": "AUTHORITY",
                "requires_government_auth_for_private_data": True,
                "public_analysis_only_without_auth": True,
            },
        }
    )

    def list_modes(self) -> list[dict[str, Any]]:
        return [self.CAPABILITIES["FARMER"], self.CAPABILITIES["AUTHORITY"]]

    def get_capabilities(self, mode: str, *, is_authenticated_authority: bool = False) -> dict[str, Any]:
        upper = mode.upper()
        if upper not in self.CAPABILITIES:
            raise ValueError(f"Unsupported mode: {mode}")
        cap = dict(self.CAPABILITIES[upper])
        cap["is_authenticated_authority"] = is_authenticated_authority
        cap["private_records_accessible"] = bool(upper == "AUTHORITY" and is_authenticated_authority)
        cap["official_approval_actions_enabled"] = False  # AI never approves official relief
        return cap


@dataclass
class UserModeContext:
    mode: UserMode = UserMode.FARMER
    selected_aoi: str | None = "10009160"
    selected_field_id: str | None = "YL-CAND-03"
    loaded_layers: list[str] = field(default_factory=lambda: ["Fields", "OPERA_VH"])
    shared_conversation_context: list[dict[str, str]] = field(default_factory=list)
    allowed_analysis_results: dict[str, Any] = field(default_factory=dict)
    is_authenticated_authority: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["mode"] = self.mode.value
        return data


class ModeTransitionController:
    """Safely transition between FARMER and AUTHORITY while preserving allowed state."""

    SENSITIVE_KEYS = {"private_applicant_id", "national_id", "land_parcel_owner", "non_public_case_file"}

    def switch_mode(
        self,
        current: UserModeContext,
        target_mode: str,
        *,
        is_authenticated_authority: bool = False,
    ) -> UserModeContext:
        upper = target_mode.upper()
        if upper not in ("FARMER", "AUTHORITY"):
            raise ValueError(f"Invalid target mode: {target_mode}")

        # Mode switch NEVER elevates backend authorization on its own
        auth_ok = bool(current.is_authenticated_authority and is_authenticated_authority)
        filtered_results = {
            k: v
            for k, v in current.allowed_analysis_results.items()
            if k not in self.SENSITIVE_KEYS and (auth_ok or not str(k).startswith("private_"))
        }
        return UserModeContext(
            mode=UserMode(upper),
            selected_aoi=current.selected_aoi,
            selected_field_id=current.selected_field_id,
            loaded_layers=list(current.loaded_layers),
            shared_conversation_context=list(current.shared_conversation_context),
            allowed_analysis_results=filtered_results,
            is_authenticated_authority=auth_ok,
        )
