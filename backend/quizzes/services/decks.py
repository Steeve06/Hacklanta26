"""Today's deck: create it on first visit, record a card at a time, finish it to count the day."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from accounts.clock import now as clock_now

from ..models import CardReview, DailyDeck, Flashcard
from .cards import pick
from .streaks import GRACE, record_day


@dataclass
class ReviewOutcome:
    deck: DailyDeck
    milestone: int | None


def local_day(student, moment: datetime) -> date:
    return moment.astimezone(student.tz).date()


def day_end(student, day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time(0), tzinfo=student.tz)


def today_deck(student, now: datetime | None = None) -> DailyDeck:
    day = local_day(student, now or clock_now(student))
    deck = DailyDeck.objects.filter(student=student, day=day).first()
    if deck:
        return deck
    try:
        with transaction.atomic():
            return DailyDeck.objects.create(student=student, day=day, cards=pick(student, day))
    except IntegrityError:
        return DailyDeck.objects.get(student=student, day=day)


def state_of(deck: DailyDeck, now: datetime) -> str:
    if deck.completed_at:
        return "done"
    if now < day_end(deck.student, deck.day):
        return "open"
    return "closed"


def counts_for_streak(deck: DailyDeck, finished_at: datetime) -> bool:
    """A deck counts on its own day, or just after midnight if the student started it in time."""
    end = day_end(deck.student, deck.day)
    if finished_at < end:
        return True
    started_in_time = deck.started_at is not None and deck.started_at < end
    return started_in_time and finished_at <= end + GRACE


def review(deck: DailyDeck, card_id: int, knew: bool) -> ReviewOutcome:
    """Record how one card went. Re-rating a card is ignored, and so is anything after the deck
    is finished. The last card finishes the deck and, if it's on time, extends the streak."""
    with transaction.atomic():
        deck = DailyDeck.objects.select_for_update().get(pk=deck.pk)
        if deck.completed_at is not None:
            return ReviewOutcome(deck, None)
        if card_id not in deck.cards:
            raise ValidationError("That card isn't in this deck.")
        now = clock_now(deck.student)
        if deck.started_at is None:
            deck.started_at = now
        card = Flashcard.objects.get(pk=card_id)
        CardReview.objects.get_or_create(deck=deck, card=card, defaults={"knew": knew})
        reviews = dict(deck.reviews.values_list("card_id", "knew"))
        if all(c in reviews for c in deck.cards):
            deck.completed_at = now
            deck.knew = sum(1 for c in deck.cards if reviews[c])
            deck.counted_for_streak = counts_for_streak(deck, now)
        deck.save()
    milestone = None
    if deck.counted_for_streak:
        _, milestone = record_day(deck)
    return ReviewOutcome(deck, milestone)
