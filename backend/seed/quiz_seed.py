"""Question banks for every chapter and some streak history for the demo students."""

from datetime import timedelta

from django.utils import timezone

from lms.models import Chapter
from quizzes.models import Streak, StreakEvent
from quizzes.services.bank import rebuild_bank

STREAKS = {
    "on_track": (6, 9, 1),
    "extension": (4, 4, 0),
    "slightly_behind": (2, 5, 0),
    "badly_behind": (0, 3, 0),
}


def seed_banks() -> int:
    return sum(rebuild_bank(chapter) for chapter in Chapter.objects.all())


def seed_streaks(students: dict) -> None:
    now = timezone.now()
    for profile, (current, longest, freezes) in STREAKS.items():
        student = students[profile]
        Streak.objects.update_or_create(
            student=student,
            defaults={
                "current": current,
                "longest": longest,
                "freezes": freezes,
                "on_time_toward_freeze": current % 5,
            },  # fmt: skip
        )
        for i in range(current):
            event = StreakEvent.objects.create(
                student=student, result=StreakEvent.Result.ON_TIME, streak_after=current - i
            )
            StreakEvent.objects.filter(pk=event.pk).update(
                created_at=now - timedelta(days=2 * i + 1)
            )
        if current == 0:
            event = StreakEvent.objects.create(student=student, result=StreakEvent.Result.MISSED)
            StreakEvent.objects.filter(pk=event.pk).update(created_at=now - timedelta(days=3))
