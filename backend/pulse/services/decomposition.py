"""Work items → study tasks."""

from ..planning.decompose import TaskDraft, heuristic_decompose
from ..planning.inventory import WorkItem


def decompose(student, items: list[WorkItem]) -> tuple[list[TaskDraft], dict]:
    drafts = [draft for item in items for draft in heuristic_decompose(item)]
    return drafts, {"decomposition": "heuristic"}
