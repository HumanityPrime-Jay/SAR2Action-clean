import json

from scripts.validate_science_cache import audit


def test_missing_b_team_cache_is_explicitly_blocked(tmp_path):
    result = audit(tmp_path)
    assert result['status'] == 'BLOCKED'
    assert len(result['errors']) == 3
    assert not any(result['expected_evidence_ids'].values())


def test_empty_stores_cannot_be_labeled_verified(tmp_path):
    (tmp_path / 'evidence_store.json').write_text(json.dumps({'records': []}), encoding='utf-8')
    (tmp_path / 'fingerprint_store.json').write_text(json.dumps({'fingerprints': {}}), encoding='utf-8')
    (tmp_path / 'analysis_store.json').write_text(json.dumps({'analyses': {}}), encoding='utf-8')
    result = audit(tmp_path)
    assert result['status'] == 'BLOCKED'
    assert result['external_nasa_provenance_verified'] is False
    assert result['counts'] == {'evidence': 0, 'fingerprints': 0, 'analyses': 0, 'claims': 0}
