"""The planning pipeline: inventory → decomposition → placement → persisted schedule."""

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from django.db import transaction
from django.dispatch import Signal

from accounts.clock import now as clock_now
from accounts.models import StudentProfile
from lms.selectors import student_snapshot

from ..models import AvailabilityBlock, Blackout, Schedule, Session, StudyTask
from ..planning.decompose import TaskDraft
from ..planning.feedback import parse_feedback
from ..planning.inventory import Inventory, WorkItem, build_inventory
from ..planning.slots import free_time
from ..planning.solver import Solver, check_hard_constraints
from ..planning.types import Constraints, Interval, Placement, Preferences, SolveResult, TaskSpec
from .decomposition import decompose
from .overload import build_overload_report
from .pace import measured_pace, productive_hours
from .polish import polish

logger = logging.getLogger(__name__)

schedule_committed = Signal()

KIND_BY_ITEM = {
    "study": "study",
    "homework": "assignment",
    "discussion": "discussion",
    "quiz": "quiz",
}
MIN_REMAINING_MINUTES = 5
PIN_WINDOW = timedelta(hours=24)
VERSIONS_KEPT = 20

ProgressCallback = Callable[[str, int], None]


@dataclass
class PlanContext:
    student: object
    profile: StudentProfile
    now: datetime
    tz: object
    horizon_end: datetime


def _noop(stage: str, progress: int) -> None:
    return None


def plan(
    student, *, reason: str, on_progress: ProgressCallback = _noop, at: datetime | None = None
) -> Schedule:
    """Build and activate a new schedule version. `at` overrides "now" (seeding only)."""
    profile, _ = StudentProfile.objects.get_or_create(user=student)
    now = at or clock_now(student)
    tz = student.tz
    on_progress("collecting", 10)
    snapshot = student_snapshot(student, now)
    horizon_end = snapshot.term_end_at(tz) or now + timedelta(days=120)
    ctx = PlanContext(student, profile, now, tz, max(horizon_end, now))
    inventory = build_inventory(snapshot, ctx.horizon_end)

    on_progress("estimating", 35)
    drafts, decomposition_meta = decompose(student, inventory.items)
    tasks = _sync_tasks(student, inventory.items, drafts)

    on_progress("building", 65)
    previous = Schedule.objects.filter(student=student, is_active=True).first()
    history = _history(previous, now)
    done_minutes = _done_minutes(history)
    pace = measured_pace(student)
    specs = _task_specs(inventory, drafts, tasks, done_minutes, pace, now)
    free = _free_time(ctx, history)
    preferences = _preferences(student, profile)
    constraints = Constraints(
        tz=tz,
        now=now,
        horizon_end=ctx.horizon_end,
        max_minutes_per_day=int(float(profile.max_hours_per_day) * 60),
        session_minutes=profile.session_minutes,
    )
    result = _solve(specs, free, constraints, preferences, previous, now)

    problems = check_hard_constraints(result, specs, free, constraints)
    if problems:
        logger.error("Plan for student %s broke hard constraints: %s", student.id, problems[:5])

    overload = build_overload_report(
        specs, result, free, constraints, inventory, blocks_exist=bool(free)
    )
    on_progress("polishing", 85)
    titles, summary = polish(student, inventory, specs, result, overload, now)
    schedule = _persist(ctx, previous, history, specs, result, titles, summary, overload, {
        "reason": reason,
        "pace": pace,
        "iterations": result.iterations,
        "elapsed_ms": result.elapsed_ms,
        "penalty": result.penalty,
        "violations": len(problems),
        **decomposition_meta,
    })  # fmt: skip
    on_progress("done", 100)
    return schedule


