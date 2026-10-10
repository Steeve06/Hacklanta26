"""Work items → study tasks: AI per course, validated and cached, with a heuristic fallback."""

import hashlib
import logging
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import connections

from ai.client import AIError, available, complete_json, note_fallback
from ai.models import AICache
from ai.schemas import Decomposition, StudyTaskOut

from ..planning.decompose import REPLY_LAG_HOURS, TaskDraft, heuristic_decompose
from ..planning.inventory import WorkItem

logger = logging.getLogger(__name__)

PROMPT = "decompose_v1"
CLAMP_LOW, CLAMP_HIGH = 0.5, 1.5


class InvalidDecomposition(ValueError):
    pass


def item_cache_key(item: WorkItem) -> str:
    return hashlib.sha256(f"{PROMPT}|{item.content_hash()}".encode()).hexdigest()


def payload_for(items: list[WorkItem]) -> dict:
    return {
        "course": items[0].course_code,
        "items": [
            {
                "source_type": i.source_type,
                "source_id": i.source_id,
                "kind": i.kind,
                "title": i.title,
                "baseline_minutes": i.baseline_minutes,
                "linked_chapter_ids": i.chapter_ids,
                "description": i.detail.split("|")[0][:300],
                "original_post_done": i.original_posted if i.kind == "discussion" else None,
            }
            for i in items
        ],
    }


def validate(result: Decomposition, items: list[WorkItem]) -> list[TaskDraft]:
    """Turn AI output into drafts or raise InvalidDecomposition listing every problem."""
    by_ref = {i.ref: i for i in items}
    problems: list[str] = []
    drafts: list[TaskDraft] = []
    seen: set[str] = set()
    per_item: dict[str, list[StudyTaskOut]] = defaultdict(list)
    for task in result.tasks:
        ref = f"{task.source_type}:{task.source_id}"
        if ref not in by_ref:
            problems.append(f"unknown item {ref}")
            continue
        key = f"{ref}:{task.part}"
        if key in seen:
            problems.append(f"duplicate task {key}")
            continue
        seen.add(key)
        per_item[ref].append(task)
    missing = [ref for ref in by_ref if ref not in per_item]
    if missing:
        problems.append(f"items without tasks: {', '.join(missing)}")
    for ref, tasks in per_item.items():
        if by_ref[ref].source_type == "chapter" and [t.part for t in tasks] != ["read"]:
            problems.append(f"{ref} must be exactly one task with part 'read'")
    external = {f"chapter:{cid}:read" for i in items for cid in i.chapter_ids}
    external |= {f"{i.ref}:{part}" for i in items for part in ("original",) if i.original_posted}
    for ref, tasks in per_item.items():
        item = by_ref[ref]
        total = sum(t.est_minutes for t in tasks)
        low, high = item.baseline_minutes * CLAMP_LOW, item.baseline_minutes * CLAMP_HIGH
        scale = 1.0 if low <= total <= high else (low if total < low else high) / total
        for t in tasks:
            if item.kind == "discussion" and item.original_posted and "orig" in t.part:
                continue
            deps = [d for d in t.depends_on if d in seen or d in external]
            unknown = set(t.depends_on) - set(deps)
            if unknown:
                problems.append(f"{ref}:{t.part} depends on unknown {sorted(unknown)}")
            minutes = max(5, round(t.est_minutes * scale))
            drafts.append(
                TaskDraft(
                    ref=ref,
                    part=t.part,
                    title=t.title
                    if t.title.startswith(item.course_code)
                    else f"{item.course_code} · {t.title}",
                    est_minutes=minutes,
                    depends_on=deps,
                    min_chunk=min(t.min_chunk_minutes, minutes),
                    splittable=t.splittable,
                    lag_hours=REPLY_LAG_HOURS if "repl" in t.part else 0,
                    ai_generated=True,
                )
            )
    if _has_cycle(drafts):
        problems.append("dependencies contain a cycle")
    if problems:
        raise InvalidDecomposition("; ".join(problems))
    return drafts


def _has_cycle(drafts: list[TaskDraft]) -> bool:
    graph = {d.key: d.depends_on for d in drafts}
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        if state.get(node) == 1:
            return True
        if state.get(node) == 2 or node not in graph:
            return False
        state[node] = 1
        if any(visit(dep) for dep in graph[node]):
            return True
        state[node] = 2
        return False

    return any(visit(n) for n in graph)


def _to_payload(drafts: list[TaskDraft]) -> list[dict]:
    return [d.__dict__ for d in drafts]


def _from_payload(rows: list[dict]) -> list[TaskDraft]:
    return [TaskDraft(**row) for row in rows]


def _ask(items: list[WorkItem]) -> tuple[list[TaskDraft] | None, str]:
    """Call the model (once, then once more with the validation errors). Thread-safe: no ORM writes
    other than call logging, and connections are closed on exit."""
    note = ""
    try:
        for _ in range(2):
            try:
                result = complete_json(
                    purpose="decompose", tier="planner", prompt=PROMPT,
                    payload=payload_for(items), schema=Decomposition, max_tokens=3000,
                    retry_note=note,
                )  # fmt: skip
                return validate(result, items), ""
            except InvalidDecomposition as exc:
                note = str(exc)
        return None, f"invalid output: {note}"
    except AIError as exc:
        return None, str(exc)
    finally:
        if threading.current_thread() is not threading.main_thread():
            connections.close_all()


def decompose(student, items: list[WorkItem]) -> tuple[list[TaskDraft], dict]:
    """Cached items reuse earlier output; only new or changed items go to the model, one call per
    course, in parallel."""
    drafts: list[TaskDraft] = []
    pending: dict[int, list[WorkItem]] = defaultdict(list)
    sources = {"cached": 0, "ai": 0, "heuristic": 0, "fallback": 0}
    keys = {item.ref: item_cache_key(item) for item in items}
    cached = {c.key: c.payload for c in AICache.objects.filter(key__in=keys.values())}
    use_ai = available()
    for item in items:
        if keys[item.ref] in cached:
            drafts.extend(_from_payload(cached[keys[item.ref]]))
            sources["cached"] += 1
        elif use_ai:
            pending[item.course_id].append(item)
        else:
            drafts.extend(heuristic_decompose(item))
            sources["heuristic"] += 1

    calls = 0
    if pending:
        if settings.AI_PARALLEL and len(pending) > 1:
            with ThreadPoolExecutor(max_workers=len(pending)) as pool:
                futures = {cid: pool.submit(_ask, group) for cid, group in pending.items()}
            answers = {cid: future.result() for cid, future in futures.items()}
        else:
            answers = {cid: _ask(group) for cid, group in pending.items()}
        for course_id, (result, error) in answers.items():
            calls += 1
            course_items = pending[course_id]
            if result is None:
                note_fallback("decompose", error)
                drafts.extend(d for i in course_items for d in heuristic_decompose(i))
                sources["fallback"] += len(course_items)
                continue
            for item in course_items:
                item_drafts = [d for d in result if d.ref == item.ref]
                AICache.objects.update_or_create(
                    key=keys[item.ref],
                    defaults={"purpose": "decompose", "payload": _to_payload(item_drafts)},
                )
            drafts.extend(result)
            sources["ai"] += len(course_items)
    return drafts, {"decomposition": sources, "ai_calls_decompose": calls}
