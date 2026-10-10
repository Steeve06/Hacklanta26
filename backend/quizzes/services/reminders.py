"""Streak reminders for the notification engine."""

from datetime import datetime

from notifications.candidates import Candidate
from notifications.models import Trigger
from notifications.templates_loader import TIERS

from ..models import StudyCheck
from .streaks import AT_RISK_WINDOW, get_streak, open_checks


def check_title(check: StudyCheck) -> str:
    chapters = list(check.chapters.select_related("course").order_by("course__code", "order"))
    return ", ".join(f"{c.course.code} Ch {c.order}" for c in chapters) or "Study check"


def streak_candidates(student, now: datetime) -> list[Candidate]:
    streak = get_streak(student)
    found = []
    for check in open_checks(student, now).filter(closes_at__lte=now + AT_RISK_WINDOW):
        first = check.chapters.select_related("course").first()
        found.append(
            Candidate(
                trigger=Trigger.STREAK_AT_RISK,
                tier=TIERS[Trigger.STREAK_AT_RISK],
                source_type="study_check",
                source_id=check.id,
                course_id=first.course_id if first else None,
                variables={
                    "title": check_title(check),
                    "course": first.course.code if first else "",
                    "streak_days": streak.current,
                },
                link=f"/pulse/checks/{check.id}",
                due_at=check.closes_at,
            )
        )
    return found


def check_still_open(check_id: int, now: datetime) -> bool:
    check = StudyCheck.objects.filter(pk=check_id).first()
    return bool(check and not check.passed and not check.resolved and check.closes_at > now)