def _sync_tasks(student, items: list[WorkItem], drafts: list[TaskDraft]) -> dict[str, StudyTask]:
    item_by_ref = {i.ref: i for i in items}
    hashes = {i.ref: i.content_hash() for i in items}
    existing = {
        f"{t.source_type}:{t.source_id}:{t.key}": t
        for t in StudyTask.objects.filter(student=student)
    }
    keep: dict[str, StudyTask] = {}
    for draft in drafts:
        item = item_by_ref[draft.ref]
        values = {
            "course_id": item.course_id,
            "title": draft.title,
            "est_minutes": draft.est_minutes,
            "min_chunk_minutes": draft.min_chunk,
            "splittable": draft.splittable,
            "ai_generated": draft.ai_generated,
            "cache_key": hashes[draft.ref],
            "active": True,
        }
        task = existing.get(draft.key)
        if task is None:
            task = StudyTask.objects.create(
                student=student, source_type=item.source_type, source_id=item.source_id,
                key=draft.part, **values,
            )  # fmt: skip
        else:
            changed = [k for k, v in values.items() if getattr(task, k) != v]
            for k in changed:
                setattr(task, k, values[k])
            if changed:
                task.save(update_fields=[*changed, "updated_at"])
        keep[draft.key] = task
    stale = [t.id for k, t in existing.items() if k not in keep and t.active]
    StudyTask.objects.filter(id__in=stale).update(active=False)
    for draft in drafts:
        deps = [keep[d] for d in draft.depends_on if d in keep]
        keep[draft.key].depends_on.set(deps)
    return keep


def _history(previous: Schedule | None, now: datetime) -> list[Session]:
    if previous is None:
        return []
    return list(
        previous.sessions.select_related("task").exclude(
            status=Session.Status.PLANNED, start__gte=now
        )
    )


def _done_minutes(history: list[Session]) -> dict[str, int]:
    done: dict[str, int] = defaultdict(int)
    for s in history:
        if s.kind == Session.Kind.CHAPTER_QUIZ:
            continue
        if s.status in (Session.Status.DONE, Session.Status.PARTIAL):
            done[_task_ref(s.task)] += s.completed_minutes
    return done


def _task_ref(task: StudyTask) -> str:
    return f"{task.source_type}:{task.source_id}:{task.key}"


def _task_specs(
    inventory: Inventory,
    drafts: list[TaskDraft],
    tasks: dict[str, StudyTask],
    done: dict[str, int],
    pace: float,
    now: datetime,
) -> list[TaskSpec]:
    items = {i.ref: i for i in inventory.items}
    specs: dict[str, TaskSpec] = {}
    for draft in drafts:
        item = items[draft.ref]
        remaining = round(draft.est_minutes * pace) - done.get(draft.key, 0)
        if remaining < MIN_REMAINING_MINUTES:
            continue
        specs[draft.key] = TaskSpec(
            key=draft.key,
            source_type=item.source_type,
            source_id=item.source_id,
            part=draft.part,
            course_id=item.course_id,
            course_code=item.course_code,
            title=tasks[draft.key].title,
            kind=KIND_BY_ITEM[item.kind],
            minutes=remaining,
            min_chunk=min(draft.min_chunk, remaining),
            splittable=draft.splittable,
            not_before=max(item.not_before, now),
            deadline=item.deadline,
            weight=item.weight,
            depends_on=list(draft.depends_on),
            lag_after_deps=timedelta(hours=draft.lag_hours),
            chapter_id=item.source_id if item.source_type == "chapter" else None,
            late_window=item.late_window,
        )
    for spec in specs.values():
        spec.depends_on = [d for d in spec.depends_on if d in specs]
    return list(specs.values())


def _free_time(ctx: PlanContext, history: list[Session]) -> dict:
    blocks = [
        (b.weekday, b.start_time, b.end_time)
        for b in AvailabilityBlock.objects.filter(student=ctx.student)
    ]
    blackouts = [
        Interval(b.start, b.end)
        for b in Blackout.objects.filter(student=ctx.student, end__gt=ctx.now)
    ]
    avoided = [
        Interval(s.start, s.end)
        for s in history
        if s.status == Session.Status.RESCHEDULED and s.end > ctx.now
    ]
    return free_time(
        blocks,
        [*blackouts, *avoided],
        tz=ctx.tz,
        start=ctx.now,
        end=ctx.horizon_end,
        earliest=ctx.profile.earliest_time,
        latest=ctx.profile.latest_time,
    )


