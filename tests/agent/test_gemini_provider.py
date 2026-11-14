from types import SimpleNamespace

from backend.app.services.gemini_provider import GeminiModelProvider
from backend.app.services.real_agent_runtime import FIRST_TOOLS, redact_credentials


class FakeModels:
    def __init__(self, calls):
        self.calls = calls
        self.config = None

    def generate_content(self, *, model, contents, config):
        self.config = config
        return SimpleNamespace(function_calls=self.calls)


def test_gemini_only_declares_safe_tools_and_validates_arguments(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'local-test-key-with-sufficient-length')
    models = FakeModels([
        SimpleNamespace(name='rank_change_regions', args={'case_id': 'case-a', 'aoi_bbox_wgs84': [100, 0, 101, 1]}),
        SimpleNamespace(name='shell', args={'command': 'whoami'}),
    ])
    provider = GeminiModelProvider(client=SimpleNamespace(models=models))
    calls, _ = provider.choose_gis_tools('Rank changes', {'rank_change_regions': FIRST_TOOLS['rank_change_regions']},
                                          {'case_id': 'case-a', 'aoi_bbox_wgs84': [100, 0, 101, 1]})
    assert calls[0]['error'] is None
    assert calls[1]['error'] == 'unauthorized_tool'
    assert models.config.automatic_function_calling.disable is True
    assert len(models.config.tools[0].function_declarations) == 1


def test_invalid_schema_and_secret_redaction(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'secret-test-credential-long-enough')
    models = FakeModels([SimpleNamespace(name='rank_change_regions', args={'case_id': 5})])
    provider = GeminiModelProvider(client=SimpleNamespace(models=models))
    calls, _ = provider.choose_gis_tools('Rank', {'rank_change_regions': FIRST_TOOLS['rank_change_regions']}, {})
    assert calls[0]['error'] == 'invalid_arguments'
    assert 'secret-test-credential-long-enough' not in redact_credentials('key=secret-test-credential-long-enough')
