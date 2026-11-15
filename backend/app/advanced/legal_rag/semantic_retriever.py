"""Model-Free Deterministic Legal Semantic Retrieval Engine (P2).

Pipeline:
QUERY -> NORMALIZATION -> EXACT ARTICLE DETECTION -> CONCEPT MATCHING
-> SYNONYM EXPANSION -> FTS5 SEARCH (BM25) -> STRUCTURED RETRIEVAL
-> DETERMINISTIC RANKING -> SOURCE VERIFICATION

Zero neural models, zero Hugging Face downloads, zero vector/hash embeddings, zero GPU required.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from backend.app.advanced.legal_rag.database import LegalDatabase
from backend.app.advanced.legal_rag.legal_concepts import (
    ConceptMatch,
    LegalConceptDictionary,
    normalize_taiwan_legal_query,
)

CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def chinese_num_to_int(token: str) -> int | None:
    token = token.strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if token == "十":
        return 10
    if "十" in token:
        parts = token.split("十", 1)
        tens = CN_DIGITS.get(parts[0], 1) if parts[0] else 1
        ones = CN_DIGITS.get(parts[1], 0) if parts[1] else 0
        return tens * 10 + ones
    if len(token) == 1 and token in CN_DIGITS:
        return CN_DIGITS[token]
    return None


@dataclass
class StructuredLegalQuery:
    raw_query: str
    normalized_query: str
    exact_article_nos: list[str] = field(default_factory=list)
    exact_paragraph_no: int | None = None
    exact_item_no: int | None = None
    matched_concepts: list[dict[str, Any]] = field(default_factory=list)
    expanded_synonyms: list[str] = field(default_factory=list)
    keyword_terms: list[str] = field(default_factory=list)
    linked_articles: list[str] = field(default_factory=list)
    linked_appendices: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_structured_legal_query(
    query: str,
    concept_dict: LegalConceptDictionary,
) -> StructuredLegalQuery:
    """Normalize query, detect exact articles/subsections, match concepts, and expand synonyms."""
    norm = normalize_taiwan_legal_query(query)
    article_nos: list[str] = []

    for m in re.finditer(r"第?\s*(\d+(?:-\d+)?)\s*條", norm):
        no = m.group(1)
        if no not in article_nos:
            article_nos.append(no)

    for m in re.finditer(r"第\s*([一二三四五六七八九十]+)\s*條(?:\s*之\s*([一二三四五六七八九十]+))?", norm):
        base = chinese_num_to_int(m.group(1))
        if base is not None:
            sub = chinese_num_to_int(m.group(2)) if m.group(2) else None
            no = f"{base}-{sub}" if sub is not None else str(base)
            if no not in article_nos:
                article_nos.append(no)

    p_no = None
    m_p = re.search(r"第\s*([一二三四五六七八九十\d]+)\s*項", norm)
    if m_p:
        p_no = chinese_num_to_int(m_p.group(1))

    i_no = None
    m_i = re.search(r"第\s*([一二三四五六七八九十\d]+)\s*款", norm)
    if m_i:
        i_no = chinese_num_to_int(m_i.group(1))

    concept_matches: list[ConceptMatch] = concept_dict.match_concepts(norm)
    expanded_synonyms = concept_dict.expand_synonyms(concept_matches, max_terms=12)

    linked_articles: list[str] = []
    linked_appendices: list[str] = []
    for cm in concept_matches:
        for a in cm.linked_articles:
            if a not in linked_articles:
                linked_articles.append(a)
        for app in cm.linked_appendices:
            if app not in linked_appendices:
                linked_appendices.append(app)

    terms: list[str] = []
    for cm in concept_matches:
        for t in cm.matched_triggers:
            if t not in terms:
                terms.append(t)
    for syn in expanded_synonyms:
        if syn not in terms:
            terms.append(syn)

    for seq in re.findall(r"[\u4e00-\u9fff]{2,}", norm):
        cleaned = re.sub(r"(請問|什麼是|是什麼|怎麼|可以|嗎|呢|的|有哪些|多少|如何|能否|還能|算不算)", "", seq)
        if len(cleaned) >= 2 and cleaned not in terms:
            terms.append(cleaned)
        if len(cleaned) >= 4:
            for i in range(0, len(cleaned) - 2, 2):
                sub = cleaned[i : i + 3]
                if sub not in terms:
                    terms.append(sub)

    return StructuredLegalQuery(
        raw_query=query,
        normalized_query=norm,
        exact_article_nos=article_nos,
        exact_paragraph_no=p_no,
        exact_item_no=i_no,
        matched_concepts=[cm.to_dict() for cm in concept_matches],
        expanded_synonyms=expanded_synonyms,
        keyword_terms=terms[:18],
        linked_articles=linked_articles,
        linked_appendices=linked_appendices,
    )


class DeterministicSemanticRetriever:
    """Model-free legal semantic retriever using SQLite FTS5 BM25 + Controlled Ontology + Exact Lookup."""

    def __init__(
        self,
        db: LegalDatabase | None = None,
        concept_dict: LegalConceptDictionary | None = None,
    ):
        self.db = db or LegalDatabase()
        self.concept_dict = concept_dict or LegalConceptDictionary()

    def exact_search(self, structured: StructuredLegalQuery) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for art_no in structured.exact_article_nos:
            art = self.db.get_article_exact(art_no)
            if art:
                target_cid = art["article_id"]
                if structured.exact_paragraph_no is not None:
                    p_cid = f"{art['article_id']}-P{structured.exact_paragraph_no}"
                    if structured.exact_item_no is not None:
                        i_cid = f"{p_cid}-I{structured.exact_item_no}"
                        if self.db.get_provision_exact(i_cid):
                            target_cid = i_cid
                    elif self.db.get_provision_exact(p_cid):
                        target_cid = p_cid
                hits.append({
                    **art,
                    "citation_id": target_cid,
                    "retrieval_channel": "exact",
                    "rank_pos": len(hits) + 1,
                })
        return hits

    def fts5_bm25_search(self, structured: StructuredLegalQuery, limit: int = 12) -> list[dict[str, Any]]:
        terms = structured.keyword_terms or [structured.normalized_query]
        fts_hits = self.db.fts_search(terms, limit=limit)
        enriched: list[dict[str, Any]] = []
        seen: set[str] = set()
        for h in fts_hits:
            aid = h["article_id"]
            if aid in seen:
                continue
            seen.add(aid)
            art_no = aid.split("-ARTICLE-")[-1]
            art = self.db.get_article_exact(art_no)
            if art:
                enriched.append({
                    **art,
                    "citation_id": art["article_id"],
                    "retrieval_channel": "fts5_bm25",
                    "bm25_rank": float(h.get("rank", 0.0)),
                    "rank_pos": len(enriched) + 1,
                })
        return enriched[:limit]

    def concept_structured_search(self, structured: StructuredLegalQuery) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        seen: set[str] = set()
        for art_no in structured.linked_articles:
            art = self.db.get_article_exact(art_no)
            if art and art["article_id"] not in seen:
                seen.add(art["article_id"])
                hits.append({
                    **art,
                    "citation_id": art["article_id"],
                    "retrieval_channel": "concept_ontology",
                    "rank_pos": len(hits) + 1,
                })
        return hits

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        rrf_k: int = 60,
        extra_queries: list[str] | None = None,
        candidate_articles: list[str] | None = None,
    ) -> dict[str, Any]:
        structured = build_structured_legal_query(query, self.concept_dict)
        exact_hits = self.exact_search(structured)
        fts_hits = self.fts5_bm25_search(structured, limit=12)
        concept_hits = self.concept_structured_search(structured)

        scores: dict[str, float] = {}
        doc_map: dict[str, dict[str, Any]] = {}
        channels: dict[str, list[str]] = {}

        def _accumulate(hits: list[dict[str, Any]], weight: float, channel: str) -> None:
            for rank, item in enumerate(hits, 1):
                aid = item["article_id"]
                doc_map[aid] = item
                channels.setdefault(aid, [])
                if channel not in channels[aid]:
                    channels[aid].append(channel)
                scores[aid] = scores.get(aid, 0.0) + weight * (1.0 / (rrf_k + rank))

        _accumulate(exact_hits, 4.0, "exact")
        _accumulate(concept_hits, 2.2, "concept_ontology")
        _accumulate(fts_hits, 1.5, "fts5_bm25")

        # Optional Gemini-Assisted Semantic Expansion (fused deterministically, never replacing original query)
        if extra_queries:
            for eq in extra_queries[:3]:
                if not eq or not eq.strip():
                    continue
                eq_struct = build_structured_legal_query(eq, self.concept_dict)
                eq_fts = self.fts5_bm25_search(eq_struct, limit=8)
                eq_concepts = self.concept_structured_search(eq_struct)
                _accumulate(eq_concepts, 1.4, "gemini_concept_expansion")
                _accumulate(eq_fts, 1.1, "gemini_fts_expansion")

        if candidate_articles:
            verified_candidates: list[dict[str, Any]] = []
            seen_cand: set[str] = set()
            for art_no in candidate_articles[:8]:
                art = self.db.get_article_exact(art_no)
                if art and art["article_id"] not in seen_cand:
                    seen_cand.add(art["article_id"])
                    verified_candidates.append({
                        **art,
                        "citation_id": art["article_id"],
                        "retrieval_channel": "gemini_routed_verified",
                        "rank_pos": len(verified_candidates) + 1,
                    })
            _accumulate(verified_candidates, 1.3, "gemini_routed_verified")

        # Deterministic term-overlap & source-verification boost (purely lexical, zero AI models)
        boost_terms = [t for t in (structured.keyword_terms + structured.expanded_synonyms) if len(t) >= 2]
        for aid, doc in doc_map.items():
            text = doc.get("text", "")
            overlap = sum(1 for t in boost_terms if t in text)
            scores[aid] = scores.get(aid, 0.0) + min(overlap, 10) * 0.004

        ranked: list[dict[str, Any]] = []
        for aid, score in sorted(scores.items(), key=lambda kv: kv[1], reverse=True):
            doc = doc_map[aid]
            # Verify required source integrity fields exist
            if not (doc.get("law_id") and doc.get("article_id") and doc.get("source_sha256") and doc.get("text")):
                continue
            ranked.append({
                **doc,
                "deterministic_score": round(score, 6),
                "matched_channels": channels.get(aid, []),
            })

        if exact_hits:
            exact_ids = {h["article_id"] for h in exact_hits}
            pinned = [r for r in ranked if r["article_id"] in exact_ids]
            rest = [r for r in ranked if r["article_id"] not in exact_ids]
            final_hits = (pinned + rest)[:top_k]
        else:
            final_hits = ranked[:top_k]

        return {
            "query": query,
            "retrieval_mode": "MODEL_FREE_DETERMINISTIC_SEMANTIC",
            "ontology_id": self.concept_dict.ontology_id,
            "structured_query": structured.to_dict(),
            "hits": final_hits,
            "uses_neural_models": False,
            "requires_gpu": False,
        }
