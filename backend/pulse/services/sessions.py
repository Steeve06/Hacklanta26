"""Student actions on scheduled sessions."""

from datetime import UTC, datetime, timedelta

from rest_framework.exceptions import ValidationError

from accounts.clock import now as clock_now
from lms.models import Assessment, DueDateOverride

from ..models import AvailabilityBlock, Blackout, Schedule, Session
from ..planning.slots import free_time
from ..planning.types import Interval
from .classes import in_class
from .replan import request_replan
from .status import invalidate as invalidate_status

S = Session.Status


def active_session(student, session_id: int) -> Session:
    session = (
        Session.objects.select_related("task", "schedule")
        .filter(pk=session_id, schedule__student=student, schedule__is_active=True)
        .first()
    )
    if session is None:
        from rest_framework.exceptions import NotFound

        raise NotFound("That session isn't in your current schedule.")
    return session


def update_status(student, session: Session, status: str, completed_minutes: int | None) -> Session:
    if status not in (S.DONE, S.PARTIAL, S.SKIPPED, S.PLANNED):
        raise ValidationError({"status": "Use done, partial, skipped or planned."})
    if status == S.PARTIAL and (
        completed_minutes is None or not 0 < completed_minutes < session.minutes
    ):
        raise ValidationError(
            {"completed_minutes": f"Enter between 1 and {session.minutes - 1} minutes."}
        )
    minutes = {S.DONE: session.minutes, S.PARTIAL: completed_minutes, S.SKIPPED: 0, S.PLANNED: 0}[
        status
    ]
    if status == S.PLANNED and session.end < clock_now(student) and session.status == S.PLANNED:
        return session
    session.status = status
    session.completed_minutes = minutes or 0
    session.save(update_fields=["status", "completed_minutes", "updated_at"])
    invalidate_status(student.id)
    request_replan(student, f"session_{status}")
    return session


def reschedule(student, session: Session) -> Session:
    if session.status != S.PLANNED:
        raise ValidationError("Only upcoming sessions can be rescheduled.")
    if session.end <= clock_now(student):
        raise ValidationError("This session has already ended. Mark it as skipped instead.")
    session.status = S.RESCHEDULED
    session.save(update_fields=["status", "updated_at"])
    request_replan(student, "session_rescheduled")
    return session


def active_schedule(student) -> Schedule | None:
    return Schedule.objects.filter(student=student, is_active=True).first()


def check_move(student, session: Session, start: datetime) -> datetime:
    """Raise ValidationError unless the session can go at `start`. Returns the new end."""
    now = clock_now(student)
    if session.status != S.PLANNED or session.kind == Session.Kind.CHAPTER_QUIZ:
        raise ValidationError("Only upcoming study sessions can be moved.")
    end = start + (session.end - session.start)
    if start <= now:
        raise ValidationError("Pick a time that hasn't passed yet.")
    profile = student.profile
    blocks = [
        (b.weekday, b.start_time, b.end_time)
        for b in AvailabilityBlock.objects.filter(student=student)
    ]
    blackouts = [
        Interval(b.start, b.end) for b in Blackout.objects.filter(student=student, end__gt=now)
    ] + in_class(student, now, end + timedelta(days=1))
    free = free_time(blocks, blackouts, tz=student.tz, start=now, end=end + timedelta(days=1),
                     earliest=profile.earliest_time, latest=profile.latest_time)  # fmt: skip
    day = start.astimezone(student.tz).date()
    utc_start, utc_end = start.astimezone(UTC), end.astimezone(UTC)
    if not any(iv.start <= utc_start and utc_end <= iv.end for iv in free.get(day, [])):
        raise ValidationError(
            "That time isn't inside your free study time, or you're in class then."
        )
    gap = timedelta(minutes=10)
    clash = (
        Session.objects.filter(schedule=session.schedule, status=S.PLANNED)
        .exclude(pk=session.pk)
        .filter(start__lt=end + gap, end__gt=start - gap)
        .exists()
    )
    if clash:
        raise ValidationError("Another session is already planned then.")
    if session.task.source_type == "assessment":
        override = DueDateOverride.objects.filter(
            assessment_id=session.task.source_id, student=student
        ).first()
        assessment = Assessment.objects.filter(pk=session.task.source_id).first()
        due = override.due_at if override else (assessment.due_at if assessment else None)
        if due and end > due:
            raise ValidationError("That's after the due date.")
    return end


def move(student, session: Session, start: datetime) -> Session:
    """Put a session at a time the student chose and lock it there. The rest of the plan is
    rebuilt around it."""
    end = check_move(student, session, start)
    session.start, session.end, session.locked = start, end, True
    session.save(update_fields=["start", "end", "locked", "updated_at"])
    request_replan(student, "session_moved")
    return session
