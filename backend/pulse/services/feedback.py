"""Read a student's note about their schedule ("keep Sundays free, mornings are best") as solver
preferences. The model reads free text; the keyword parser is the fallback."""

import hashlib

from ai.client import AIError, available, complete_json, note_fallback
from ai.models import AICache
from ai.schemas import FeedbackPrefs

from ..planning.feedback import parse_feedback

PROMPT = "feedback_v1"

Prefs = tuple[dict[int, float], tuple[int, int] | None]


def _from_model(result: FeedbackPrefs) -> Prefs:
    days = {d.weekday: round(d.factor, 2) for d in result.days}
    hours = None
    if result.preferred_hours:
        lo, hi = result.preferred_hours
        if 0 <= lo < hi <= 24:
            hours = (lo, hi)
    return days, hours


def preferences_from_feedback(text: str) -> Prefs:
    text = (text or "").strip()
    if not text:
        return {}, None
    key = "feedback:" + hashlib.sha256(f"{PROMPT}\n{text.lower()}".encode()).hexdigest()[:48]
    cached = AICache.objects.filter(key=key).first()
    if cached:
        days = {int(k): v for k, v in cached.payload["days"].items()}
        hours = tuple(cached.payload["hours"]) if cached.payload["hours"] else None
        return days, hours
    if available():
        try:
            result = complete_json(
                purpose="feedback", tier="light", prompt=PROMPT,
                payload={"note": text[:300]}, schema=FeedbackPrefs, max_tokens=400,
            )  # fmt: skip
            if result.understood:
                days, hours = _from_model(result)
                AICache.objects.update_or_create(
                    key=key,
                    defaults={"purpose": "feedback", "payload": {"days": days, "hours": hours}},
                )
                return days, hours
        except AIError as exc:
            note_fallback("feedback", str(exc))
    return parse_feedback(text)
