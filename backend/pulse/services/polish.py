"""Session titles and the plan summary."""

from collections import Counter
from datetime import timedelta

from ..planning.inventory import Inventory
from ..planning.types import SolveResult, TaskSpec

DETAIL_DAYS = 14


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
            f"{excluded.course_code} {excluded.title} is past its cut-off, so it's not in the plan."
        )
    return " ".join(parts)


def polish(
    student, inventory: Inventory, specs: list[TaskSpec], result: SolveResult, overload, now
):
    """Return (titles by placement index, summary). Titles default to the task titles."""
    return {}, template_summary(inventory, specs, result, overload, now)
