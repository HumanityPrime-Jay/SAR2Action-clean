"""Model-Free Legal Retriever Facade (delegates to DeterministicSemanticRetriever)."""
from __future__ import annotations

from typing import Any

from backend.app.advanced.legal_rag.database import LegalDatabase
from backend.app.advanced.legal_rag.legal_concepts import LegalConceptDictionary
from backend.app.advanced.legal_rag.semantic_retriever import (
    DeterministicSemanticRetriever,
    StructuredLegalQuery,
    build_structured_legal_query,
)


def analyze_legal_query(query: str) -> StructuredLegalQuery:
    return build_structured_legal_query(query, LegalConceptDictionary())


class HybridLegalRetriever(DeterministicSemanticRetriever):
    """Backward-compatible facade over DeterministicSemanticRetriever (no neural models)."""

    def __init__(self, db: LegalDatabase | None = None, concept_dict: LegalConceptDictionary | None = None):
        super().__init__(db=db, concept_dict=concept_dict)

    def hybrid_search(
        self,
        query: str,
        *,
        top_k: int = 5,
        use_reranker: bool = False,
        rrf_k: int = 60,
        extra_queries: list[str] | None = None,
        candidate_articles: list[str] | None = None,
    ) -> dict[str, Any]:
        del use_reranker  # Unused: retrieval is 100% deterministic & model-free
        return self.retrieve(
            query,
            top_k=top_k,
            rrf_k=rrf_k,
            extra_queries=extra_queries,
            candidate_articles=candidate_articles,
        )
