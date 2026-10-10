"""Daily streaks: finish one deck a day to keep it going. Missed days use a freeze or reset it."""

from datetime import date, datetime, time, timedelta

from django.db import transaction

from accounts.clock import now as clock_now

from ..models import DailyDeck, Streak, StreakEvent

FREEZE_EVERY = 5
MAX_FREEZES = 2
MILESTONES = (3, 7, 14, 30, 50, 100)
GRACE = timedelta(minutes=15)
AT_RISK_WINDOW = timedelta(hours=4)
BROKEN_RECENTLY = timedelta(days=7)


def get_streak(student) -> Streak:
    return Streak.objects.get_or_create(student=student)[0]


def settled_through(student, now: datetime) -> date:
    """The last local day that is over, allowing the grace period after midnight."""
    return (now - GRACE).astimezone(student.tz).date() - timedelta(days=1)


def _settle(streak: Streak, through: date) -> list[StreakEvent]:
    """Walk the days the streak skipped up to `through`: each one spends a freeze, and the first
    day with no freeze left resets the streak. Callers hold the row lock."""
    events = []
    if streak.current == 0 or streak.last_day is None:
        return events
    day = streak.last_day + timedelta(days=1)
    while day <= through:
        if streak.freezes > 0:
            streak.freezes -= 1
            streak.last_day = day
            result = StreakEvent.Result.FROZEN
        else:
            streak.current = 0
            streak.on_time_toward_freeze = 0
            streak.last_day = None
            result = StreakEvent.Result.MISSED
        events.append(
            StreakEvent.objects.create(
                student_id=streak.student_id, day=day, result=result, streak_after=streak.current
            )
        )
        if result == StreakEvent.Result.MISSED:
            break
        day += timedelta(days=1)
    streak.save()
    return events


@transaction.atomic
def settle(student, now: datetime | None = None) -> list[StreakEvent]:
    """Bring the streak up to date. Safe to call any time; already-settled days are skipped."""
    now = now or clock_now(student)
    streak = Streak.objects.select_for_update().get_or_create(student=student)[0]
    return _settle(streak, settled_through(student, now))


@transaction.atomic
def record_day(deck: DailyDeck) -> tuple[Streak, int | None]:
    """Count a finished deck's day. Returns the streak and a milestone reached, if any."""
    streak = Streak.objects.select_for_update().get_or_create(student=deck.student)[0]
    if StreakEvent.objects.filter(deck=deck).exists():
        return streak, None
    _settle(streak, deck.day - timedelta(days=1))
    if streak.last_day is not None and streak.last_day >= deck.day:
        return streak, None
    streak.current += 1
    streak.longest = max(streak.longest, streak.current)
    streak.last_day = deck.day
    streak.on_time_toward_freeze += 1
    if streak.on_time_toward_freeze >= FREEZE_EVERY:
        streak.on_time_toward_freeze = 0
        streak.freezes = min(MAX_FREEZES, streak.freezes + 1)
    streak.save()
    StreakEvent.objects.create(
        student=deck.student,
        deck=deck,
        day=deck.day,
        result=StreakEvent.Result.ON_TIME,
        streak_after=streak.current,
    )
    return streak, streak.current if streak.current in MILESTONES else None


def done_today(student, now: datetime) -> bool:
    today = now.astimezone(student.tz).date()
    return DailyDeck.objects.filter(student=student, day=today, completed_at__isnull=False).exists()


def at_risk(student, now: datetime) -> timedelta | None:
    """Time left today when there's a streak to lose, today's deck isn't done, and midnight is
    close. None otherwise."""
    streak = Streak.objects.filter(student=student).first()
    if not streak or streak.current == 0:
        return None
    local = now.astimezone(student.tz)
    midnight = datetime.combine(local.date() + timedelta(days=1), time(0), tzinfo=student.tz)
    left = midnight - now
    if left > AT_RISK_WINDOW or done_today(student, now):
        return None
    return left


def streak_component(student, now: datetime) -> tuple[float, list]:
    """Status input: full when the streak is healthy, half when today's deck is still due late in
    the day, zero right after a break. Students who never started a streak get full credit."""
    from pulse.services.status import Reason

    last = StreakEvent.objects.filter(student=student).first()
    if (
        last
        and last.result == StreakEvent.Result.MISSED
        and now - last.created_at <= BROKEN_RECENTLY
    ):
        return 0.0, [Reason(6, "Your daily streak just reset")]
    left = at_risk(student, now)
    if left is not None:
        hours = max(1, round(left.total_seconds() / 3600))
        return 0.5, [Reason(5, f"Today's flashcards aren't done and the day ends in {hours} h")]
    return 1.0, []
