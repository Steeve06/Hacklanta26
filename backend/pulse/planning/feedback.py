"""Turn short regenerate feedback ("less on weekends") into solver preferences."""

import re

DAYS = {
    "monday": [0], "tuesday": [1], "wednesday": [2], "thursday": [3], "friday": [4],
    "saturday": [5], "sunday": [6], "weekend": [5, 6], "weekday": [0, 1, 2, 3, 4],
    "weeknight": [0, 1, 2, 3, 4],
}  # fmt: skip
LESS = r"(less|fewer|lighter|not much|avoid|no|nothing|free|off)"
MORE = r"(more|heavier|extra)"


def parse_feedback(text: str) -> tuple[dict[int, float], tuple[int, int] | None]:
    text = text.lower()
    factors: dict[int, float] = {}
    for word, days in DAYS.items():
        pattern = rf"\b{word}s?\b"
        if not re.search(pattern, text):
            continue
        if re.search(
            rf"\b(no|nothing|free|off|avoid)\b[^.,;]*{pattern}|{pattern}[^.,;]*\b(off|free)\b", text
        ):
            factor = 0.0
        elif re.search(rf"\b{LESS}\b[^.,;]*{pattern}", text):
            factor = 0.5
        elif re.search(rf"\b{MORE}\b[^.,;]*{pattern}", text):
            factor = 1.0
        else:
            continue
        for day in days:
            factors[day] = min(factors.get(day, 1.0), factor)
    hours = None
    if re.search(r"\bmornings?\b|\bearl(y|ier)\b", text):
        hours = (6, 12)
    elif re.search(r"\bafternoons?\b", text):
        hours = (12, 17)
    elif re.search(r"\bevenings?\b|\bnights?\b|\blater\b", text):
        hours = (17, 23)
    return factors, hours
