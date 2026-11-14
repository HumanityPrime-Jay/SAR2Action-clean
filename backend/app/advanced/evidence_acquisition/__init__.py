"""Active Evidence Acquisition (Phase C)."""
from backend.app.advanced.evidence_acquisition.catalog_search import (
    CatalogScene,
    CatalogSearchQuery,
    SatelliteCatalogSearcher,
)
from backend.app.advanced.evidence_acquisition.controller import (
    AcquisitionAction,
    AcquisitionController,
    AcquisitionPlan,
    UnauthorizedAcquisitionError,
)
from backend.app.advanced.evidence_acquisition.gap_detector import (
    EvidenceGapReport,
    detect_evidence_gaps,
)

__all__ = [
    "AcquisitionAction",
    "AcquisitionController",
    "AcquisitionPlan",
    "CatalogScene",
    "CatalogSearchQuery",
    "EvidenceGapReport",
    "SatelliteCatalogSearcher",
    "UnauthorizedAcquisitionError",
    "detect_evidence_gaps",
]
