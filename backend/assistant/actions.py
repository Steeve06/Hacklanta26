"""Changes the assistant can propose. Each one is checked against the student's own data when
it's proposed and again when the student confirms, then applied through the same services the
app's buttons use."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from pydantic import ValidationError as PydanticError
from rest_framework.exceptions import APIException
from rest_framework.exceptions import ValidationError as DRFError

from accounts.clock import now as clock_now
from ai.schemas import AssistantAction
from pulse.models import AvailabilityBlock, Blackout, Session
from pulse.serializers import merge_blocks
from pulse.services import sessions as session_service
from pulse.services.replan import request_replan, start_generate_job

WEEKDAYS = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"]
SESSION_ACTIONS = {"skip_session", "mark_done", "reschedule_session", "move_session"}
LIMIT_FIELDS = {
    "max_hours_per_week": ("Weekly limit", 2, 40, "hours"),
    "max_hours_per_day": ("Most in one day", 1, 12, "hours"),
}
MAX_BLOCK = timedelta(days=14)


class Rejected(Exception):
    """The proposal can't be applied; the message says why in plain words."""


@dataclass
class Checked:
    data: dict
    text: str


def when(moment: datetime, tz) -> str:
    local = moment.astimezone(tz)
    clock = local.strftime("%I:%M %p").lstrip("0")
    return f"{local:%a %b} {local.day}, {clock}"


def clock(value: str) -> str:
    hour, minute = (int(x) for x in value.split(":"))
    return time(hour % 24, minute).strftime("%I:%M %p").lstrip("0")


def parse_local(value: str | None, tz) -> datetime:
    if not value:
        raise Rejected("A date and time is missing.")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as exc:
        raise Rejected(f"“{value}” isn't a date and time I can read.") from exc
    return moment.replace(tzinfo=tz) if moment.tzinfo is None else moment


def parse_clock(value: str) -> time:
    hour, minute = (int(x) for x in value.split(":"))
    if hour == 24 and minute == 0:
        return time(0)
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise Rejected(f"{value} isn't a time of day.")
    return time(hour, minute)


def _session(student, session_id: int | None) -> Session:
    session = (
        Session.objects.select_related("task", "schedule")
        .filter(pk=session_id, schedule__student=student, schedule__is_active=True)
        .first()
    )
    if session is None:
        raise Rejected("That session isn't in your current schedule.")
    if session.status != Session.Status.PLANNED:
        raise Rejected(f"“{session.title}” is already marked {session.status}.")
    return session


def _guard(fn, *args):
    """Run a service check, turning its API error into a plain rejection."""
    try:
        return fn(*args)
    except APIException as exc:
        detail = exc.detail
        if isinstance(detail, list):
            detail = detail[0]
        if isinstance(detail, dict):
            detail = next(iter(detail.values()))
            detail = detail[0] if isinstance(detail, list) else detail
        raise Rejected(str(detail)) from exc


