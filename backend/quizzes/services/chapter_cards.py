"""Course flashcards built from a chapter's own text: each bold key term becomes a fill-in-the-blank
card on the sentence that introduces it. Deterministic, so it needs no model call."""

import hashlib
import re

from django.db import transaction

from lms.models import Chapter

from ..models import Flashcard

MAX_PER_CHAPTER = 12
BOLD = re.compile(r"\*\*([^*]{3,60})\*\*")
LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def _plain(text: str) -> str:
    return re.sub(r"\*\*|\*|`", "", LINK.sub(r"\1", text)).strip()


def _sentences(markdown: str) -> list[str]:
    body = "\n".join(
        re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", line)
        for line in markdown.splitlines()
        if not line.lstrip().startswith(("#", "|", "```"))
    )
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", body))
    return [p.strip() for p in parts if 30 <= len(p.strip()) <= 280]


def _useful(term: str) -> bool:
    """Skip emphasis that isn't a key term, like **fast**, and bold lead-ins such as
    **Use concrete words.** that start a paragraph."""
    if term[-1] in ".,:;!?":
        return False
    return len(term.split()) > 1 or len(term) >= 6 or (len(term) >= 4 and term[0].isupper())


def build(chapter: Chapter) -> list[tuple[str, str, str]]:
    """(slug, front, back) for each key term, in reading order."""
    cards = []
    seen: set[str] = set()
    for sentence in _sentences(chapter.body_md):
        for match in BOLD.finditer(sentence):
            term = match.group(1).strip()
            key = term.lower()
            if key in seen or not _useful(term):
                continue
            seen.add(key)
            blanked = _plain(sentence.replace(match.group(0), "_____", 1))
            if "_____" not in blanked:
                continue
            digest = hashlib.sha1(f"{key}|{blanked}".encode()).hexdigest()[:10]
            back = f"{term[0].upper()}{term[1:]}\n\n{_plain(sentence)}"
            cards.append((f"ch{chapter.id}-{digest}", f"Fill in the blank: {blanked}", back))
            break
        if len(cards) >= MAX_PER_CHAPTER:
            break
    return cards


@transaction.atomic
def ensure(chapter: Chapter) -> list[int]:
    """Active card ids for the chapter's current text, building them on first use. Cards from an
    older version of the chapter are retired, not deleted, so past decks still read."""
    current = list(
        Flashcard.objects.filter(
            chapter=chapter, content_hash=chapter.content_hash, active=True
        ).values_list("id", flat=True)
    )
    if current:
        return current
    Flashcard.objects.filter(chapter=chapter).update(active=False)
    ids = []
    for slug, front, back in build(chapter):
        card, _ = Flashcard.objects.update_or_create(
            slug=slug,
            defaults={
                "chapter": chapter, "content_hash": chapter.content_hash,
                "topic": Flashcard.Topic.COURSE, "front": front[:300], "back": back,
                "active": True,
            },
        )  # fmt: skip
        ids.append(card.id)
    return ids
