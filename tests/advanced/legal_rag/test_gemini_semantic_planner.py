"""Tests for GeminiLegalSemanticPlanner, A29/A32/A34/A37 fixes, and Blind Regression Set."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.app.advanced.gemini_client import GeminiClient
from backend.app.advanced.legal_rag import (
    GeminiLegalSemanticPlanner,
    LegalRAGService,
    LegalSemanticIntent,
)

BENCHMARK_DIR = Path(__file__).resolve().parent / "benchmark_200"


def test_legal_semantic_intent_pydantic_validation():
    intent = LegalSemanticIntent(
        original_question="test",
        detected_language="en",
        normalized_question_zh_tw="颱風水稻現金救助",
        legal_topic="CASH_RELIEF_ELIGIBILITY",
        relief_type="CASH_RELIEF",
        search_concepts=["c1", "c2", "c3", "c4", "c5", "c6", "c7"],
        suggested_article_ids=["第12條", "12-1", "invalid_art", "6", "4", "5", "9", "24"],
    )
    assert len(intent.search_concepts) == 6
    assert intent.suggested_article_ids == ["12", "12-1", "6", "4", "5", "9"]


def test_gemini_planner_fallback_on_missing_key_and_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    no_key_client = GeminiClient(api_key="")
    planner = GeminiLegalSemanticPlanner(gemini_client=no_key_client)
    intent, trace = planner.plan("My rice field in Yunlin was flooded")
    assert intent is None
    assert trace.fallback_used is True
    assert trace.fallback_reason == "GEMINI_API_KEY_NOT_CONFIGURED"

    bad_client = MagicMock(spec=GeminiClient)
    bad_client.configured = True
    bad_client.model = "gemini-3.1-flash-lite-preview"
    bad_client.generate_content.side_effect = RuntimeError("Timeout")
    planner_err = GeminiLegalSemanticPlanner(gemini_client=bad_client)
    intent2, trace2 = planner_err.plan("My rice field in Yunlin was flooded")
    assert intent2 is None
    assert trace2.fallback_used is True

    # LegalRAGService still answers deterministically even when Gemini fails
    svc = LegalRAGService(semantic_planner=planner_err)
    resp = svc.query("My rice field in Yunlin was flooded by typhoon, can I get cash relief?", use_gemini=True)
    assert resp.status == "ANSWERED"
    assert resp.citation_verification["verified"] is True


def test_known_four_critical_error_regressions_deterministic():
    held80 = {
        r["case_id"]: r
        for r in map(
            json.loads,
            (BENCHMARK_DIR / "final_held_out_80.jsonl").read_text(encoding="utf-8").splitlines(),
        )
        if r.get("case_id")
    }
    svc = LegalRAGService()

    # A29: disbursement & approval uncertainty
    r_a29 = svc.query(held80["A29"]["question"], use_gemini=False)
    assert r_a29.status == "ANSWERED"
    arts_a29 = [c["article"].removeprefix("第").removesuffix("條") for c in r_a29.citations[:5]]
    assert any(a in arts_a29 for a in held80["A29"]["expected_articles"])
    assert "未規定個別銀行或公所固定入帳天數" in r_a29.answer

    # A32: English query
    r_a32 = svc.query(held80["A32"]["question"], use_gemini=False)
    assert r_a32.status == "ANSWERED"
    arts_a32 = [c["article"].removeprefix("第").removesuffix("條") for c in r_a32.citations[:5]]
    assert any(a in arts_a32 for a in held80["A32"]["expected_articles"])

    # A34: fallow land / actual agricultural production
    r_a34 = svc.query(held80["A34"]["question"], use_gemini=False)
    assert r_a34.status == "ANSWERED"
    arts_a34 = [c["article"].removeprefix("第").removesuffix("條") for c in r_a34.citations[:5]]
    assert any(a in arts_a34 for a in held80["A34"]["expected_articles"])
    assert "區分" in r_a34.answer

    # A37: short-term vegetables & replanting loss
    r_a37 = svc.query(held80["A37"]["question"], use_gemini=False)
    assert r_a37.status == "ANSWERED"
    arts_a37 = [c["article"].removeprefix("第").removesuffix("條") for c in r_a37.citations[:5]]
    assert any(a in arts_a37 for a in held80["A37"]["expected_articles"])


def test_blind_regression_32_deterministic():
    rows = [
        json.loads(line)
        for line in (BENCHMARK_DIR / "blind_regression_32.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 32
    svc = LegalRAGService()
    status_ok = 0
    for row in rows:
        resp = svc.query(row["question"], use_gemini=False)
        assert resp.citation_verification["verified"] is True
        if resp.status == row["expected_status"]:
            status_ok += 1
    assert status_ok == 32


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="LIVE_GEMINI_NOT_RUN: GEMINI_API_KEY not set")
def test_live_gemini_semantic_planner_on_a29_and_a32():
    svc = LegalRAGService()
    r_a29 = svc.query("申請過了之後，錢大概什麼時候會匯進戶頭？", use_gemini=True)
    assert r_a29.status == "ANSWERED"
    assert r_a29.retrieval_trace["gemini_planner"]["gemini_succeeded"] is True
    assert r_a29.citation_verification["verified"] is True

    r_a32 = svc.query("My rice field in Yunlin was flooded by typhoon, can I get cash relief?", use_gemini=True)
    assert r_a32.status == "ANSWERED"
    assert r_a32.retrieval_trace["gemini_planner"]["gemini_succeeded"] is True
    arts_a32 = [c["article"].removeprefix("第").removesuffix("條") for c in r_a32.citations[:5]]
    assert any(a in arts_a32 for a in ("4", "6", "12"))