def _preferences(student, profile: StudentProfile) -> Preferences:
    day_factor, hours = parse_feedback(profile.plan_feedback)
    return Preferences(
        day_factor=day_factor, preferred_hours=hours, productive_hours=productive_hours(student)
    )


def _pins(
    previous: Schedule | None, specs: list[TaskSpec], free: dict, now: datetime, tz
) -> list[Placement]:
    if previous is None:
        return []
    by_key = {s.key: s for s in specs}
    pins = []
    for s in previous.sessions.filter(
        status=Session.Status.PLANNED, start__gte=now, start__lt=now + PIN_WINDOW
    ).select_related("task"):
        key = _task_ref(s.task)
        spec = by_key.get(key)
        if spec is None or s.kind == Session.Kind.CHAPTER_QUIZ:
            continue
        day = s.start.astimezone(tz).date()
        start, end = s.start.astimezone(UTC), s.end.astimezone(UTC)
        if not any(iv.start <= start and end <= iv.end for iv in free.get(day, [])):
            continue
        if end > spec.deadline:
            continue
        pins.append(
            Placement(key, start, end, day, spec.course_id, spec.kind, pinned=True, session_id=s.id)
        )
    return pins


def _solve(specs, free, constraints, preferences, previous, now) -> SolveResult:
    pins = _pins(previous, specs, free, now, constraints.tz)
    result = Solver(specs, free, constraints, preferences, pins).solve()
    if pins and result.shortfalls:
        unpinned = Solver(specs, free, constraints, preferences).solve()
        if sum(s.minutes for s in unpinned.shortfalls) < sum(s.minutes for s in result.shortfalls):
            return unpinned
    return result


@transaction.atomic
def _persist(ctx, previous, history, specs, result, titles, summary, overload, meta) -> Schedule:
    student = ctx.student
    last = Schedule.objects.filter(student=student).order_by("-version").first()
    Schedule.objects.filter(student=student, is_active=True).update(is_active=False)
    schedule = Schedule.objects.create(
        student=student,
        version=(last.version + 1) if last else 1,
        is_active=True,
        generated_at=ctx.now,
        horizon_end=ctx.horizon_end,
        summary=summary,
        overload_report=overload,
        solver_meta=meta,
    )
    tasks = {_task_ref(t): t for t in StudyTask.objects.filter(student=student, active=True)}
    rows = [
        Session(
            schedule=schedule,
            task=s.task,
            start=s.start,
            end=s.end,
            kind=s.kind,
            title=s.title,
            status=s.status,
            completed_minutes=s.completed_minutes,
            at_risk=s.at_risk,
        )  # fmt: skip
        for s in history
    ]
    spec_by_key = {s.key: s for s in specs}
    for i, p in enumerate(result.placements):
        task = tasks.get(p.task_key)
        if task is None:
            continue
        title = titles.get(i) or (
            _quiz_title(p, spec_by_key) if p.kind == "chapter_quiz" else task.title
        )
        rows.append(
            Session(
                schedule=schedule,
                task=task,
                start=p.start,
                end=p.end,
                kind=p.kind,
                title=title,
                at_risk=p.at_risk,
            )  # fmt: skip
        )
    Session.objects.bulk_create(rows)
    stale = Schedule.objects.filter(student=student).order_by("-version")[VERSIONS_KEPT:]
    Schedule.objects.filter(id__in=[s.id for s in stale]).delete()
    transaction.on_commit(lambda: schedule_committed.send(sender=Schedule, schedule=schedule))
    return schedule


def _quiz_title(p: Placement, specs: dict[str, TaskSpec]) -> str:
    names = [
        f"{specs[k].course_code} {specs[k].title.split(' · Read ')[-1].split(':')[0]}"
        for k in p.quiz_keys
        if k in specs
    ]
    return "Chapter quiz: " + ", ".join(names) if names else "Chapter quiz"
