"""Good / medium / bad: one backend score per course and overall. The frontend only animates it."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.core.cache import cache

from accounts.clock import now as clock_now
from lms.selectors import StudentSnapshot, student_snapshot

from ..models import Schedule, Session, StatusSnapshot

OVERLOAD_SOON = timedelta(days=3)
WEIGHTS = {"adherence": 0.40, "deadlines": 0.30, "chapters": 0.20, "streak": 0.10}
DEADLINE_PENALTY_SCALE = 15.0
CACHE_SECONDS = 120
CODE_RED_HOURS = 3
CELEBRATE_MINUTES = 15
FORCE_MEDIUM_WEIGHT = 10


@dataclass
class Reason:
    impact: float
    text: str


@dataclass
class CourseStatus:
    course_id: int | None
    code: str
    score: int
    state: str
    reasons: list[str]
    components: dict
    remaining_weight: float = 0.0
    forced: list[str] = field(default_factory=list)


def _cache_key(student_id: int) -> str:
    return f"status:{student_id}"


def invalidate(student_id: int) -> None:
    cache.delete(_cache_key(student_id))


def band(score: float, previous: str | None) -> str:
    """Hysteresis: keep the previous state until the score clearly leaves it."""
    if previous == "good" and score >= 70:
        return "good"
    if previous == "bad" and score < 50:
        return "bad"
    if previous == "medium" and 40 <= score <= 79:
        return "medium"
    if score >= 75:
        return "good"
    if score >= 45:
        return "medium"
    return "bad"


def _hours(delta: timedelta) -> int:
    return max(1, round(delta.total_seconds() / 3600))


def _adherence(sessions: list[Session], now: datetime) -> tuple[float | None, list[Reason]]:
    window = [
        s for s in sessions if now - timedelta(days=7) <= s.end <= now and s.status != "rescheduled"
    ]
    scheduled = sum(s.minutes for s in window)
    if scheduled == 0:
        return None, []
    done = sum(s.completed_minutes for s in window)
    ratio = min(1.0, done / scheduled)
    reasons = []
    skipped = [s for s in window if s.status in ("skipped", "planned")]
    if skipped and ratio < 0.8:
        reasons.append(
            Reason(
                (1 - ratio) * WEIGHTS["adherence"] * 100,
                f"{len(skipped)} of {len(window)} sessions this week weren't done",
            )
        )
    return ratio, reasons


def _deadlines(snapshot: StudentSnapshot, course_id, now) -> tuple[float, list[Reason], list[str]]:
    penalty = 0.0
    reasons: list[Reason] = []
    forced: list[str] = []
    for a in snapshot.assessments:
        if course_id is not None and a.course_id != course_id:
            continue
        weight = float(a.weight_pct)
        if a.status == "missed" and now - a.closes_at <= timedelta(days=14):
            penalty += weight
            reasons.append(Reason(weight * 2, f"Missed {a.course_code} {a.title} ({weight:g}%)"))
        if a.status == "missed" and weight >= FORCE_MEDIUM_WEIGHT:
            forced.append("medium")
        late = a.submitted_at and a.submitted_at > a.due_at
        if late and now - a.submitted_at <= timedelta(days=14):
            penalty += weight * 0.5
        if a.done or a.status in ("missed", "excused"):
            continue
        until = a.due_at - now
        if timedelta(0) < until <= timedelta(hours=72) and a.status == "not_started":
            penalty += weight * 0.5
            reasons.append(
                Reason(weight, f"{a.course_code} {a.title} due in {_hours(until)} h, not started")
            )
        elif until <= timedelta(0) and a.closes_at > now:
            penalty += weight * 0.5
            reasons.append(
                Reason(
                    weight * 1.5,
                    f"{a.course_code} {a.title} is overdue; the late window is still open",
                )
            )
    return max(0.0, 1 - penalty / DEADLINE_PENALTY_SCALE), reasons, forced


def _chapters(snapshot: StudentSnapshot, course_id, now) -> tuple[float, list[Reason]]:
    chapters = [c for c in snapshot.chapters if course_id is None or c.course_id == course_id]
    expected = [c for c in chapters if c.week_end and c.week_end <= now]
    if not expected:
        return 1.0, []
    done = sum(1 for c in expected if c.completed_at)
    behind = len(expected) - done
    reasons = []
    if behind:
        where = snapshot.course(course_id).code if course_id else "your courses"
        reasons.append(
            Reason(
                behind / len(expected) * WEIGHTS["chapters"] * 100,
                f"{behind} chapter{'s' if behind > 1 else ''} behind in {where}",
            )
        )
    return done / len(expected), reasons


def _streak_component(student, now) -> tuple[float, list[Reason]]:
    from quizzes.services.streaks import streak_component

    return streak_component(student, now)


def _course_status(student, snapshot, sessions, course_id, code, now, overload, previous):
    course_sessions = [s for s in sessions if course_id is None or s.task.course_id == course_id]
    adherence, r1 = _adherence(course_sessions, now)
    deadlines, r2, forced = _deadlines(snapshot, course_id, now)
    chapters, r3 = _chapters(snapshot, course_id, now)
    streak, r4 = _streak_component(student, now)
    components = {
        "adherence": adherence if adherence is not None else 1.0,
        "deadlines": deadlines,
        "chapters": chapters,
        "streak": streak,
    }
    score = round(sum(WEIGHTS[k] * v for k, v in components.items()) * 100)
    state = band(score, previous)
    if overload and overload.get("unresolvable"):
        forced.append("bad")
    soon = now + OVERLOAD_SOON
    tight = [
        i
        for i in (overload or {}).get("items", [])
        if (course_id is None or i["course_code"] == code)
        and datetime.fromisoformat(i["due_at"]) <= soon
    ]
    if tight:
        r2.append(Reason(15, _overload_reason(tight)))
    state = _apply_forced(state, forced)
    reasons = sorted([*r1, *r2, *r3, *r4], key=lambda r: -r.impact)
    remaining = sum(
        float(a.weight_pct)
        for a in snapshot.assessments
        if (course_id is None or a.course_id == course_id) and not a.done and a.status != "missed"
    )
    return CourseStatus(
        course_id, code, score, state, [r.text for r in reasons[:3]], components, remaining, forced
    )


def _apply_forced(state: str, forced: list[str]) -> str:
    if "bad" in forced:
        return "bad"
    if "medium" in forced and state == "good":
        return "medium"
    return state


def _overload_reason(items: list[dict]) -> str:
    """Plain, not a verdict: the plan is a help, and tight weeks happen."""
    first = min(items, key=lambda i: i["due_at"])
    title = f"{first['course_code']} {first['title']}"
    return f"{title} won't fully fit in your study time before it's due"


def compute(student, *, save: bool = True) -> dict:
    now = clock_now(student)
    snapshot = student_snapshot(student, now)
    schedule = Schedule.objects.filter(student=student, is_active=True).first()
    sessions = list(schedule.sessions.select_related("task")) if schedule else []
    overload = schedule.overload_report if schedule else None
    previous: dict = {}
    for snap in StatusSnapshot.objects.filter(student=student).order_by("-computed_at", "-id")[:50]:
        previous.setdefault(snap.course_id, snap.state)

    courses = [
        _course_status(student, snapshot, sessions, c.id, c.code, now, overload, previous.get(c.id))
        for c in snapshot.courses
    ]
    total_weight = sum(c.remaining_weight + 1 for c in courses) or 1
    overall_score = round(sum(c.score * (c.remaining_weight + 1) for c in courses) / total_weight)
    overall = _course_status(
        student, snapshot, sessions, None, "overall", now, overload, previous.get(None)
    )
    overall.score = overall_score if courses else 100
    overall.state = _apply_forced(band(overall.score, previous.get(None)), overall.forced)

    fresh = _is_fresh(student, sessions, snapshot)
    all_done = (
        bool(snapshot.assessments)
        and all(a.done or a.status == "excused" for a in snapshot.assessments)
        and all(c.completed_at for c in snapshot.chapters)
    )
    if fresh:
        overall.state, overall.reasons = "good", ["New term, new you. Nothing is late yet."]
        for c in courses:
            c.state = "good"
    if all_done:
        overall.state = "good"
        overall.reasons = ["Everything is done. Suspicious, but impressive."]

    if save:
        StatusSnapshot.objects.filter(
            student=student, computed_at__lt=now - timedelta(days=30)
        ).delete()
        StatusSnapshot.objects.bulk_create(
            StatusSnapshot(
                student=student,
                course_id=c.course_id,
                score=c.score,
                state=c.state,
                reasons=c.reasons,
                components=c.components,
                computed_at=now,
            )  # fmt: skip
            for c in [overall, *courses]
        )
    return {
        "computed_at": now,
        "overall": _as_dict(overall),
        "courses": [_as_dict(c) for c in courses],
        "fresh_start": fresh,
        "all_done": all_done,
        "moment": _moment(student, snapshot, now, fresh),
    }


def _as_dict(c: CourseStatus) -> dict:
    return {
        "course_id": c.course_id,
        "code": c.code,
        "score": c.score,
        "state": c.state,
        "reasons": c.reasons,
        "components": {k: round(v, 3) for k, v in c.components.items()},
    }


def _is_fresh(student, sessions, snapshot) -> bool:
    has_history = any(s.status != "planned" for s in sessions) or any(
        a.submitted_at or a.status == "missed" for a in snapshot.assessments
    )
    return not has_history and not any(c.completed_at for c in snapshot.chapters)


def _moment(student, snapshot: StudentSnapshot, now, fresh: bool) -> dict | None:
    """A one-shot animation the client should play once (keyed so it plays only once)."""
    recent = [
        a for a in snapshot.assessments
        if a.submitted_at and now - a.submitted_at <= timedelta(minutes=CELEBRATE_MINUTES)
        and a.submitted_at <= a.due_at
    ]  # fmt: skip
    if recent:
        latest = max(recent, key=lambda a: a.submitted_at)
        return {
            "kind": "celebrate",
            "key": f"submit-{latest.id}",
            "text": f"Submitted {latest.title}",
        }
    red = [
        a for a in snapshot.assessments
        if not a.done and a.status not in ("excused", "missed")
        and timedelta(0) < a.due_at - now <= timedelta(hours=CODE_RED_HOURS)
    ]  # fmt: skip
    if red:
        return {
            "kind": "gasp",
            "key": f"red-{red[0].id}",
            "text": f"{red[0].title} is due very soon",
        }
    if fresh:
        return {"kind": "fresh_start", "key": f"fresh-{student.id}", "text": "Fresh start"}
    return None


def current(student) -> dict:
    key = _cache_key(student.id)
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = compute(student)
    cache.set(key, result, CACHE_SECONDS)
    return result
