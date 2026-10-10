"""Streak bookkeeping: study checks passed in a row. Days without a check don't count either way;
a check that closes without a pass spends a freeze or resets the streak."""

from datetime import date, datetime, timedelta

from django.db import transaction

from accounts.clock import now as clock_now

from ..models import Streak, StreakEvent, StudyCheck

FREEZE_EVERY = 5
MAX_FREEZES = 2
MILESTONES = (3, 7, 14, 30, 50, 100)
GRACE = timedelta(minutes=15)
AT_RISK_WINDOW = timedelta(hours=4)
BROKEN_RECENTLY = timedelta(days=7)


def get_streak(student) -> Streak:
    return Streak.objects.get_or_create(student=student)[0]


@transaction.atomic
def record_pass(check: StudyCheck) -> tuple[Streak, int | None]:
    """Count a passed check. Returns the streak and a milestone reached, if any."""
    streak = Streak.objects.select_for_update().get_or_create(student=check.student)[0]
    if StreakEvent.objects.filter(study_check=check).exists():
        return streak, None
    streak.current += 1
    streak.longest = max(streak.longest, streak.current)
    streak.on_time_toward_freeze += 1
    if streak.on_time_toward_freeze >= FREEZE_EVERY:
        streak.on_time_toward_freeze = 0
        streak.freezes = min(MAX_FREEZES, streak.freezes + 1)
    streak.save()
    StreakEvent.objects.create(
        student=check.student,
        study_check=check,
        day=check.scheduled_date,
        result=StreakEvent.Result.ON_TIME,
        streak_after=streak.current,
    )
    return streak, streak.current if streak.current in MILESTONES else None


def _spend_freeze_or_reset(streak: Streak) -> str:
    if streak.freezes > 0:
        streak.freezes -= 1
        return StreakEvent.Result.FROZEN
    streak.current = 0
    streak.on_time_toward_freeze = 0
    return StreakEvent.Result.MISSED


@transaction.atomic
def record_missed(check: StudyCheck) -> StreakEvent:
    """A check closed (or ran out of tries) without a pass: spend a freeze, else reset."""
    streak = Streak.objects.select_for_update().get_or_create(student=check.student)[0]
    existing = StreakEvent.objects.filter(study_check=check).first()
    if existing:
        return existing
    result = _spend_freeze_or_reset(streak)
    streak.save()
    StudyCheck.objects.filter(pk=check.pk).update(resolved=True)
    return StreakEvent.objects.create(
        student=check.student,
        study_check=check,
        day=check.scheduled_date,
        result=result,
        streak_after=streak.current,
    )


@transaction.atomic
def record_missed_deadline(student, assessment_id: int, day: date) -> StreakEvent | None:
    """Coursework that passed its due date without a submission counts like a missed check,
    once per assessment. Returns None if it was already counted."""
    streak = Streak.objects.select_for_update().get_or_create(student=student)[0]
    if StreakEvent.objects.filter(student=student, assessment_id=assessment_id).exists():
        return None
    result = _spend_freeze_or_reset(streak)
    streak.save()
    return StreakEvent.objects.create(
        student=student, assessment_id=assessment_id, day=day, result=result,
        streak_after=streak.current,
    )  # fmt: skip


def sweep_student(student, now: datetime | None = None) -> list[StreakEvent]:
    """Settle checks whose window (plus the grace period) is over without a pass, and deadlines
    that passed without a submission."""
    from .missed import missed_deadlines

    now = now or clock_now(student)
    overdue = StudyCheck.objects.filter(
        student=student, resolved=False, passed=False, closes_at__lt=now - GRACE
    )
    events = [record_missed(check) for check in overdue]
    for row in missed_deadlines(student, now):
        day = row["due_at"].astimezone(student.tz).date()
        event = record_missed_deadline(student, row["assessment_id"], day)
        if event:
            events.append(event)
    return events


def open_checks(student, now: datetime):
    return StudyCheck.objects.filter(
        student=student, opens_at__lte=now, closes_at__gt=now, passed=False, resolved=False
    )


def week_of(student, now: datetime) -> list[dict]:
    """The last seven local days, oldest first, with what happened to that day's checks."""
    today = now.astimezone(student.tz).date()
    first = today - timedelta(days=6)
    results: dict[date, str] = {}
    events = StreakEvent.objects.filter(
        student=student, day__gte=first, day__lte=today
    ).values_list("day", "result")
    rank = {"missed": 1, "frozen": 2, "done": 3}
    for day, result in events:
        label = "done" if result == StreakEvent.Result.ON_TIME else result
        if rank[label] > rank.get(results.get(day, ""), 0):
            results[day] = label
    for day in open_checks(student, now).values_list("scheduled_date", flat=True):
        results.setdefault(day, "open")
    return [
        {"day": first + timedelta(days=i), "result": results.get(first + timedelta(days=i), "none")}
        for i in range(7)
    ]


def streak_component(student, now: datetime) -> tuple[float, list]:
    """Status input: full when the streak is healthy, half when a check is about to close, zero
    right after a break. Students who never had a check get full credit."""
    from pulse.services.status import Reason

    last = StreakEvent.objects.filter(student=student).first()
    if (
        last
        and last.result == StreakEvent.Result.MISSED
        and now - last.created_at <= BROKEN_RECENTLY
    ):
        return 0.0, [Reason(6, "Your study streak just reset")]
    closing = open_checks(student, now).filter(closes_at__lte=now + AT_RISK_WINDOW).first()
    if closing:
        hours = max(1, round((closing.closes_at - now).total_seconds() / 3600))
        return 0.5, [Reason(5, f"A study check closes in {hours} h and isn't done yet")]
    return 1.0, []
