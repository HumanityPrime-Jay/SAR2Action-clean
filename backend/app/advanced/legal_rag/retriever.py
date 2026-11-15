"""Hybrid Legal Retrieval Engine (Phase E): Exact + FTS5 Keyword + Embedding + RRF + Reranker."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from backend.app.advanced.legal_rag.database import LegalDatabase
from backend.app.advanced.legal_rag.embeddings import (
    LocalEmbeddingEngine,
    LocalRerankerEngine,
    cosine_similarity,
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
class QueryAnalysis:
    raw_query: str
    exact_article_nos: list[str] = field(default_factory=list)
    exact_paragraph_no: int | None = None
    exact_item_no: int | None = None
    keyword_terms: list[str] = field(default_factory=list)
    intent_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_legal_query(query: str) -> QueryAnalysis:
    """Extract exact article/subsection numbers, deadlines, thresholds, and legal keywords."""
    q = query.strip()
    article_nos: list[str] = []

    # Match Arabic forms like 第12-1條, 12-1條, 第12條
    for m in re.finditer(r"第?\s*(\d+(?:-\d+)?)\s*條", q):
        no = m.group(1)
        if no not in article_nos:
            article_nos.append(no)

    # Match Chinese forms like 第十二條之一, 第十二條
    for m in re.finditer(r"第\s*([一二三四五六七八九十]+)\s*條(?:\s*之\s*([一二三四五六七八九十]+))?", q):
        base = chinese_num_to_int(m.group(1))
        if base is not None:
            sub = chinese_num_to_int(m.group(2)) if m.group(2) else None
            no = f"{base}-{sub}" if sub is not None else str(base)
            if no not in article_nos:
                article_nos.append(no)

    p_no = None
    m_p = re.search(r"第\s*([一二三四五六七八九十\d]+)\s*項", q)
    if m_p:
        p_no = chinese_num_to_int(m_p.group(1))

    i_no = None
    m_i = re.search(r"第\s*([一二三四五六七八九十\d]+)\s*款", q)
    if m_i:
        i_no = chinese_num_to_int(m_i.group(1))

    signals: list[str] = []
    kw_candidates = [
        ("deadline", ("期限", "幾天", "工作日", "展延", "三十日", "十個工作日", "申請時間")),
        ("loss_threshold", ("20%", "百分之二十", "損失率", "未達", "門檻")),
        ("exception", ("例外", "但書", "免勘查", "不在此限", "天氣參數")),
        ("appendix_amount", ("附表", "額度", "多少錢", "金額", "每公頃", "低利貸款")),
        ("disaster_definition", ("天然災害", "所稱", "定義", "颱風", "豪雨", "寒流", "地震", "旱災")),
        ("applicant_eligibility", ("農民", "資格", "申請人", "地號", "實際從事", "承租", "申請")),
        ("relief_types", ("現金救助", "低利貸款", "補助", "救助種類")),
        ("loss_estimation", ("損失金額", "估算", "第9條", "第九條", "生產總費用", "成園費")),
        ("application_procedure", ("哪裡申請", "公所", "文件", "程序", "怎麼申請", "可以申請")),
    ]
    terms: list[str] = []
    for sig, words in kw_candidates:
        matched = [w for w in words if w in q]
        if matched:
            signals.append(sig)
            terms.extend(matched)

    # Also extract CJK 2-4 char chunks from query for FTS5 trigram / LIKE
    for seq in re.findall(r"[\u4e00-\u9fff]{2,}", q):
        # Strip common question words
        cleaned = re.sub(r"(請問|什麼是|是什麼|怎麼|可以|嗎|呢|的|有哪些|多少|如何|能否|還能)", "", seq)
        if len(cleaned) >= 2 and cleaned not in terms:
            terms.append(cleaned)
        if len(cleaned) >= 4:
            for i in range(0, len(cleaned) - 2, 2):
                sub = cleaned[i : i + 3]
                if sub not in terms:
                    terms.append(sub)

    return QueryAnalysis(
        raw_query=q,
        exact_article_nos=article_nos,
        exact_paragraph_no=p_no,
        exact_item_no=i_no,
        keyword_terms=terms[:12],
        intent_signals=signals,
    )


class HybridLegalRetriever:
    """Multi-stage retriever: Exact + SQLite FTS5 Keyword + Embedding + RRF + Reranker."""

    def __init__(
        self,
        db: LegalDatabase | None = None,
        embedding_engine: LocalEmbeddingEngine | None = None,
        reranker_engine: LocalRerankerEngine | None = None,
    ):
        self.db = db or LegalDatabase()
        self.embedder = embedding_engine or LocalEmbeddingEngine()
        self.reranker = reranker_engine or LocalRerankerEngine()
        self._ensure_embeddings_indexed()

    def _ensure_embeddings_indexed(self) -> None:
        meta = self.embedder.metadata
        articles = self.db.list_all_articles()
        with self.db._connect() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) FROM legal_embeddings WHERE embedding_model_id = ?",
                (meta["embedding_model_id"],),
            ).fetchone()[0]
            if existing >= len(articles):
                return
            vectors = self.embedder.embed_batch([a["text"] for a in articles])
            for art, vec in zip(articles, vectors):
                conn.execute(
                    "INSERT OR REPLACE INTO legal_embeddings VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        art["article_id"],
                        meta["embedding_model_id"],
                        meta["embedding_model_revision"],
                        meta["embedding_dimension"],
                        json.dumps(vec),
                        art["source_sha256"],
                    ),
                )
            conn.commit()

    def exact_search(self, analysis: QueryAnalysis) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for art_no in analysis.exact_article_nos:
            art = self.db.get_article_exact(art_no)
            if art:
                # If subsection requested, still return full article + targeted citation_id
                target_cid = art["article_id"]
                if analysis.exact_paragraph_no is not None:
                    p_cid = f"{art['article_id']}-P{analysis.exact_paragraph_no}"
                    if analysis.exact_item_no is not None:
                        i_cid = f"{p_cid}-I{analysis.exact_item_no}"
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

    def keyword_search(self, analysis: QueryAnalysis, limit: int = 10) -> list[dict[str, Any]]:
        terms = analysis.keyword_terms or [analysis.raw_query]
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
                    "retrieval_channel": "keyword",
                    "rank_pos": len(enriched) + 1,
                })
        return enriched[:limit]

    def embedding_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        q_vec = self.embedder.embed_batch([query])[0]
        meta = self.embedder.metadata
        articles_by_id = {a["article_id"]: a for a in self.db.list_all_articles()}
        scored: list[tuple[float, dict[str, Any]]] = []
        with self.db._connect() as conn:
            rows = conn.execute(
                "SELECT chunk_id, vector_json FROM legal_embeddings WHERE embedding_model_id = ?",
                (meta["embedding_model_id"],),
            ).fetchall()
        for r in rows:
            art = articles_by_id.get(r["chunk_id"])
            if not art:
                continue
            sim = cosine_similarity(q_vec, json.loads(r["vector_json"]))
            scored.append((sim, art))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                **art,
                "citation_id": art["article_id"],
                "retrieval_channel": "embedding",
                "embedding_similarity": round(sim, 6),
                "rank_pos": idx,
            }
            for idx, (sim, art) in enumerate(scored[:limit], 1)
        ]

    def hybrid_search(
        self,
        query: str,
        *,
        top_k: int = 5,
        use_reranker: bool = True,
        rrf_k: int = 60,
    ) -> dict[str, Any]:
        analysis = analyze_legal_query(query)
        exact_hits = self.exact_search(analysis)
        kw_hits = self.keyword_search(analysis, limit=10)
        emb_hits = self.embedding_search(query, limit=10)

        # Reciprocal Rank Fusion (RRF): never add raw heterogeneous scores
        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, dict[str, Any]] = {}
        channels: dict[str, list[str]] = {}

        def _accumulate(hits: list[dict[str, Any]], weight: float, channel: str) -> None:
            for rank, item in enumerate(hits, 1):
                aid = item["article_id"]
                doc_map[aid] = item
                channels.setdefault(aid, [])
                if channel not in channels[aid]:
                    channels[aid].append(channel)
                rrf_scores[aid] = rrf_scores.get(aid, 0.0) + weight * (1.0 / (rrf_k + rank))

        _accumulate(exact_hits, 3.0, "exact")
        _accumulate(kw_hits, 1.5, "keyword")
        _accumulate(emb_hits, 1.0, "embedding")

        # Deterministic legal priority boosts (deadlines, thresholds, exceptions)
        priority_map = {
            "deadline": {"12", "12-2"},
            "loss_threshold": {"12-1"},
            "exception": {"12", "12-1", "12-2"},
            "disaster_definition": {"2", "3", "4"},
            "applicant_eligibility": {"5", "6", "12-1"},
            "relief_types": {"4", "6", "7"},
            "loss_estimation": {"9"},
            "application_procedure": {"12"},
            "appendix_amount": {"6", "6-1", "6-2", "6-3", "6-4"},
        }
        for sig in analysis.intent_signals:
            for art_no in priority_map.get(sig, set()):
                aid = f"M0090019-ARTICLE-{art_no}"
                if aid not in doc_map:
                    art = self.db.get_article_exact(art_no)
                    if art:
                        doc_map[aid] = {**art, "citation_id": aid}
                        channels.setdefault(aid, []).append("rule_priority")
                if aid in doc_map:
                    rrf_scores[aid] = rrf_scores.get(aid, 0.0) + 0.03

        fused = []
        for aid, score in sorted(rrf_scores.items(), key=lambda kv: kv[1], reverse=True):
            fused.append({
                **doc_map[aid],
                "rrf_score": round(score, 6),
                "matched_channels": channels.get(aid, []),
            })

        if use_reranker and fused:
            # Keep exact article hit pinned at #1 when user explicitly asked for an article number
            if exact_hits:
                exact_ids = {h["article_id"] for h in exact_hits}
                pinned = [f for f in fused if f["article_id"] in exact_ids]
                rest = self.reranker.rerank(query, [f for f in fused if f["article_id"] not in exact_ids])
                final_hits = (pinned + rest)[:top_k]
            else:
                final_hits = self.reranker.rerank(query, fused[: max(top_k * 2, 8)])[:top_k]
        else:
            final_hits = fused[:top_k]

        return {
            "query": query,
            "analysis": analysis.to_dict(),
            "hits": final_hits,
            "embedding_metadata": self.embedder.metadata,
            "reranker_neural_loaded": self.reranker.neural_loaded,
        }
