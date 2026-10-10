"""Availability, a week of study history and a current plan for the demo students."""

from datetime import time, timedelta

from django.utils import timezone

from accounts.models import StudentProfile
from lms.models import Submission
from pulse.models import AvailabilityBlock, Session
from pulse.services.planner import plan

AVAILABILITY = {
    "on_track": {
        "blocks": [
            *[(d, time(18), time(21)) for d in range(4)],
            (5, time(10), time(13)),
            (6, time(14), time(17)),
        ],
        "max_hours": 3, "session": 50, "tz": "America/New_York",
    },
    "slightly_behind": {
        "blocks": [
            *[(d, time(17), time(20)) for d in (0, 2, 4)],
            (6, time(13), time(16)),
        ],
        "max_hours": 2.5, "session": 50, "tz": "America/New_York",
    },
    "badly_behind": {
        "blocks": [(1, time(19), time(20, 30)), (3, time(19), time(20, 30))],
        "max_hours": 1.5, "session": 25, "tz": "America/New_York",
    },
    "extension": {
        "blocks": [(d, time(16), time(19)) for d in range(5)],
        "max_hours": 3, "session": 50, "tz": "America/Chicago",
    },
}  # fmt: skip

DONE_SHARE = {"on_track": 1.0, "extension": 0.9, "slightly_behind": 0.6, "badly_behind": 0.15}


def seed_plans(students: dict) -> None:
    now = timezone.now()
    for profile_name, settings in AVAILABILITY.items():
        student = students[profile_name]
        student.timezone = settings["tz"]
        student.save(update_fields=["timezone"])
        AvailabilityBlock.objects.bulk_create(
            AvailabilityBlock(student=student, weekday=d, start_time=s, end_time=e)
            for d, s, e in settings["blocks"]
        )
        StudentProfile.objects.filter(user=student).update(
            max_hours_per_day=settings["max_hours"],
            session_minutes=settings["session"],
            onboarding_done=True,
        )
        student.refresh_from_db()
        past = plan(student, reason="seed", at=now - timedelta(days=7))
        record_history(past, now, DONE_SHARE[profile_name])
        plan(student, reason="seed")


def record_history(schedule, now, done_share: float) -> None:
    """Mark last week's sessions. Work on items still unsubmitted is only half done."""
    submitted = set(
        Submission.objects.filter(student=schedule.student).values_list("assessment_id", flat=True)
    )
    past = list(schedule.sessions.select_related("task").filter(end__lte=now).order_by("start"))
    for i, session in enumerate(past):
        position = (i + 1) / max(len(past), 1)
        open_item = (
            session.task.source_type == "assessment" and session.task.source_id not in submitted
        )
        if position <= done_share and open_item:
            session.status = Session.Status.PARTIAL
            session.completed_minutes = max(1, session.minutes // 2)
        elif position <= done_share:
            session.status = Session.Status.DONE
            session.completed_minutes = session.minutes
        elif i % 3 == 0:
            session.status = Session.Status.PARTIAL
            session.completed_minutes = max(1, session.minutes // 2)
        else:
            session.status = Session.Status.SKIPPED
        session.save(update_fields=["status", "completed_minutes"])
