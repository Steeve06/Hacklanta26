"""Explain work that does not fit before its deadline, and what would fix it."""

import math
from collections import defaultdict
from datetime import datetime, timedelta

from ..planning.inventory import Inventory
from ..planning.types import Constraints, SolveResult, TaskSpec

URGENT = timedelta(hours=24)
UNUSED_MINUTES = 15
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
    latest_due = max(by_key[g.task_key].deadline for g in result.shortfalls)
    first = min(short.values(), key=lambda e: e["due_at"])
    if not blocks_exist:
        suggestions = list(_no_availability()["suggestions"])
    else:
        suggestions = _urgent_suggestion(first, constraints)
        suggestions += _capacity_suggestions(result, free, constraints, latest_due)
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


def _when(moment, constraints: Constraints) -> str:
    local = moment.astimezone(constraints.tz)
    clock = local.strftime("%I:%M %p").lstrip("0")
    if local.date() == constraints.now.astimezone(constraints.tz).date():
        return f"{clock} today"
    return f"{local:%a %b} {local.day}, {clock}"


def _urgent_suggestion(entry: dict, constraints: Constraints) -> list[dict]:
    """Work due within a day can only be helped by time before that deadline, so say so."""
    due = datetime.fromisoformat(entry["due_at"])
    if due - constraints.now > URGENT:
        return []
    return [
        {
            "type": "add_time_before",
            "text": f"Find {math.ceil(entry['minutes_short'] / 5) * 5} more minutes for "
            f"\u201c{entry['title']}\u201d before {_when(due, constraints)}.",
        }
    ]


def _capacity_suggestions(result, free: dict, constraints: Constraints, before) -> list[dict]:
    """Name the limit that is actually full before the first missed deadline. Adding free time
    only helps when no limit is full; otherwise it's the student's own daily or
    weekly limit that stops the plan."""
    tz = constraints.tz
    placed_day: dict = defaultdict(int)
    placed_week: dict = defaultdict(int, constraints.week_used)
    for p in result.placements:
        placed_day[p.day] += p.minutes
        placed_week[constraints.week_of(p.day)] += p.minutes
    day_full = week_full = False
    day = constraints.now.astimezone(tz).date()
    last = before.astimezone(tz).date()
    while day <= last:
        spare = sum(iv.minutes for iv in free.get(day, [])) - placed_day[day]
        if spare >= UNUSED_MINUTES:
            if placed_day[day] >= constraints.max_minutes_per_day - 15:
                day_full = True
            week_cap = constraints.max_minutes_per_week
            if week_cap is not None and placed_week[constraints.week_of(day)] >= week_cap - 15:
                week_full = True
        day += timedelta(days=1)
    suggestions = []
    if week_full:
        hours = f"{constraints.max_minutes_per_week / 60:g}"
        suggestions.append(
            {
                "type": "raise_weekly_limit",
                "text": f"Raise your weekly study limit (now {hours} hours).",
            }
        )
    if day_full:
        hours = f"{constraints.max_minutes_per_day / 60:g}"
        suggestions.append(
            {
                "type": "raise_daily_limit",
                "text": f"Raise your most study hours in one day (now {hours} hours).",
            }
        )
    if not suggestions:
        suggestions += _availability_suggestions(free, constraints, before)
    return suggestions


def _availability_suggestions(free: dict, constraints: Constraints, before) -> list[dict]:
    """The two days before `before` with the least free time. Only days that come before the
    deadline are named; within a week those are dates, over longer spans weekdays."""
    tz = constraints.tz
    day = constraints.now.astimezone(tz).date()
    last = before.astimezone(tz).date()
    days = []
    while day <= last:
        days.append(day)
        day += timedelta(days=1)
    if len(days) < 7:
        minutes = {d: sum(iv.minutes for iv in free.get(d, [])) for d in days}
        lightest = sorted(days, key=lambda d: (minutes[d], d))[:2]
        today = constraints.now.astimezone(tz).date()
        return [
            {
                "type": "add_availability",
                "weekday": d.weekday(),
                "text": "Add study time today."
                if d == today
                else f"Add study time on {d:%a %b} {d.day}.",
            }
            for d in sorted(lightest)
        ]
    per_weekday: dict[int, int] = defaultdict(int)
    for d in days:
        per_weekday[d.weekday()] += sum(iv.minutes for iv in free.get(d, []))
    lightest_weekdays = sorted(range(7), key=lambda wd: (per_weekday[wd], wd))[:2]
    return [
        {
            "type": "add_availability",
            "weekday": wd,
            "text": f"Add a study block on {WEEKDAYS[wd]}s.",
        }
        for wd in lightest_weekdays
    ]
