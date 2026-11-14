"""High-Accuracy Hybrid Legal RAG (Phases D-G)."""
from backend.app.advanced.legal_rag.database import LegalDatabase, build_sqlite_database
from backend.app.advanced.legal_rag.embeddings import LocalEmbeddingEngine, LocalRerankerEngine
from backend.app.advanced.legal_rag.parser import LAW_ID, LAW_NAME, build_legal_dataset
from backend.app.advanced.legal_rag.retriever import HybridLegalRetriever, analyze_legal_query
from backend.app.advanced.legal_rag.rules import RuleEvaluationItem, RuleState, evaluate_legal_rules
from backend.app.advanced.legal_rag.service import LegalRAGResponse, LegalRAGService, VerifiedCitation

__all__ = [
    "HybridLegalRetriever",
    "LAW_ID",
    "LAW_NAME",
    "LegalDatabase",
    "LegalRAGResponse",
    "LegalRAGService",
    "LocalEmbeddingEngine",
    "LocalRerankerEngine",
    "RuleEvaluationItem",
    "RuleState",
    "VerifiedCitation",
    "analyze_legal_query",
    "build_legal_dataset",
    "build_sqlite_database",
    "evaluate_legal_rules",
]
