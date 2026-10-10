"""The flashcard library and a few days of daily-deck history for the demo students."""

import random
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from quizzes.models import CardReview, DailyDeck, Flashcard, Streak, StreakEvent
from quizzes.services.cards import pick, sync_cards
from quizzes.services.focus import choose

from .pulse_seed import AVAILABILITY

STREAKS = {
    "on_track": (6, 9, 1),
    "extension": (4, 4, 0),
    "slightly_behind": (2, 5, 0),
    "badly_behind": (0, 3, 0),
}


def seed_cards() -> int:
    return sync_cards()


def seed_streaks(students: dict) -> None:
    """Each student with a streak finished a deck every day up to yesterday, so today's deck is
    the one that keeps it going."""
    now = timezone.now()
    for profile, (current, longest, freezes) in STREAKS.items():
        student = students[profile]
        tz = ZoneInfo(AVAILABILITY[profile]["tz"])
        today = now.astimezone(tz).date()
        rng = random.Random(profile)
        Streak.objects.update_or_create(
            student=student,
            defaults={
                "current": current,
                "longest": longest,
                "freezes": freezes,
                "on_time_toward_freeze": current % 5,
                "last_day": today - timedelta(days=1) if current else None,
            },  # fmt: skip
        )
        for i in range(current, 0, -1):
            day = today - timedelta(days=i)
            finished = datetime.combine(day, time(20, rng.randrange(60)), tzinfo=tz)
            focus = choose(student, finished)
            deck = DailyDeck.objects.create(
                student=student, day=day, kind=focus.kind, course_id=focus.course_id,
                assessment_id=focus.assessment_id, cards=pick(student, day, focus.pools),
                started_at=finished, completed_at=finished, counted_for_streak=True,
            )  # fmt: skip
            knew = [rng.random() < 0.75 for _ in deck.cards]
            CardReview.objects.bulk_create(
                CardReview(deck=deck, card=Flashcard(pk=c), knew=k)
                for c, k in zip(deck.cards, knew, strict=True)
            )
            deck.knew = sum(knew)
            deck.save(update_fields=["knew"])
            event = StreakEvent.objects.create(
                student=student, deck=deck, day=day, result=StreakEvent.Result.ON_TIME,
                streak_after=current - i + 1,
            )  # fmt: skip
            StreakEvent.objects.filter(pk=event.pk).update(created_at=finished)
        if current == 0:
            day = today - timedelta(days=3)
            event = StreakEvent.objects.create(
                student=student, day=day, result=StreakEvent.Result.MISSED
            )
            StreakEvent.objects.filter(pk=event.pk).update(created_at=now - timedelta(days=2))