def check(student, raw: dict) -> Checked:
    try:
        action = AssistantAction.model_validate(raw)
    except PydanticError as exc:
        raise Rejected("That change is missing details.") from exc
    tz = student.tz
    kind = action.type
    if kind in SESSION_ACTIONS:
        session = _session(student, action.session_id)
        label = f"“{session.title}” ({when(session.start, tz)})"
        data = {"type": kind, "session_id": session.id}
        if kind == "skip_session":
            return Checked(data, f"Skip {label}. Its work moves to later sessions.")
        if kind == "mark_done":
            if session.start > clock_now(student):
                raise Rejected("A session can only be marked done once it has started.")
            return Checked(data, f"Mark {label} as done.")
        if kind == "reschedule_session":
            if session.end <= clock_now(student):
                raise Rejected("That session has already ended. Skip it instead.")
            return Checked(data, f"Move {label} to the next free time that works.")
        start = parse_local(action.start, tz)
        _guard(session_service.check_move, student, session, start)
        data["start"] = start.isoformat()
        return Checked(data, f"Move {label} to {when(start, tz)}, and keep it there.")
    if kind == "block_time":
        start, end = parse_local(action.start, tz), parse_local(action.end, tz)
        if end <= start:
            raise Rejected("The busy time has to end after it starts.")
        if end - start > MAX_BLOCK:
            raise Rejected("Busy times can be at most two weeks long.")
        if end <= clock_now(student):
            raise Rejected("That time has already passed.")
        label = (action.label or "Busy").strip()[:60] or "Busy"
        data = {"type": kind, "start": start.isoformat(), "end": end.isoformat(), "label": label}
        return Checked(data, f"Keep {when(start, tz)} to {when(end, tz)} free ({label}).")
    if kind == "set_day_availability":
        if action.weekday is None:
            raise Rejected("Which day of the week?")
        blocks = []
        for r in action.blocks or []:
            start, end = parse_clock(r.start), parse_clock(r.end)
            minutes = ((end.hour * 60 + end.minute) or 24 * 60) - (start.hour * 60 + start.minute)
            if minutes < 30:
                raise Rejected("Study blocks need to be at least 30 minutes long.")
            blocks.append({"weekday": action.weekday, "start_time": start, "end_time": end})
        merged, _ = merge_blocks(blocks)
        others = AvailabilityBlock.objects.filter(student=student).exclude(weekday=action.weekday)
        if not merged and not others.exists():
            raise Rejected("That would leave you with no study time at all.")
        ranges = [
            {"start": b["start_time"].strftime("%H:%M"), "end": b["end_time"].strftime("%H:%M")}
            for b in merged
        ]
        day = WEEKDAYS[action.weekday]
        text = (
            f"{day}: study {', '.join(f'{clock(r["start"])}–{clock(r["end"])}' for r in ranges)}."
            if ranges
            else f"{day}: no study time."
        )
        return Checked({"type": kind, "weekday": action.weekday, "blocks": ranges}, text)
    if kind == "set_limits":
        return _check_limits(student, action)
    if kind == "rebuild_schedule":
        return Checked({"type": kind}, "Rebuild your schedule from now with your current settings.")
    note = (action.note or "").strip()
    if not note:
        raise Rejected("What should the schedule change?")
    return Checked(
        {"type": "schedule_note", "note": note},
        f"Rebuild your schedule with this in mind: “{note}”",
    )


def _check_limits(student, action: AssistantAction) -> Checked:
    profile = student.profile
    data: dict = {"type": "set_limits"}
    parts = []
    for field, (label, low, high, unit) in LIMIT_FIELDS.items():
        value = getattr(action, field)
        if value is None:
            continue
        value = round(float(value) * 2) / 2
        if not low <= value <= high:
            raise Rejected(f"{label} has to be between {low} and {high} {unit}.")
        data[field] = value
        parts.append(f"{label.lower()} {value:g} {unit}")
    if action.session_minutes is not None:
        if action.session_minutes not in (25, 50, 90):
            raise Rejected("Sessions can be 25, 50 or 90 minutes.")
        data["session_minutes"] = action.session_minutes
        parts.append(f"sessions of {action.session_minutes} minutes")
    earliest = parse_clock(action.earliest_time) if action.earliest_time else profile.earliest_time
    latest = parse_clock(action.latest_time) if action.latest_time else profile.latest_time
    if action.earliest_time or action.latest_time:
        if latest <= earliest:
            raise Rejected("The latest study time has to be after the earliest.")
        data["earliest_time"] = earliest.strftime("%H:%M")
        data["latest_time"] = latest.strftime("%H:%M")
        parts.append(
            f"study between {clock(data['earliest_time'])} and {clock(data['latest_time'])}"
        )
    week = data.get("max_hours_per_week", float(profile.max_hours_per_week))
    day = data.get("max_hours_per_day", float(profile.max_hours_per_day))
    if day > week:
        raise Rejected("The most in one day can't be more than the weekly limit.")
    if not parts:
        raise Rejected("Which setting should change?")
    return Checked(data, "Change your settings: " + "; ".join(parts) + ".")


