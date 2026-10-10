"""Streak reminders for the notification engine."""

from datetime import datetime

from notifications.candidates import Candidate
from notifications.models import Trigger
from notifications.templates_loader import TIERS

from ..models import DailyDeck
from .decks import day_end, today_deck
from .streaks import at_risk, get_streak


def streak_candidates(student, now: datetime) -> list[Candidate]:
    if at_risk(student, now) is None:
        return []
    deck = today_deck(student, now)
    return [
        Candidate(
            trigger=Trigger.STREAK_AT_RISK,
            tier=TIERS[Trigger.STREAK_AT_RISK],
            source_type="daily_deck",
            source_id=deck.id,
            course_id=None,
            variables={
                "title": "Today's quiz",
                "course": "",
                "streak_days": get_streak(student).current,
            },
            link="/pulse/quiz/today",
            due_at=day_end(student, deck.day),
        )
    ]


def deck_still_open(deck_id: int, now: datetime) -> bool:
    deck = DailyDeck.objects.filter(pk=deck_id).select_related("student").first()
    return bool(deck and deck.completed_at is None and now < day_end(deck.student, deck.day))
