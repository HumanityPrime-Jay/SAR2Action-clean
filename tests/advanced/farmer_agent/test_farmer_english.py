"""English mode of the farmer chat: Gemini translates in and out, and Chinese is the safe fallback."""
from backend.app.advanced.farmer_agent import FarmerConversationService


class FakeGemini:
    configured = True
    model = "fake-flash"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def generate_content(self, contents, **kwargs):
        self.calls.append(contents[0]["parts"][0]["text"])
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return {"candidates": [{"content": {"parts": [{"text": reply}]}}]}


def service(replies):
    svc = FarmerConversationService(use_gemini=True)
    svc.gemini_client = FakeGemini(replies)
    return svc


def test_english_question_is_translated_and_reply_comes_back_in_english():
    svc = service(["申請需要哪些文件？", "Bring your ID, seal, land or cultivation proof and a passbook copy."])
    res = svc.chat("en-1", "What documents do I need?", lang="en")
    assert res.intent == "REQUIRED_DOCUMENTS"
    assert res.reply_language == "en"
    assert res.reply.startswith("Bring your ID")
    assert res.sources == ["M0090019-ARTICLE-12"]


def test_chinese_reply_is_kept_when_translation_fails():
    svc = service([RuntimeError("Gemini request failed (503)")])
    res = svc.chat("en-2", "申請需要哪些文件？", lang="en")
    assert res.reply_language == "zh"
    assert "身分證" in res.reply


def test_stalled_call_is_retried_once():
    svc = service([RuntimeError("Gemini transport/timeout error on model 'x': timed out"), "Bring your ID."])
    res = svc.chat("en-7", "申請需要哪些文件？", lang="en")
    assert res.reply_language == "en"
    assert len(svc.gemini_client.calls) == 2


def test_translation_that_changes_numbers_is_rejected():
    svc = service(["Apply within 5 working days of the announcement."])
    res = svc.chat("en-3", "申請期限是什麼時候？", lang="en")
    assert res.reply_language == "zh"
    assert "10 個工作日" in res.reply


def test_translation_that_adds_numbers_is_rejected():
    svc = service(["申請需要哪些文件？", "For your 12.5 hectares, bring your ID and a passbook copy."])
    res = svc.chat("en-6", "What documents do I need?", lang="en")
    assert res.reply_language == "zh"


def test_translation_that_claims_approval_is_rejected():
    svc = service(["Good news: your relief has been approved."])
    res = svc.chat("en-4", "申請需要哪些文件？", lang="en")
    assert res.reply_language == "zh"


def test_without_gemini_english_mode_answers_in_chinese():
    res = FarmerConversationService(use_gemini=False).chat("en-5", "申請需要哪些文件？", lang="en")
    assert res.reply_language == "zh"
    assert "身分證" in res.reply
