"""Model-Free Deterministic Legal Semantic Retrieval (Phases D-G + P2)."""
from backend.app.advanced.legal_rag.database import LegalDatabase, build_sqlite_database
from backend.app.advanced.legal_rag.legal_concepts import (
    ConceptMatch,
    LegalConceptDictionary,
    normalize_taiwan_legal_query,
)
from backend.app.advanced.legal_rag.parser import LAW_ID, LAW_NAME, build_legal_dataset
from backend.app.advanced.legal_rag.retriever import HybridLegalRetriever, analyze_legal_query
from backend.app.advanced.legal_rag.rules import (
    LegalDecisionEvaluator,
    LegalDecisionResult,
    RuleEvaluationItem,
    RuleState,
    evaluate_legal_rules,
)
from backend.app.advanced.legal_rag.semantic_retriever import (
    DeterministicSemanticRetriever,
    StructuredLegalQuery,
    build_structured_legal_query,
)
from backend.app.advanced.legal_rag.semantic_planner import (
    SEMANTIC_TOPIC_ARTICLE_ROUTES,
    GeminiLegalSemanticPlanner,
    LegalSemanticIntent,
    PlannerTrace,
)
from backend.app.advanced.legal_rag.service import LegalRAGResponse, LegalRAGService, VerifiedCitation

__all__ = [
    "ConceptMatch",
    "DeterministicSemanticRetriever",
    "GeminiLegalSemanticPlanner",
    "HybridLegalRetriever",
    "LAW_ID",
    "LAW_NAME",
    "LegalConceptDictionary",
    "LegalDatabase",
    "LegalDecisionEvaluator",
    "LegalDecisionResult",
    "LegalRAGResponse",
    "LegalRAGService",
    "LegalSemanticIntent",
    "PlannerTrace",
    "RuleEvaluationItem",
    "RuleState",
    "SEMANTIC_TOPIC_ARTICLE_ROUTES",
    "StructuredLegalQuery",
    "VerifiedCitation",
    "analyze_legal_query",
    "build_legal_dataset",
    "build_sqlite_database",
    "build_structured_legal_query",
    "evaluate_legal_rules",
    "normalize_taiwan_legal_query",
]
