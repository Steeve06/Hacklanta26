"""Session titles and the plan summary.

AI writes them on explicit generates; re-plans reuse cached titles and a template summary, so
routine re-plans make no model calls.
"""

import hashlib
from collections import Counter
from datetime import timedelta

from ai.client import AIError, available, complete_json, note_fallback
from ai.models import AICache
from ai.schemas import Polish

from ..planning.inventory import Inventory
from ..planning.types import SolveResult, TaskSpec

DETAIL_DAYS = 14
MAX_TITLED_TASKS = 60
PROMPT = "polish_v1"
AI_REASONS = {"generate"}


def template_summary(inventory: Inventory, specs, result: SolveResult, overload, now) -> str:
    soon = [p for p in result.placements if p.start < now + timedelta(days=DETAIL_DAYS)]
    minutes = sum(p.minutes for p in soon)
    courses = Counter(spec.course_code for spec in specs)
    parts = []
    if soon:
        parts.append(
            f"{len(soon)} sessions over the next two weeks, about {round(minutes / 60, 1):g} hours "
            f"in total across {len(courses)} courses."
        )
    else:
        parts.append("Nothing needs scheduling in the next two weeks.")
    if overload and overload["items"]:
        parts.append(
            f"{len(overload['items'])} items don't fit before their deadlines; "
            f"about {overload['extra_hours_needed']:g} more hours would cover them."
        )
    elif result.at_risk:
        parts.append("A few deadlines are close, so those sessions come first.")
    for excluded in inventory.excluded[:2]:
        parts.append(
            f"{excluded.course_code} {excluded.title} is past due, so it's not in the plan."
        )
    return " ".join(parts)


def _title_key(spec: TaskSpec) -> str:
    return hashlib.sha256(f"{PROMPT}|title|{spec.key}|{spec.title}".encode()).hexdigest()


def _clean_title(title: str, spec: TaskSpec) -> str:
    title = title.strip()
    if not title.startswith(spec.course_code):
        title = f"{spec.course_code} · {title}"
    return title[:80]


def polish(
    student,
    inventory: Inventory,
    specs: list[TaskSpec],
    result: SolveResult,
    overload,
    now,
    *,
    reason: str = "",
):
    """Return (titles by placement index, summary)."""
    by_key = {s.key: s for s in specs}
    upcoming_keys: list[str] = []
    for p in result.placements:
        soon = p.start < now + timedelta(days=DETAIL_DAYS)
        if (
            soon
            and p.kind != "chapter_quiz"
            and p.task_key in by_key
            and p.task_key not in upcoming_keys
        ):
            upcoming_keys.append(p.task_key)
    upcoming_keys = upcoming_keys[:MAX_TITLED_TASKS]
    cache_keys = {k: _title_key(by_key[k]) for k in by_key}
    cached = {
        c.key: c.payload["title"] for c in AICache.objects.filter(key__in=cache_keys.values())
    }
    task_titles = {k: cached[ck] for k, ck in cache_keys.items() if ck in cached}
    summary = template_summary(inventory, specs, result, overload, now)

    if reason in AI_REASONS and available() and upcoming_keys:
        try:
            response = complete_json(
                purpose="polish", tier="light", prompt=PROMPT, schema=Polish, max_tokens=1500,
                payload={
                    "sessions": [
                        {"index": i, "course": by_key[k].course_code, "kind": by_key[k].kind,
                         "current_title": by_key[k].title}  # fmt: skip
                        for i, k in enumerate(upcoming_keys)
                    ],
                    "plan_facts": summary,
                },
            )  # fmt: skip
            for row in response.titles:
                if row.index < len(upcoming_keys):
                    key = upcoming_keys[row.index]
                    title = _clean_title(row.title, by_key[key])
                    task_titles[key] = title
                    AICache.objects.update_or_create(
                        key=cache_keys[key],
                        defaults={"purpose": "polish", "payload": {"title": title}},
                    )
            summary = response.summary.strip()
        except AIError as exc:
            note_fallback("polish", str(exc))

    titles = {
        i: task_titles[p.task_key]
        for i, p in enumerate(result.placements)
        if p.kind != "chapter_quiz" and p.task_key in task_titles
    }
    return titles, summary
