"""Turn a deck's cards into a mix of question types and grade the answers.

Item shapes, stored in DailyDeck.items:
  {"type": "flashcard", "card": id}                      self-rated: flip, then "Got it" or not
  {"type": "mcq", "card": id, "options": [str, ...]}     pick the right term (or answer)
  {"type": "short", "card": id}                          type the missing term
  {"type": "match", "cards": [id, ...], "clues": [id, ...]}  pair each term with its sentence

Course cards have a short answer (the key term), so they can be any type. General library cards
only have a long answer, so they are flashcards or multiple choice.
"""

import random
import re
from difflib import SequenceMatcher

from rest_framework.exceptions import ValidationError

from ..models import Flashcard

MATCH_PAIRS = 3
COURSE_ROTATION = ("mcq", "short", "flashcard")
GENERAL_ROTATION = ("mcq", "flashcard")
XP_PER_CORRECT = 10
XP_FOR_FINISHING = 20


def cards_needed(items: int) -> int:
    """A matching item uses several cards, so a deck of `items` questions needs a few extra."""
    return items + MATCH_PAIRS - 1


def _distractors(card: Flashcard, rng: random.Random, pool: list[Flashcard]) -> list[str]:
    """Three wrong options from the same chapter's course (or the general library)."""
    if card.answer:
        candidates = Flashcard.objects.filter(
            chapter__course_id=card.chapter.course_id, active=True
        ).exclude(answer="")
        options = {c.answer for c in candidates} | {c.answer for c in pool if c.answer}
        options = [o for o in options if o.lower() != card.answer.lower()]
    else:
        options = [c.back for c in pool if not c.answer and c.id != card.id]
        if len(options) < 3:
            others = Flashcard.objects.filter(chapter__isnull=True, active=True).exclude(pk=card.pk)
            options += [c.back for c in others[:20]]
    options = sorted(set(options))
    rng.shuffle(options)
    return options[:3]


def build(card_ids: list[int], items: int, rng: random.Random) -> list[dict]:
    """Up to `items` questions from the picked cards, in the picked order. One matching question
    appears when there are enough course cards; the rest rotate through the other types."""
    cards = {c.id: c for c in Flashcard.objects.filter(id__in=card_ids).select_related("chapter")}
    ordered = [cards[c] for c in card_ids if c in cards]
    course = [c for c in ordered if c.answer]
    plan: list[dict] = []
    used: set[int] = set()
    match_at = None
    if len(course) >= MATCH_PAIRS and items >= 3:
        group = course[-MATCH_PAIRS:]
        clues = [c.id for c in group]
        rng.shuffle(clues)
        match_item = {"type": "match", "cards": [c.id for c in group], "clues": clues}
        used |= {c.id for c in group}
        match_at = min(len(ordered), items) // 2
    turn = {True: 0, False: 0}
    for card in ordered:
        if len(plan) >= items - (1 if match_at is not None else 0):
            break
        if card.id in used:
            continue
        rotation = COURSE_ROTATION if card.answer else GENERAL_ROTATION
        kind = rotation[turn[bool(card.answer)] % len(rotation)]
        turn[bool(card.answer)] += 1
        item: dict = {"type": kind, "card": card.id}
        if kind == "mcq":
            wrong = _distractors(card, rng, ordered)
            if len(wrong) < 3:
                item = {"type": "flashcard", "card": card.id}
            else:
                right = card.answer or card.back
                options = [right, *wrong]
                rng.shuffle(options)
                item["options"] = options
        plan.append(item)
        used.add(card.id)
    if match_at is not None:
        plan.insert(min(match_at, len(plan)), match_item)
    return plan


def item_cards(item: dict) -> list[int]:
    return item["cards"] if item["type"] == "match" else [item["card"]]


def normalize(text: str) -> str:
    text = re.sub(r"[^\w\s]", " ", text.lower())
    words = [w for w in text.split() if w not in {"a", "an", "the"}]
    return " ".join(words)


def close_enough(given: str, expected: str) -> bool:
    """Forgive case, articles, punctuation, plurals and a small typo."""
    a, b = normalize(given), normalize(expected)
    if not a:
        return False
    if a == b or a.rstrip("s") == b.rstrip("s"):
        return True
    return len(b) >= 5 and SequenceMatcher(None, a, b).ratio() >= 0.85


def grade(item: dict, response: dict, cards: dict[int, Flashcard]) -> tuple[bool, dict[int, bool]]:
    """Whether the item is right overall, and per card (for spaced repetition)."""
    kind = item["type"]
    if kind == "flashcard":
        knew = response.get("knew")
        if not isinstance(knew, bool):
            raise ValidationError("Say whether you knew it.")
        return knew, {item["card"]: knew}
    if kind == "mcq":
        choice = response.get("choice")
        if not isinstance(choice, int) or not 0 <= choice < len(item["options"]):
            raise ValidationError("Pick one of the options.")
        card = cards[item["card"]]
        right = item["options"][choice] == (card.answer or card.back)
        return right, {card.id: right}
    if kind == "short":
        text = response.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("Type an answer.")
        card = cards[item["card"]]
        right = close_enough(text[:120], card.answer)
        return right, {card.id: right}
    if kind == "match":
        pairs = response.get("pairs")
        n = len(item["cards"])
        if not isinstance(pairs, list) or len(pairs) != n or sorted(pairs) != list(range(n)):
            raise ValidationError("Match every term to one sentence.")
        per_card = {
            card_id: item["clues"][pairs[i]] == card_id for i, card_id in enumerate(item["cards"])
        }
        return all(per_card.values()), per_card
    raise ValidationError("Unknown question type.")


def solution(item: dict, cards: dict[int, Flashcard]) -> dict:
    """What the student sees after answering."""
    if item["type"] == "match":
        return {"pairs": [item["clues"].index(c) for c in item["cards"]]}
    card = cards[item["card"]]
    # course cards' backs are "Term\n\nthe full sentence"; the sentence alone explains the answer
    explanation = card.back.split("\n\n", 1)[-1] if card.answer else card.back
    out: dict = {"answer": card.answer or card.back, "explanation": explanation}
    if item["type"] == "mcq":
        out["choice"] = item["options"].index(card.answer or card.back)
    return out
