"""The flashcard library and the daily pick."""

import random
from datetime import date

from ..cards import CARDS
from ..models import CardReview, Flashcard

DECK_SIZE = 5
MAX_REVIEW = 2


def sync_cards(model=Flashcard) -> int:
    """Upsert the built-in cards by slug and retire any that were removed. Returns cards active."""
    slugs = []
    for slug, topic, front, back in CARDS:
        model.objects.update_or_create(
            slug=slug, defaults={"topic": topic, "front": front, "back": back, "active": True}
        )
        slugs.append(slug)
    model.objects.exclude(slug__in=slugs).update(active=False)
    return len(slugs)


def pick(student, day: date, size: int = DECK_SIZE) -> list[int]:
    """Choose a day's cards: a couple the student is still learning, then cards they haven't seen,
    then the ones they saw longest ago. Topics are spread out and the pick is stable per day."""
    rng = random.Random(f"{student.id}:{day.isoformat()}")
    active = list(Flashcard.objects.filter(active=True).values_list("id", "topic"))
    if not active:
        sync_cards()
        active = list(Flashcard.objects.filter(active=True).values_list("id", "topic"))
    topic_of = dict(active)
    latest: dict[int, tuple[date, bool]] = {}
    reviews = (
        CardReview.objects.filter(deck__student=student, deck__day__lt=day)
        .order_by("deck__day")
        .values_list("card_id", "deck__day", "knew")
    )
    for card_id, seen_on, knew in reviews:
        latest[card_id] = (seen_on, knew)

    still_learning = [c for c, (_, knew) in latest.items() if not knew and c in topic_of]
    still_learning.sort(key=lambda c: latest[c][0])
    unseen = [c for c in topic_of if c not in latest]
    rng.shuffle(unseen)
    seen = sorted((c for c in topic_of if c in latest and c not in still_learning),
                  key=lambda c: (latest[c][0], rng.random()))  # fmt: skip

    chosen = still_learning[:MAX_REVIEW]
    for pool in (unseen, seen, still_learning[MAX_REVIEW:]):
        # First pass favours topics not in the deck yet; second pass fills whatever is left.
        for strict in (True, False):
            for card in pool:
                if len(chosen) >= size:
                    return chosen
                if card in chosen:
                    continue
                if strict and topic_of[card] in {topic_of[c] for c in chosen}:
                    continue
                chosen.append(card)
    return chosen
