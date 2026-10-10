"""Rules no notification may break, whoever or whatever wrote it."""

import re
import string

from .copy import BLOCKLIST

_PATTERNS = [re.compile(rf"\b{re.escape(term.strip())}\b", re.IGNORECASE) for term in BLOCKLIST]
SCORE_PATTERN = re.compile(
    r"\b\d+(\.\d+)?\s*(/|out of)\s*\d+|\bscored?\b|\bgrade(d)? (of|was)\b", re.IGNORECASE
)


def banned_terms(text: str) -> list[str]:
    return [p.pattern for p in _PATTERNS if p.search(text)]


def is_safe(text: str) -> bool:
    return not banned_terms(text) and not SCORE_PATTERN.search(text)


def placeholders(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}
