"""Embeddings and reranking for the legal RAG (Phase E3/E4).

Retrieval runs on deterministic hashed character-ngram embeddings and a lexical-overlap
reranker: no neural model is downloaded or run. `neural_model_loaded` stays in the
metadata (always False) so stored rows and API responses keep their shape.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

FALLBACK_EMBED_MODEL_ID = "deterministic-cjk-trigram-hash-v1"
FALLBACK_DIM = 256


def _cjk_ngram_vector(text: str, dim: int = FALLBACK_DIM) -> list[float]:
    vec = [0.0] * dim
    cleaned = "".join(ch for ch in text if not ch.isspace())
    if not cleaned:
        return vec
    grams: list[str] = []
    for n in (1, 2, 3):
        if len(cleaned) >= n:
            grams.extend(cleaned[i : i + n] for i in range(len(cleaned) - n + 1))
    for g in grams:
        digest = hashlib.sha256(g.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class LocalEmbeddingEngine:
    """Deterministic CJK n-gram embedding engine."""

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "embedding_model_id": FALLBACK_EMBED_MODEL_ID,
            "embedding_model_revision": "v1-offline",
            "embedding_dimension": FALLBACK_DIM,
            "neural_model_loaded": False,
            "device": "cpu",
            "fallback_reason": None,
        }

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [_cjk_ngram_vector(t) for t in texts]


class LocalRerankerEngine:
    """Deterministic lexical-overlap reranker on top of the RRF score."""

    neural_loaded = False
    fallback_reason: str | None = None

    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not candidates:
            return []
        q_chars = set(query.replace(" ", ""))
        rescored = []
        for c in candidates:
            txt = c.get("text", "")
            overlap = len(q_chars & set(txt)) / max(1, len(q_chars))
            base = float(c.get("rrf_score", c.get("score", 0.0)))
            rescored.append({
                **c,
                "rerank_score": round(base + 0.05 * overlap, 6),
                "reranker_type": "deterministic_fallback",
            })
        return sorted(rescored, key=lambda x: x["rerank_score"], reverse=True)
