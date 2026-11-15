"""Unit & integration tests for Earth Change Intelligence Platform."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.earth_intelligence.discovery_story import AIMapActionValidator
from backend.app.main import app

client = TestClient(app)


def test_global_event_catalog_and_epistemic_separation():
    r = client.get("/api/earth/events")
    assert r.status_code == 200
    body = r.json()
    assert len(body["supported_event_types"]) == 8
    by_id = {e["event_id"]: e for e in body["events"]}
    assert by_id["CHAMPI-YUNLIN-TAIXI"]["change_analysis_status"] == "CHANGE_ANALYZED"
    assert by_id["CHAMPI-YUNLIN-TAIXI"]["scientific_qa"]["yl_cand_03_vh_db"] == 7.55336
    assert by_id["CHAMPI-YUNLIN-TAIXI"]["scientific_qa"]["crop_damage_confirmed"] is False
    assert by_id["GLOBAL-CMR-MEKONG-FLOOD-REF"]["change_analysis_status"] == "CATALOG_DISCOVERED"
    assert by_id["GLOBAL-CMR-MEKONG-FLOOD-REF"]["demo_mode"] == "CATALOG_ONLY"


def test_earth_memory_timeline_warning_window_and_gaps():
    r = client.get("/api/earth/events/CHAMPI-YUNLIN-TAIXI/timeline?field_id=YL-CAND-03")
    assert r.status_code == 200
    body = r.json()
    assert len(body["acquisitions"]) >= 6
    assert len(body["observation_gaps"]) >= 1
    assert all(g["status"] == "NO_OBSERVATION" for g in body["observation_gaps"])
    oct22 = next(a for a in body["acquisitions"] if a["date_label"] == "2026-10-22")
    assert oct22["warning_phase"] == "DURING_TYPHOON_WARNING"
    assert oct22["metric_value"] == 7.55336 or oct22["metric_value"] == -10.59
    nisar_16 = next(a for a in body["acquisitions"] if a["acquisition_id"] == "NISAR-GCOV-20261016-P05023")
    assert nisar_16["compatible_with_baseline"] is False


def test_reality_lens_all_four_modes_no_fake_confidence():
    for lens in ("OBSERVED", "HYPOTHESES", "UNKNOWN", "NEXT_EVIDENCE"):
        r = client.get(f"/api/earth/events/CHAMPI-YUNLIN-TAIXI/lens/{lens}?field_id=YL-CAND-03")
        assert r.status_code == 200
        body = r.json()
        assert body["lens"] == lens
        assert body["no_fake_confidence"] is True
        assert len(body["features"]) >= 5


def test_surface_fingerprint_and_compatibility_gate():
    r = client.get("/api/earth/fingerprint/YL-CAND-03")
    assert r.status_code == 200
    fp = r.json()
    assert fp["temporal_difference_db"] == 7.55336
    assert fp["hh_hv_signature"] == "NOT_AVAILABLE"

    cmp_ok = client.post(
        "/api/earth/fingerprint/compare",
        json={"source_region_id": "YL-CAND-03", "target_region_id": "YL-CAND-01"},
    )
    assert cmp_ok.status_code == 200
    assert cmp_ok.json()["comparable"] is True
    assert cmp_ok.json()["normalized_feature_distance"] is not None

    cmp_bad = client.post(
        "/api/earth/fingerprint/compare",
        json={"source_region_id": "YL-CAND-03", "target_region_id": "TW03-NISAR-AOI"},
    )
    assert cmp_bad.status_code == 200
    assert cmp_bad.json()["comparable"] is False
    assert cmp_bad.json()["normalized_feature_distance"] is None


def test_hypothesis_arena_and_experiment_guardrail():
    arena = client.get("/api/earth/hypotheses/CHAMPI-YUNLIN-TAIXI?field_id=YL-CAND-03")
    assert arena.status_code == 200
    assert len(arena.json()["hypotheses"]) == 5

    flood_arena = client.get("/api/earth/hypotheses/GLOBAL-CMR-MEKONG-FLOOD-REF")
    assert flood_arena.status_code == 200
    assert "inundation" in flood_arena.json()["hypotheses"][0]["description"].lower()

    run = client.post(
        "/api/earth/hypotheses/experiment",
        json={"event_id": "CHAMPI-YUNLIN-TAIXI", "field_id": "YL-CAND-03", "hypothesis_id": "H1"},
    )
    assert run.status_code == 200
    body = run.json()
    assert body["executed"] is True
    assert body["hypothesis_status_after"] != "FALSIFIED"


def test_evidence_gaps_and_offline_catalog_search():
    gaps = client.get("/api/earth/evidence-gaps/CHAMPI-YUNLIN-TAIXI?field_id=YL-CAND-03")
    assert gaps.status_code == 200
    assert len(gaps.json()["gaps"]) >= 3

    cat = client.post(
        "/api/earth/evidence-gaps/catalog-search",
        json={"event_id": "CHAMPI-YUNLIN-TAIXI", "live_network": False},
    )
    assert cat.status_code == 200
    assert cat.json()["download_permitted"] is False
    assert cat.json()["scenes"] == []


def test_guided_discovery_allowlist_and_context_awareness():
    validated, rejected = AIMapActionValidator.validate_actions([
        {"action": "FLY_TO_REGION", "params": {"lon": 120.19, "lat": 23.70}},
        {"action": "EXEC_ARBITRARY_JS", "params": {"code": "alert(1)"}},
    ])
    assert len(validated) == 1
    assert len(rejected) == 1

    r = client.post(
        "/api/earth/guided-discovery",
        json={
            "query": "這個數字是什麼意思？",
            "prefer_gemini": False,
            "context": {"event_id": "CHAMPI-YUNLIN-TAIXI", "selected_field_id": "YL-CAND-03", "user_mode": "AUTHORITY", "lang": "zh"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "7.55336" in body["answer"]
    assert body["validated_actions_count"] >= 1


def test_planetary_story_generate_persist_import_and_html():
    gen = client.post(
        "/api/earth/stories/generate",
        json={"event_id": "CHAMPI-YUNLIN-TAIXI", "field_id": "YL-CAND-03", "user_mode": "AUTHORITY", "lang": "en"},
    )
    assert gen.status_code == 200
    story = gen.json()
    assert len(story["chapters"]) == 7
    assert story["chapters"][0]["chapter_code"].startswith("CHAPTER 01")
    assert story["chapters"][6]["chapter_code"].startswith("CHAPTER 07")

    fetched = client.get(f"/api/earth/stories/{story['story_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["story_id"] == story["story_id"]

    imp = client.post("/api/earth/stories/import", json={"story": story})
    assert imp.status_code == 200

    html_resp = client.get(f"/api/earth/stories/{story['story_id']}/export.html")
    assert html_resp.status_code == 200
    assert "CHAPTER 01" in html_resp.text
