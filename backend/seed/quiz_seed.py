"""The flashcard library and a few days of quiz-session history for the demo students and their
classmates, so streaks and the leaderboard have something to show."""

import random
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from quizzes.models import CardReview, DailyDeck, DeckAnswer, Flashcard, Streak, StreakEvent
from quizzes.services import items as item_service
from quizzes.services.cards import pick, sync_cards
from quizzes.services.decks import session_size
from quizzes.services.focus import choose

from .pulse_seed import AVAILABILITY

STREAKS = {
    "on_track": (6, 9, 1),
    "extension": (4, 4, 0),
    "slightly_behind": (2, 5, 0),
    "badly_behind": (0, 3, 0),
}
# Classmates have already done today's session, so the leaderboard is lively on any day.
CLASSMATE_STREAKS = {"Priya": 12, "Tomás": 3, "Hannah": 8, "Kwame": 1}
SKILL = {"Priya": 0.9, "Tomás": 0.6, "Hannah": 0.8, "Kwame": 0.5}


def seed_cards() -> int:
    return sync_cards()


def _response(item: dict, correct: bool, cards: dict[int, Flashcard], rng) -> dict:
    kind = item["type"]
    if kind == "flashcard":
        return {"knew": correct}
    if kind == "short":
        return {"text": cards[item["card"]].answer if correct else "not sure"}
    if kind == "mcq":
        card = cards[item["card"]]
        right = item["options"].index(card.answer or card.back)
        return {"choice": right if correct else (right + 1) % len(item["options"])}
    pairs = [item["clues"].index(c) for c in item["cards"]]
    return {"pairs": pairs if correct else pairs[1:] + pairs[:1]}


def finished_session(student, day, finished: datetime, skill: float, rng) -> DailyDeck:
    """A session done on `day`, answered about as well as `skill`, counted for the streak."""
    focus = choose(student, finished)
    questions, seconds = session_size(focus)
    cards = pick(student, day, focus.pools, size=item_service.cards_needed(questions))
    plan = item_service.build(cards, questions, rng)
    deck = DailyDeck.objects.create(
        student=student, day=day, kind=focus.kind, course_id=focus.course_id,
        assessment_id=focus.assessment_id, cards=cards, items=plan, time_limit_seconds=seconds,
        started_at=finished - timedelta(seconds=seconds - 20), completed_at=finished,
        counted_for_streak=True,
    )  # fmt: skip
    by_id = {c.id: c for c in Flashcard.objects.filter(id__in=cards)}
    right = 0
    for position, item in enumerate(plan):
        response = _response(item, rng.random() < skill, by_id, rng)
        correct, per_card = item_service.grade(item, response, by_id)
        right += correct
        DeckAnswer.objects.create(deck=deck, position=position, response=response, correct=correct)
        CardReview.objects.bulk_create(
            CardReview(deck=deck, card_id=c, knew=k) for c, k in per_card.items()
        )
    deck.knew = right
    deck.xp = right * item_service.XP_PER_CORRECT + item_service.XP_FOR_FINISHING
    deck.save(update_fields=["knew", "xp"])
    return deck


def _history(student, tz, days: list, current: int, longest: int, freezes: int, skill, rng):
    for i, day in enumerate(days, start=1):
        finished = datetime.combine(day, time(20, rng.randrange(60)), tzinfo=tz)
        finished = min(finished, timezone.now() - timedelta(minutes=30))
        deck = finished_session(student, day, finished, skill, rng)
        event = StreakEvent.objects.create(
            student=student, deck=deck, day=day, result=StreakEvent.Result.ON_TIME,
            streak_after=current - len(days) + i,
        )  # fmt: skip
        StreakEvent.objects.filter(pk=event.pk).update(created_at=finished)
    Streak.objects.update_or_create(
        student=student,
        defaults={
            "current": current, "longest": max(longest, current), "freezes": freezes,
            "on_time_toward_freeze": current % 5, "last_day": days[-1] if days else None,
        },
    )  # fmt: skip


def seed_streaks(students: dict, classmates: list | None = None) -> None:
    """Demo students finished a session every day up to yesterday, so today's session is the one
    that keeps the streak going. Classmates have done today's already."""
    now = timezone.now()
    for profile, (current, longest, freezes) in STREAKS.items():
        student = students[profile]
        tz = ZoneInfo(AVAILABILITY[profile]["tz"])
        today = now.astimezone(tz).date()
        days = [today - timedelta(days=i) for i in range(current, 0, -1)]
        _history(student, tz, days, current, longest, freezes, 0.75, random.Random(profile))
        if current == 0:
            event = StreakEvent.objects.create(
                student=student, day=today - timedelta(days=3), result=StreakEvent.Result.MISSED
            )
            StreakEvent.objects.filter(pk=event.pk).update(created_at=now - timedelta(days=2))
    for classmate in classmates or []:
        current = CLASSMATE_STREAKS.get(classmate.first_name, 2)
        tz = classmate.tz
        today = now.astimezone(tz).date()
        days = [today - timedelta(days=i) for i in range(current - 1, -1, -1)]
        if now.astimezone(tz).hour < 1:
            days = days[:-1]  # too early in the day to have done today's
        rng = random.Random(classmate.email)
        _history(classmate, tz, days, len(days), len(days), min(2, len(days) // 5),
                 SKILL.get(classmate.first_name, 0.7), rng)  # fmt: skip
