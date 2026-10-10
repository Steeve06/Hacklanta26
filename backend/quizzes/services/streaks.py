"""Streak bookkeeping: consecutive quizzes finished inside their windows."""

from datetime import datetime, timedelta

from django.db import transaction

from accounts.clock import now as clock_now

from ..models import ChapterQuiz, Streak, StreakEvent

FREEZE_EVERY = 5
MAX_FREEZES = 2
MILESTONES = (3, 7, 14, 30, 50, 100)
GRACE = timedelta(minutes=15)
AT_RISK_WINDOW = timedelta(hours=4)
BROKEN_RECENTLY = timedelta(days=7)


def get_streak(student) -> Streak:
    return Streak.objects.get_or_create(student=student)[0]


@transaction.atomic
def record_on_time(quiz: ChapterQuiz) -> tuple[Streak, int | None]:
    """Count a finished quiz. Returns the streak and a milestone reached, if any."""
    streak = Streak.objects.select_for_update().get_or_create(student=quiz.student)[0]
    if StreakEvent.objects.filter(quiz=quiz).exists():
        return streak, None
    streak.current += 1
    streak.longest = max(streak.longest, streak.current)
    streak.on_time_toward_freeze += 1
    if streak.on_time_toward_freeze >= FREEZE_EVERY:
        streak.on_time_toward_freeze = 0
        streak.freezes = min(MAX_FREEZES, streak.freezes + 1)
    streak.save()
    StreakEvent.objects.create(
        student=quiz.student,
        quiz=quiz,
        result=StreakEvent.Result.ON_TIME,
        streak_after=streak.current,
    )
    return streak, streak.current if streak.current in MILESTONES else None


@transaction.atomic
def record_missed(quiz: ChapterQuiz) -> StreakEvent:
    """A window closed without a finished quiz: spend a freeze if there is one, else reset."""
    streak = Streak.objects.select_for_update().get_or_create(student=quiz.student)[0]
    existing = StreakEvent.objects.filter(quiz=quiz).first()
    if existing:
        return existing
    if streak.freezes > 0:
        streak.freezes -= 1
        result = StreakEvent.Result.FROZEN
    else:
        streak.current = 0
        streak.on_time_toward_freeze = 0
        result = StreakEvent.Result.MISSED
    streak.save()
    return StreakEvent.objects.create(
        student=quiz.student, quiz=quiz, result=result, streak_after=streak.current
    )


def sweep_student(student, now: datetime | None = None) -> list[StreakEvent]:
    now = now or clock_now(student)
    events = []
    overdue = ChapterQuiz.objects.filter(
        student=student, resolved=False, closes_at__lt=now - GRACE
    ).exclude(submitted_at__isnull=False, counted_for_streak=True)
    for quiz in overdue:
        event = record_missed(quiz)
        quiz.resolved = True
        quiz.save(update_fields=["resolved", "updated_at"])
        events.append(event)
    return events


def open_quizzes(student, now: datetime):
    return ChapterQuiz.objects.filter(
        student=student, opens_at__lte=now, closes_at__gt=now, submitted_at__isnull=True
    )


def streak_component(student, now: datetime) -> tuple[float, list]:
    """Status input: full when the streak is healthy, half when a quiz is about to close, zero
    right after a break. Students who never had a quiz get full credit."""
    from pulse.services.status import Reason

    last = StreakEvent.objects.filter(student=student).first()
    if (
        last
        and last.result == StreakEvent.Result.MISSED
        and now - last.created_at <= BROKEN_RECENTLY
    ):
        return 0.0, [Reason(6, "Your quiz streak just reset")]
    closing = open_quizzes(student, now).filter(closes_at__lte=now + AT_RISK_WINDOW).first()
    if closing:
        hours = max(1, round((closing.closes_at - now).total_seconds() / 3600))
        return 0.5, [Reason(5, f"A chapter quiz closes in {hours} h and isn't done yet")]
    return 1.0, []
