"""Which reminders are true right now for one student."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from lms.selectors import AssessmentInfo, StudentSnapshot
from pulse.models import Schedule, Session

from .models import Trigger
from .templates_loader import TIERS

SESSION_STARTING_WINDOW = timedelta(minutes=10)
IGNORED_AFTER = timedelta(minutes=30)
IGNORED_LOOKBACK = timedelta(hours=6)
MISSED_LOOKBACK = timedelta(days=2)


@dataclass
class Candidate:
    trigger: str
    tier: int
    source_type: str
    source_id: int
    course_id: int | None
    variables: dict = field(default_factory=dict)
    link: str = ""
    due_at: datetime | None = None
    gentle: bool = False


def _hours(delta: timedelta) -> int:
    return max(1, round(delta.total_seconds() / 3600))


def _assessment_link(a: AssessmentInfo) -> str:
    return f"/lms/courses/{a.course_id}/assignments/{a.id}"


def _progress_ratio(sessions: list[Session], assessment_id: int) -> float | None:
    mine = [
        s
        for s in sessions
        if s.task.source_type == "assessment" and s.task.source_id == assessment_id
    ]
    total = sum(s.minutes for s in mine if s.status != "rescheduled")
    if not total:
        return None
    return sum(s.completed_minutes for s in mine) / total


def assessment_trigger(
    a: AssessmentInfo, sessions: list[Session], now: datetime
) -> Candidate | None:
    """The single most urgent reminder for an assessment, or None."""
    if a.done or a.status == "excused":
        return None
    until = a.due_at - now
    base = {"title": a.title, "course": a.course_code, "weight": f"{float(a.weight_pct):g}"}
    if until <= timedelta(0):
        if now - a.closes_at > MISSED_LOOKBACK:
            return None
        late_hours = max(0, round((a.closes_at - now).total_seconds() / 3600))
        trigger = Trigger.MISSED_LATE
        variables = {**base, "late_hours": late_hours}
    else:
        variables = {**base, "hours_left": _hours(until)}
        ratio = _progress_ratio(sessions, a.id)
        if until <= timedelta(hours=3):
            trigger = Trigger.CODE_RED
        elif until <= timedelta(hours=24):
            trigger = Trigger.FINAL_STRETCH
        elif until <= timedelta(hours=48) and ratio is not None and ratio < 0.3:
            trigger = Trigger.FALLING_BEHIND
        elif until <= timedelta(hours=72) and a.status == "not_started":
            trigger = Trigger.UPCOMING_DUE
        else:
            return None
    if a.extended:
        if trigger == Trigger.MISSED_LATE:
            return None
        trigger = Trigger.UPCOMING_DUE
    return Candidate(
        trigger=trigger,
        tier=TIERS[trigger],
        source_type="assessment",
        source_id=a.id,
        course_id=a.course_id,
        variables=variables,
        link=_assessment_link(a),
        due_at=a.due_at,
        gentle=a.extended,
    )


def session_triggers(
    sessions: list[Session], snapshot: StudentSnapshot, now: datetime
) -> list[Candidate]:
    codes = {c.id: c.code for c in snapshot.courses}
    found = []
    for s in sessions:
        if s.status != Session.Status.PLANNED or s.kind == Session.Kind.CHAPTER_QUIZ:
            continue
        variables = {
            "title": s.title.split(" · ", 1)[-1],
            "course": codes.get(s.task.course_id, ""),
        }
        if now < s.start <= now + SESSION_STARTING_WINDOW:
            trigger = Trigger.SESSION_STARTING
        elif now - IGNORED_LOOKBACK <= s.end <= now - IGNORED_AFTER:
            trigger = Trigger.SESSION_IGNORED
        else:
            continue
        found.append(
            Candidate(
                trigger, TIERS[trigger], "session", s.id, s.task.course_id, variables, "/pulse"
            )
        )
    return found


def evaluate(student, snapshot: StudentSnapshot, now: datetime) -> list[Candidate]:
    schedule = Schedule.objects.filter(student=student, is_active=True).first()
    sessions = list(schedule.sessions.select_related("task")) if schedule else []
    candidates = [c for a in snapshot.assessments if (c := assessment_trigger(a, sessions, now))]
    candidates += session_triggers(sessions, snapshot, now)
    return candidates


def still_true(notification, snapshot: StudentSnapshot, now: datetime) -> bool:
    """Re-check a queued reminder at send time."""
    if notification.trigger in (Trigger.WIN, Trigger.DIGEST):
        return True
    if notification.source_type == "assessment":
        a = next((x for x in snapshot.assessments if x.id == notification.source_id), None)
        return bool(a and not a.done and a.status != "excused")
    if notification.source_type == "session":
        session = Session.objects.filter(pk=notification.source_id).first()
        return bool(
            session and session.status == Session.Status.PLANNED and session.schedule.is_active
        )
    return True