def check_all(student, raw_actions: list[dict]) -> tuple[list[Checked], list[str]]:
    checked, problems = [], []
    for raw in raw_actions:
        try:
            checked.append(check(student, raw))
        except Rejected as exc:
            problems.append(str(exc))
    return checked, problems


@transaction.atomic
def apply_all(student, stored: list[dict]) -> None:
    """Check every change again (the plan may have moved since) and apply them in order."""
    for raw in stored:
        _apply(student, check(student, raw).data)


def _apply(student, data: dict) -> None:
    kind = data["type"]
    tz = student.tz
    if kind in SESSION_ACTIONS:
        session = _session(student, data["session_id"])
        if kind == "skip_session":
            _guard(session_service.update_status, student, session, Session.Status.SKIPPED, None)
        elif kind == "mark_done":
            _guard(session_service.update_status, student, session, Session.Status.DONE, None)
        elif kind == "reschedule_session":
            _guard(session_service.reschedule, student, session)
        else:
            _guard(session_service.move, student, session, parse_local(data["start"], tz))
        return
    if kind == "block_time":
        Blackout.objects.create(
            student=student,
            start=parse_local(data["start"], tz),
            end=parse_local(data["end"], tz),
            label=data["label"],
        )
        request_replan(student, "blackout")
        return
    if kind == "set_day_availability":
        AvailabilityBlock.objects.filter(student=student, weekday=data["weekday"]).delete()
        AvailabilityBlock.objects.bulk_create(
            AvailabilityBlock(
                student=student,
                weekday=data["weekday"],
                start_time=parse_clock(r["start"]),
                end_time=parse_clock(r["end"]),
            )
            for r in data["blocks"]
        )
        request_replan(student, "availability")
        return
    if kind == "set_limits":
        profile = student.profile
        for field in ("max_hours_per_week", "max_hours_per_day"):
            if field in data:
                setattr(profile, field, Decimal(str(data[field])))
        if "session_minutes" in data:
            profile.session_minutes = data["session_minutes"]
        if "earliest_time" in data:
            profile.earliest_time = parse_clock(data["earliest_time"])
            profile.latest_time = parse_clock(data["latest_time"])
        profile.save()
        request_replan(student, "preferences")
        return
    if kind == "rebuild_schedule":
        transaction.on_commit(lambda: start_generate_job(student, student.profile.plan_feedback))
        return
    profile = student.profile
    profile.plan_feedback = data["note"]
    profile.save(update_fields=["plan_feedback", "updated_at"])
    transaction.on_commit(lambda: start_generate_job(student, data["note"]))


def link_for(student, data: dict) -> dict:
    """Where the student can see a change once it's applied. Worked out before applying, since
    re-planning replaces the session rows."""
    kind = data["type"]
    tz = student.tz
    moment = None
    if kind in SESSION_ACTIONS:
        if data.get("start"):
            moment = parse_local(data["start"], tz)
        else:
            session = Session.objects.filter(pk=data["session_id"]).first()
            moment = session.start if session else None
    elif kind == "block_time":
        moment = parse_local(data["start"], tz)
    if kind == "set_day_availability":
        return {"to": "/settings#availability", "label": "See your study time"}
    if kind == "set_limits":
        return {"to": "/settings#preferences", "label": "See your study preferences"}
    if moment is not None:
        day = moment.astimezone(tz).date().isoformat()
        return {"to": f"/pulse/week?from={day}", "label": "See it in your week"}
    return {"to": "/pulse/week", "label": "See your new plan"}


def describe_rejection(exc: Exception) -> str:
    return str(exc) if isinstance(exc, Rejected | DRFError) else "Something went wrong."
