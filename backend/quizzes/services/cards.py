"""The general flashcard library and the daily pick."""

import random
from datetime import date

from ..cards import CARDS
from ..models import CardReview, Flashcard

DECK_SIZE = 5
MAX_REVIEW = 2


def sync_cards(model=Flashcard) -> int:
    """Upsert the built-in general cards by slug and retire any that were removed. Course cards
    are left alone. Returns the number of general cards."""
    slugs = []
    for slug, topic, front, back in CARDS:
        model.objects.update_or_create(
            slug=slug, defaults={"topic": topic, "front": front, "back": back, "active": True}
        )
        slugs.append(slug)
    model.objects.filter(chapter__isnull=True).exclude(slug__in=slugs).update(active=False)
    return len(slugs)


def general_ids() -> list[int]:
    ids = list(
        Flashcard.objects.filter(chapter__isnull=True, active=True).values_list("id", flat=True)
    )
    if not ids:
        sync_cards()
        ids = list(
            Flashcard.objects.filter(chapter__isnull=True, active=True).values_list("id", flat=True)
        )
    return ids


def pick(
    student, day: date, pools: list[list[int]] | None = None, size: int = DECK_SIZE
) -> list[int]:
    """Choose a day's cards from `pools`, in priority order (general cards by default). Within the
    pools: a couple the student is still learning, then cards they haven't seen, then the ones they
    saw longest ago. Chapters or topics are spread out, and the pick is stable per day."""
    pools = pools if pools is not None else [general_ids()]
    rng = random.Random(f"{student.id}:{day.isoformat()}")
    every = {c for pool in pools for c in pool}
    group = {
        card_id: chapter_id or topic
        for card_id, chapter_id, topic in Flashcard.objects.filter(id__in=every).values_list(
            "id", "chapter_id", "topic"
        )
    }
    latest: dict[int, tuple[date, bool]] = {}
    seen_at: dict[int, int] = {}
    reviews = (
        CardReview.objects.filter(deck__student=student, deck__day__lt=day, card_id__in=every)
        .order_by("deck__day", "id")
        .values_list("card_id", "deck__day", "knew")
    )
    for position, (card_id, seen_on, knew) in enumerate(reviews):
        latest[card_id] = (seen_on, knew)
        seen_at[card_id] = position

    chosen: list[int] = []
    for pool in pools:
        # Databases return ids in no fixed order; sort so the day's pick is the same every time.
        pool = sorted(c for c in pool if c in group and c not in chosen)
        learning = sorted((c for c in pool if c in latest and not latest[c][1]),
                          key=lambda c: seen_at[c])  # fmt: skip
        unseen = [c for c in pool if c not in latest]
        rng.shuffle(unseen)
        seen = sorted((c for c in pool if c in latest and latest[c][1]),
                      key=lambda c: (latest[c][0], rng.random()))  # fmt: skip
        budget = max(0, MAX_REVIEW - sum(1 for c in chosen if c in latest and not latest[c][1]))
        chosen += learning[:budget]
        for ordered in (unseen, seen, learning[budget:]):
            # First pass spreads chapters (or topics); second pass fills whatever is left.
            for strict in (True, False):
                for card in ordered:
                    if len(chosen) >= size:
                        return chosen
                    if card in chosen:
                        continue
                    if strict and group[card] in {group[c] for c in chosen}:
                        continue
                    chosen.append(card)
    return chosen
