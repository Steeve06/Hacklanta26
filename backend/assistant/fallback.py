"""Answers without the model. Recognises the common requests by keyword so the assistant still
works when no AI provider is configured or the provider is down."""

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from accounts.clock import now as clock_now
from pulse.models import Session
from pulse.planning.feedback import parse_feedback

from .actions import when

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
PARTS = {"morning": (time(6), time(12)), "afternoon": (time(12), time(17)),
         "evening": (time(17), time(23, 59)), "tonight": (time(17), time(23, 59))}  # fmt: skip
HELP = (
    "I can skip or move a session, keep a day or an evening free, change your study hours, or "
    "rebuild the plan around a preference like “keep Sundays free”. What would you like to change?"
)


@dataclass
class Reply:
    text: str
    actions: list[dict] = field(default_factory=list)


def _has(text: str, *words: str) -> bool:
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


def _day(text: str, now: datetime) -> datetime | None:
    today = now.date()
    if _has(text, "today", "tonight", "this evening", "this morning", "this afternoon"):
        return datetime.combine(today, time(0), tzinfo=now.tzinfo)
    if _has(text, "tomorrow"):
        return datetime.combine(today + timedelta(days=1), time(0), tzinfo=now.tzinfo)
    for i, name in enumerate(DAYS):
        if _has(text, name, name[:3]):
            ahead = (i - today.weekday()) % 7
            return datetime.combine(today + timedelta(days=ahead), time(0), tzinfo=now.tzinfo)
    return None


def _upcoming(student, now: datetime):
    return (
        Session.objects.filter(
            schedule__student=student,
            schedule__is_active=True,
            status=Session.Status.PLANNED,
            end__gt=now,
        )
        .exclude(kind=Session.Kind.CHAPTER_QUIZ)
        .order_by("start")
    )


def _target_session(student, text: str, now: datetime) -> Session | None:
    day = _day(text, now)
    sessions = _upcoming(student, now)
    if day is not None:
        sessions = sessions.filter(start__gte=day, start__lt=day + timedelta(days=1))
    return sessions.first()


def _busy(student, text: str, now: datetime) -> Reply | None:
    if not _has(text, "busy", "working", "shift", "away", "trip", "can't study", "cannot study",
                "appointment"):  # fmt: skip
        return None
    day = _day(text, now)
    if day is None:
        return None
    profile = student.profile
    start_t, end_t = profile.earliest_time, profile.latest_time
    for part, (lo, hi) in PARTS.items():
        if _has(text, part):
            start_t, end_t = max(lo, start_t), min(hi, end_t) if end_t != time(0) else hi
            break
    start = datetime.combine(day.date(), start_t, tzinfo=now.tzinfo)
    end = datetime.combine(day.date(), end_t, tzinfo=now.tzinfo)
    if end_t == time(0) or end <= start:
        end = datetime.combine(day.date(), time(23, 59), tzinfo=now.tzinfo)
    start = max(start, now)
    if end <= start:
        return Reply("That time has already passed today.")
    action = {
        "type": "block_time",
        "start": start.strftime("%Y-%m-%dT%H:%M"),
        "end": end.strftime("%Y-%m-%dT%H:%M"),
        "label": "Busy",
    }
    return Reply("I can keep that time free and move any study planned then.", [action])


def answer(student, text: str) -> Reply:
    now = clock_now(student).astimezone(student.tz)
    lowered = text.lower().replace("’", "'")

    if _has(lowered, "skip", "can't make", "cannot make", "won't make", "not going to make"):
        session = _target_session(student, lowered, now)
        if session is None:
            return Reply("I couldn't find an upcoming session to skip.")
        return Reply(
            f"I can skip “{session.title}” and spread its work over later sessions.",
            [{"type": "skip_session", "session_id": session.id}],
        )
    busy = _busy(student, lowered, now)
    if busy:
        return busy
    if _has(lowered, "move", "reschedule", "later", "push", "postpone"):
        session = _target_session(student, lowered, now)
        if session is None:
            return Reply("I couldn't find an upcoming session to move.")
        return Reply(
            f"I can move “{session.title}” to the next free time that works.",
            [{"type": "reschedule_session", "session_id": session.id}],
        )
    if _has(lowered, "done", "finished", "completed"):
        session = (
            Session.objects.filter(
                schedule__student=student,
                schedule__is_active=True,
                status=Session.Status.PLANNED,
                start__lte=now,
            )
            .exclude(kind=Session.Kind.CHAPTER_QUIZ)
            .order_by("-start")
            .first()
        )
        if session is None:
            return Reply("None of your sessions has started yet, so there's nothing to mark done.")
        return Reply(
            f"Nice work. I can mark “{session.title}” as done.",
            [{"type": "mark_done", "session_id": session.id}],
        )
    days, hours = parse_feedback(text)
    if days or hours:
        return Reply(
            "I can rebuild your schedule around that.",
            [{"type": "schedule_note", "note": text.strip()[:300]}],
        )
    if _has(lowered, "next", "today", "what", "when", "schedule"):
        session = _upcoming(student, now).first()
        if session is None:
            return Reply("You have no sessions planned right now.")
        return Reply(f"Next up: “{session.title}”, {when(session.start, student.tz)}.")
    return Reply(HELP)
