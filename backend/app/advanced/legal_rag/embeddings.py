"""Lazy-loaded Semantic Embedding & Neural Reranking (Phase E3/E4).

Supports Qwen/Qwen3-Embedding-0.6B and Qwen/Qwen3-Reranker-0.6B with GPU/CPU
fallback and model caching. When transformers/models are unavailable offline,
falls back to deterministic hashed character-ngram embeddings and explicitly
reports `neural_model_loaded = False` (never pretends neural models ran).
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

EMBEDDING_MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"
RERANKER_MODEL_ID = "Qwen/Qwen3-Reranker-0.6B"
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
    """Lazy-loaded embedding engine with model cache and CPU/offline fallback."""

    def __init__(self, prefer_neural: bool = True):
        self.prefer_neural = prefer_neural
        self._model = None
        self._tokenizer = None
        self._neural_loaded = False
        self._load_error: str | None = None
        self._device = "cpu"

    def _try_load_neural(self) -> None:
        if self._model is not None or self._load_error is not None or not self.prefer_neural:
            return
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL_ID, local_files_only=True)
            self._model = AutoModel.from_pretrained(EMBEDDING_MODEL_ID, local_files_only=True).to(self._device)
            self._model.eval()
            self._neural_loaded = True
        except Exception as exc:
            self._load_error = f"{type(exc).__name__}: {exc}"
            self._neural_loaded = False

    @property
    def metadata(self) -> dict[str, Any]:
        self._try_load_neural()
        return {
            "embedding_model_id": EMBEDDING_MODEL_ID if self._neural_loaded else FALLBACK_EMBED_MODEL_ID,
            "embedding_model_revision": "local-cached" if self._neural_loaded else "v1-offline",
            "embedding_dimension": 1024 if self._neural_loaded else FALLBACK_DIM,
            "neural_model_loaded": self._neural_loaded,
            "device": self._device if self._neural_loaded else "cpu",
            "fallback_reason": self._load_error,
        }

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._try_load_neural()
        if self._neural_loaded and self._model is not None and self._tokenizer is not None:
            import torch

            with torch.no_grad():
                enc = self._tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt").to(self._device)
                out = self._model(**enc)
                emb = out.last_hidden_state[:, 0]
                emb = torch.nn.functional.normalize(emb, p=2, dim=1)
                return emb.cpu().tolist()
        return [_cjk_ngram_vector(t) for t in texts]


class LocalRerankerEngine:
    """Lazy-loaded neural reranker with safe offline fallback."""

    def __init__(self, prefer_neural: bool = True):
        self.prefer_neural = prefer_neural
        self._model = None
        self._tokenizer = None
        self._neural_loaded = False
        self._load_error: str | None = None

    def _try_load(self) -> None:
        if self._model is not None or self._load_error is not None or not self.prefer_neural:
            return
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._tokenizer = AutoTokenizer.from_pretrained(RERANKER_MODEL_ID, local_files_only=True)
            self._model = AutoModelForSequenceClassification.from_pretrained(RERANKER_MODEL_ID, local_files_only=True).to(device)
            self._model.eval()
            self._neural_loaded = True
        except Exception as exc:
            self._load_error = f"{type(exc).__name__}: {exc}"
            self._neural_loaded = False

    @property
    def neural_loaded(self) -> bool:
        self._try_load()
        return self._neural_loaded

    @property
    def fallback_reason(self) -> str | None:
        self._try_load()
        return self._load_error

    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self._try_load()
        if not candidates:
            return []
        if self._neural_loaded and self._model is not None and self._tokenizer is not None:
            import torch

            pairs = [[query, c.get("text", "")] for c in candidates]
            with torch.no_grad():
                enc = self._tokenizer(pairs, padding=True, truncation=True, max_length=512, return_tensors="pt")
                scores = self._model(**enc).logits.view(-1).float().cpu().tolist()
            rescored = [{**c, "rerank_score": float(s), "reranker_type": "neural"} for c, s in zip(candidates, scores)]
            return sorted(rescored, key=lambda x: x["rerank_score"], reverse=True)

        # Deterministic lexical-overlap fallback when neural reranker is not cached locally
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
