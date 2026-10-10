"""Explain work that does not fit before its deadline, and what would fix it."""

import math
from collections import defaultdict
from datetime import timedelta

from ..planning.inventory import Inventory
from ..planning.types import Constraints, SolveResult, TaskSpec

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def build_overload_report(
    specs: list[TaskSpec],
    result: SolveResult,
    free: dict,
    constraints: Constraints,
    inventory: Inventory,
    *,
    blocks_exist: bool,
) -> dict | None:
    by_key = {s.key: s for s in specs}
    item_titles = {(i.source_type, i.source_id): i.title for i in inventory.items}
    short: dict[tuple[str, int], dict] = {}
    for gap in result.shortfalls:
        spec = by_key[gap.task_key]
        entry = short.setdefault(
            (spec.source_type, spec.source_id),
            {
                "source_type": spec.source_type,
                "source_id": spec.source_id,
                "course_code": spec.course_code,
                "title": item_titles.get((spec.source_type, spec.source_id), spec.title),
                "due_at": spec.deadline.isoformat(),
                "minutes_short": 0,
                "needs_longer_block": False,
            },
        )
        entry["minutes_short"] += gap.minutes
        if not spec.splittable and spec.minutes > _longest_block(free):
            entry["needs_longer_block"] = True
    at_risk = sorted(
        {
            f"{by_key[k].course_code} "
            + item_titles.get((by_key[k].source_type, by_key[k].source_id), by_key[k].title)
            for k in result.at_risk
            if k in by_key
        }
    )
    if not short:
        return None if blocks_exist else _no_availability()
    minutes = sum(e["minutes_short"] for e in short.values())
    earliest_due = min(by_key[g.task_key].deadline for g in result.shortfalls)
    suggestions = _availability_suggestions(free, constraints, earliest_due)
    for entry in sorted(short.values(), key=lambda e: e["due_at"]):
        if entry["source_type"] == "assessment":
            suggestions.append(
                {
                    "type": "request_extension",
                    "assessment_id": entry["source_id"],
                    "text": f"Ask your {entry['course_code']} instructor for an extension on "
                    f"\u201c{entry['title']}\u201d",
                }
            )
    return {
        "items": sorted(short.values(), key=lambda e: e["due_at"]),
        "extra_hours_needed": math.ceil(minutes / 60 * 2) / 2,
        "at_risk": at_risk,
        "suggestions": suggestions[:4],
        "unresolvable": not blocks_exist,
        "excluded": [
            {"course_code": e.course_code, "title": e.title, "reason": e.reason}
            for e in inventory.excluded
        ],
    }


def _no_availability() -> dict:
    return {
        "items": [],
        "extra_hours_needed": 0,
        "at_risk": [],
        "suggestions": [
            {"type": "add_availability", "text": "Add at least one weekly study block."}
        ],
        "unresolvable": True,
        "excluded": [],
    }


def _longest_block(free: dict) -> int:
    return max((iv.minutes for ivs in free.values() for iv in ivs), default=0)


def _availability_suggestions(free: dict, constraints: Constraints, before) -> list[dict]:
    per_weekday: dict[int, int] = defaultdict(int)
    day = constraints.now.astimezone(constraints.tz).date()
    last = before.astimezone(constraints.tz).date()
    while day <= last:
        per_weekday[day.weekday()] += sum(iv.minutes for iv in free.get(day, []))
        day += timedelta(days=1)
    lightest = sorted(range(7), key=lambda wd: per_weekday[wd])[:2]
    return [
        {
            "type": "add_availability",
            "weekday": wd,
            "text": f"Add a study block on {WEEKDAYS[wd]}s.",
        }
        for wd in lightest
    ]
