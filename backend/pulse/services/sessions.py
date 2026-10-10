"""Student actions on scheduled sessions."""

from rest_framework.exceptions import ValidationError

from accounts.clock import now as clock_now

from ..models import Schedule, Session
from .replan import request_replan

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
