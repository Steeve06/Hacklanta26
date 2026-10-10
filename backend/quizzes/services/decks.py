"""Today's quiz session: built on first visit, timed once started, finished when every question
is answered or the clock runs out. A finished session counts its day toward the streak."""

import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from accounts.clock import now as clock_now

from ..models import CardReview, DailyDeck, DeckAnswer, Flashcard
from . import items as item_service
from .cards import pick
from .focus import choose
from .streaks import GRACE, record_day

REGULAR = (5, 180)  # questions, seconds
QUIZ_PREP = (8, 300)  # never more than five minutes
LATE_ANSWER_GRACE = timedelta(seconds=10)


@dataclass
class AnswerOutcome:
    deck: DailyDeck
    milestone: int | None


def local_day(student, moment: datetime) -> date:
    return moment.astimezone(student.tz).date()


def day_end(student, day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time(0), tzinfo=student.tz)


def session_size(focus) -> tuple[int, int]:
    """Three minutes normally; a longer (but at most five-minute) session before a quiz."""
    if focus.kind == DailyDeck.Kind.UPCOMING and focus.assessment_type == "quiz":
        return QUIZ_PREP
    return REGULAR


def build_deck(student, day: date, now: datetime) -> DailyDeck:
    focus = choose(student, now)
    questions, seconds = session_size(focus)
    cards = pick(student, day, focus.pools, size=item_service.cards_needed(questions))
    rng = random.Random(f"{student.id}:{day.isoformat()}:items")
    return DailyDeck.objects.create(
        student=student, day=day, kind=focus.kind, course_id=focus.course_id,
        assessment_id=focus.assessment_id, cards=cards, time_limit_seconds=seconds,
        items=item_service.build(cards, questions, rng),
    )  # fmt: skip


def today_deck(student, now: datetime | None = None) -> DailyDeck:
    """Today's session, built on first visit around what's coming up, then fixed for the day."""
    now = now or clock_now(student)
    day = local_day(student, now)
    deck = DailyDeck.objects.filter(student=student, day=day).first()
    if deck and not deck.items and deck.started_at is None:
        deck.delete()  # an untouched deck from before sessions had questions: rebuild it
    elif deck:
        return deck
    try:
        with transaction.atomic():
            return build_deck(student, day, now)
    except IntegrityError:
        return DailyDeck.objects.get(student=student, day=day)


def deadline(deck: DailyDeck) -> datetime | None:
    if deck.started_at is None:
        return None
    return deck.started_at + timedelta(seconds=deck.time_limit_seconds)


def state_of(deck: DailyDeck, now: datetime) -> str:
    if deck.completed_at:
        return "done"
    if now < day_end(deck.student, deck.day):
        return "open"
    return "closed"


def counts_for_streak(deck: DailyDeck, finished_at: datetime) -> bool:
    """A session counts on its own day, or just after midnight if it was started in time."""
    end = day_end(deck.student, deck.day)
    if finished_at < end:
        return True
    started_in_time = deck.started_at is not None and deck.started_at < end
    return started_in_time and finished_at <= end + GRACE


def start(deck: DailyDeck) -> DailyDeck:
    """Start the clock. Starting again does nothing."""
    if deck.started_at is None and deck.completed_at is None:
        DailyDeck.objects.filter(pk=deck.pk, started_at__isnull=True).update(
            started_at=clock_now(deck.student)
        )
        deck.refresh_from_db()
    return deck


def _finish(deck: DailyDeck, now: datetime) -> None:
    """Close a locked deck. Unanswered questions count as wrong; at least one answer is needed
    for the day to count."""
    answers = list(deck.answers.all())
    deck.completed_at = now
    deck.knew = sum(1 for a in answers if a.correct)
    deck.counted_for_streak = bool(answers) and counts_for_streak(deck, now)
    deck.xp = deck.knew * item_service.XP_PER_CORRECT + (
        item_service.XP_FOR_FINISHING if deck.counted_for_streak else 0
    )
    deck.save()


def _after_finish(deck: DailyDeck) -> int | None:
    if deck.counted_for_streak:
        return record_day(deck)[1]
    return None


def expire_if_due(deck: DailyDeck) -> AnswerOutcome:
    """Finish a session whose clock ran out while the student was away."""
    end = deadline(deck)
    if deck.completed_at or end is None:
        return AnswerOutcome(deck, None)
    now = clock_now(deck.student)
    if now <= end + LATE_ANSWER_GRACE:
        return AnswerOutcome(deck, None)
    with transaction.atomic():
        deck = DailyDeck.objects.select_for_update().get(pk=deck.pk)
        if deck.completed_at:
            return AnswerOutcome(deck, None)
        # Close it as of the deadline, so a late visit can't make it count for a later day.
        _finish(deck, end)
    return AnswerOutcome(deck, _after_finish(deck))


def answer(deck: DailyDeck, position: int, response: dict) -> AnswerOutcome:
    """Grade one question. Answering again is ignored, and so is anything after the session is
    finished. The last answer finishes the session."""
    outcome = expire_if_due(deck)
    if outcome.deck.completed_at:
        # Time ran out (or it was already finished): the answer is dropped, the result stands.
        return outcome
    with transaction.atomic():
        deck = DailyDeck.objects.select_for_update().get(pk=deck.pk)
        if deck.completed_at is not None:
            return AnswerOutcome(deck, None)
        if deck.started_at is None:
            raise ValidationError("Start the session first.")
        if not 0 <= position < len(deck.items):
            raise ValidationError("That question isn't in this session.")
        now = clock_now(deck.student)
        if not DeckAnswer.objects.filter(deck=deck, position=position).exists():
            item = deck.items[position]
            cards = {
                c.id: c for c in Flashcard.objects.filter(id__in=item_service.item_cards(item))
            }
            correct, per_card = item_service.grade(item, response, cards)
            DeckAnswer.objects.create(
                deck=deck, position=position, response=response, correct=correct
            )
            for card_id, knew in per_card.items():
                CardReview.objects.get_or_create(
                    deck=deck, card_id=card_id, defaults={"knew": knew}
                )
        if deck.answers.count() >= len(deck.items):
            _finish(deck, now)
    return AnswerOutcome(deck, _after_finish(deck) if deck.completed_at else None)


def finish(deck: DailyDeck) -> AnswerOutcome:
    """Finish when every question is answered or the time is up; not before."""
    outcome = expire_if_due(deck)
    if outcome.deck.completed_at:
        return outcome
    deck = outcome.deck
    end = deadline(deck)
    if end is None:
        raise ValidationError("Start the session first.")
    now = clock_now(deck.student)
    if now < end and deck.answers.count() < len(deck.items):
        raise ValidationError("Answer every question, or keep going until the time is up.")
    with transaction.atomic():
        deck = DailyDeck.objects.select_for_update().get(pk=deck.pk)
        if deck.completed_at:
            return AnswerOutcome(deck, None)
        _finish(deck, min(now, end))
    return AnswerOutcome(deck, _after_finish(deck))
