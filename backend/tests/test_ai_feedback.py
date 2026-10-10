import json

import httpx
import pytest
from django.core.cache import cache

from ai import client as ai_client
from ai.models import AICallLog
from ai.schemas import FeedbackPrefs
from pulse.services.feedback import preferences_from_feedback

pytestmark = pytest.mark.django_db


@pytest.fixture
def ai_on(settings):
    settings.AI_PROVIDER = "anthropic"
    settings.AI_API_KEY = "test-key"
    cache.clear()
    return settings


def provider_returning(answer, calls):
    def call(model, system, user, schema, max_tokens):
        calls.append(user)
        return answer, 50, 20

    return call


def test_model_reads_free_text_feedback_and_the_answer_is_cached(monkeypatch, ai_on):
    calls = []
    answer = {"days": [{"weekday": 6, "factor": 0}], "preferred_hours": [8, 12], "understood": True}
    monkeypatch.setitem(ai_client.PROVIDERS, "anthropic", provider_returning(answer, calls))
    note = "I go to church on Sundays, and I think best before lunch"
    assert preferences_from_feedback(note) == ({6: 0.0}, (8, 12))
    assert preferences_from_feedback(note) == ({6: 0.0}, (8, 12))
    assert len(calls) == 1
    assert "church" in json.loads(calls[0].split("<data>\n")[1].split("\n</data>")[0])["note"]


def test_feedback_falls_back_to_keywords_without_ai():
    assert preferences_from_feedback("less on weekends, evenings please") == (
        {5: 0.5, 6: 0.5},
        (17, 23),
    )


def test_feedback_falls_back_when_the_model_does_not_understand(monkeypatch, ai_on):
    answer = {"days": [], "preferred_hours": None, "understood": False}
    monkeypatch.setitem(ai_client.PROVIDERS, "anthropic", provider_returning(answer, []))
    assert preferences_from_feedback("nothing on fridays") == ({4: 0.0}, None)


def test_feedback_falls_back_when_the_model_fails(monkeypatch, ai_on):
    def broken(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setitem(ai_client.PROVIDERS, "anthropic", broken)
    monkeypatch.setattr(ai_client.time, "sleep", lambda s: None)
    assert preferences_from_feedback("no saturdays") == ({5: 0.0}, None)
    assert AICallLog.objects.filter(purpose="feedback", fallback_used=True).exists()


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_provider_requests_are_well_formed(monkeypatch, settings, provider):
    settings.AI_PROVIDER = provider
    settings.AI_API_KEY = "test-key"
    cache.clear()
    sent = {}
    answer = {"days": [], "preferred_hours": None, "understood": False}

    def post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, body=json)
        if provider == "anthropic":
            body = {"content": [{"type": "tool_use", "input": answer}], "usage": {}}
        else:
            body = {"choices": [{"message": {"content": __import__("json").dumps(answer)}}]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(ai_client.httpx, "post", post)
    result = ai_client.complete_json(
        purpose="feedback", tier="light", prompt="feedback_v1",
        payload={"note": "hi"}, schema=FeedbackPrefs,
    )  # fmt: skip
    assert result.understood is False
    body = sent["body"]
    if provider == "anthropic":
        assert sent["headers"]["x-api-key"] == "test-key"
        assert body["tool_choice"] == {"type": "tool", "name": "respond"}
        assert "Everything inside <data>" in body["system"]
    else:
        assert sent["headers"]["Authorization"] == "Bearer test-key"
        assert body["max_completion_tokens"] > 0 and "max_tokens" not in body
        assert body["response_format"]["type"] == "json_schema"
        assert body["messages"][0]["role"] == "system"
    assert "<data>" in json.dumps(body)
