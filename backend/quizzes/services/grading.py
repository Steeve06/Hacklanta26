"""Lenient checking for typed answers. Adapted from the daily-quiz short answers."""

import re
from difflib import SequenceMatcher

ARTICLES = {"a", "an", "the"}


def normalize(text: str) -> str:
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(w for w in text.split() if w not in ARTICLES)


def close_enough(given: str, expected: str) -> bool:
    """Forgive case, articles, punctuation, a trailing plural and a small typo."""
    a, b = normalize(given), normalize(expected)
    if not a:
        return False
    if a == b or a.rstrip("s") == b.rstrip("s"):
        return True
    return len(b) >= 5 and SequenceMatcher(None, a, b).ratio() >= 0.85
