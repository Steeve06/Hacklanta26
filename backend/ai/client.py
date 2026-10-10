"""Provider-agnostic structured-output client.

Every call returns a validated Pydantic object or raises AIError. Callers always have a
deterministic fallback, so an outage, a missing key or a bad response never blocks a feature.
"""

import json
import logging
import time
from decimal import Decimal
from pathlib import Path

import httpx
from django.conf import settings
from django.core.cache import cache
from pydantic import BaseModel, ValidationError

from .models import AICallLog

logger = logging.getLogger(__name__)


PROMPTS = Path(__file__).parent / "prompts"
BREAKER_KEY = "ai:breaker:failures"
BREAKER_OPEN_KEY = "ai:breaker:open"
BREAKER_THRESHOLD = 5
BREAKER_SECONDS = 600
MAX_INPUT_CHARS = 24_000

PRICES_PER_MTOK = {
    "claude-haiku": (Decimal("1"), Decimal("5")),
    "claude-sonnet": (Decimal("3"), Decimal("15")),
    "claude-opus": (Decimal("5"), Decimal("25")),
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.6")),
    "gpt-4o": (Decimal("2.5"), Decimal("10")),
}


class AIError(Exception):
    pass


def available() -> bool:
    return bool(settings.AI_PROVIDER and settings.AI_API_KEY) and not cache.get(BREAKER_OPEN_KEY)


def model_for(tier: str) -> str:
    if tier == "planner":
        return settings.AI_MODEL_PLANNER or _default_model("planner")
    return settings.AI_MODEL_LIGHT or _default_model("light")


def _default_model(tier: str) -> str:
    if settings.AI_PROVIDER == "openai":
        return "gpt-4o" if tier == "planner" else "gpt-4o-mini"
    return "claude-sonnet-5-5" if tier == "planner" else "claude-haiku-5-5"


def load_prompt(name: str) -> tuple[str, str]:
    """Return (version, text) for a prompt file such as 'decompose_v1'."""
    return name, (PROMPTS / f"{name}.md").read_text()


def cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    for prefix, (inp, out) in PRICES_PER_MTOK.items():
        if model.startswith(prefix):
            return (inp * input_tokens + out * output_tokens) / Decimal(1_000_000)
    return Decimal(0)


def _record_failure() -> None:
    failures = (cache.get(BREAKER_KEY) or 0) + 1
    cache.set(BREAKER_KEY, failures, BREAKER_SECONDS)
    if failures >= BREAKER_THRESHOLD:
        cache.set(BREAKER_OPEN_KEY, True, BREAKER_SECONDS)
        cache.delete(BREAKER_KEY)
        logger.warning("AI circuit breaker open for %s s after repeated failures", BREAKER_SECONDS)


def _record_success() -> None:
    cache.delete(BREAKER_KEY)


def _anthropic(
    model: str, system: str, user: str, schema: dict, max_tokens: int
) -> tuple[dict, int, int]:
    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.AI_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "tools": [
                {"name": "respond", "description": "Return the result.", "input_schema": schema}
            ],
            "tool_choice": {"type": "tool", "name": "respond"},
        },
        timeout=settings.AI_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()
    block = next((b for b in body.get("content", []) if b.get("type") == "tool_use"), None)
    if block is None:
        raise AIError("No structured output in response")
    usage = body.get("usage", {})
    return block["input"], usage.get("input_tokens", 0), usage.get("output_tokens", 0)


def _openai(
    model: str, system: str, user: str, schema: dict, max_tokens: int
) -> tuple[dict, int, int]:
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
        json={
            "model": model,
            "max_completion_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "respond", "schema": schema},
            },
        },
        timeout=settings.AI_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()
    content = body["choices"][0]["message"]["content"]
    usage = body.get("usage", {})
    return json.loads(content), usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


PROVIDERS = {"anthropic": _anthropic, "openai": _openai}


def complete_json[T: BaseModel](
    *,
    purpose: str,
    tier: str,
    prompt: str,
    payload: dict,
    schema: type[T],
    max_tokens: int = 2000,
    retry_note: str = "",
) -> T:
    """Run one structured call (plus one retry with backoff). `payload` is sent as data only."""
    if not available():
        raise AIError("AI is not configured or the circuit breaker is open")
    version, system = load_prompt(prompt)
    data = json.dumps(payload, ensure_ascii=False, default=str)
    if len(data) > MAX_INPUT_CHARS:
        raise AIError("Input too large")
    user = f"<data>\n{data}\n</data>"
    if retry_note:
        user += f"\n\nYour previous answer was rejected: {retry_note[:600]}\nFix these problems."
    model = model_for(tier)
    call = PROVIDERS.get(settings.AI_PROVIDER)
    if call is None:
        raise AIError(f"Unknown AI_PROVIDER {settings.AI_PROVIDER}")
    last_error = "unknown"
    for attempt in range(2):
        started = time.monotonic()
        log = AICallLog(
            purpose=purpose, provider=settings.AI_PROVIDER, model=model, prompt_version=version
        )
        try:
            raw, tokens_in, tokens_out = call(
                model, system, user, schema.model_json_schema(), max_tokens
            )
            log.input_tokens, log.output_tokens = tokens_in, tokens_out
            log.cost_usd = cost(model, tokens_in, tokens_out)
            result = schema.model_validate(raw)
            log.success = True
            _record_success()
            return result
        except (httpx.HTTPError, ValidationError, AIError, KeyError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            log.error = last_error
            _record_failure()
            if attempt == 0 and not cache.get(BREAKER_OPEN_KEY):
                time.sleep(0.5)
        finally:
            log.latency_ms = int((time.monotonic() - started) * 1000)
            log.save()
    raise AIError(last_error)


def note_fallback(purpose: str, reason: str) -> None:
    logger.info("AI fallback used for %s: %s", purpose, reason)
    AICallLog.objects.create(purpose=purpose, fallback_used=True, error=reason[:300])
