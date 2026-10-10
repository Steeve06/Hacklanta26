"""Deterministic placement of study tasks into free time.

Greedy Earliest-Deadline-First with priority = weight / slack, placing chunks into the earliest
valid slot, then a bounded local-search pass over soft constraints. Every hard constraint is
checked on every placement; `check_hard_constraints` re-verifies a finished plan.
"""

import time as walltime
from collections import defaultdict
from datetime import date, datetime, timedelta

from .types import Constraints, Interval, Placement, Preferences, Shortfall, SolveResult, TaskSpec

MAX_ITERATIONS = 500
MAX_SECONDS = 2.0


def buffer_for(task: TaskSpec, now: datetime) -> timedelta:
    if task.late_window:
        return timedelta(0)
    return max(timedelta(hours=12), (task.deadline - now) * 0.10)


class Solver:
    def __init__(
        self,
        tasks: list[TaskSpec],
        free: dict[date, list[Interval]],
        constraints: Constraints,
        preferences: Preferences | None = None,
        pinned: list[Placement] | None = None,
    ):
        self.c = constraints
        self.prefs = preferences or Preferences()
        self.tasks = {t.key: t for t in tasks}
        self.base = {day: list(ivs) for day, ivs in free.items()}
        self.free = {day: list(ivs) for day, ivs in free.items()}
        self.capacity = {day: sum(iv.minutes for iv in ivs) for day, ivs in free.items()}
        self.day_minutes: dict[date, int] = defaultdict(int)
        self.day_course: dict[tuple[date, int], int] = defaultdict(int)
        self.placements: list[Placement] = []
        self.remaining = {t.key: t.minutes for t in tasks}
        self.successors: dict[str, list[str]] = defaultdict(list)
        for t in tasks:
            for dep in t.depends_on:
                self.successors[dep].append(t.key)
        self.at_risk: set[str] = set()
        self.shortfalls: list[Shortfall] = []
        for p in pinned or []:
            self._commit(p)
            if p.task_key in self.remaining:
                self.remaining[p.task_key] = max(0, self.remaining[p.task_key] - p.minutes)

    def day_of(self, moment: datetime) -> date:
        return moment.astimezone(self.c.tz).date()

    def limit(self, task: TaskSpec, *, use_buffer: bool) -> datetime:
        end = min(task.deadline, self.c.horizon_end)
        return end - buffer_for(task, self.c.now) if use_buffer else end

    def task_end(self, key: str) -> datetime | None:
        ends = [p.end for p in self.placements if p.task_key == key]
        return max(ends) if ends else None

    def earliest(self, task: TaskSpec) -> datetime:
        start = max(task.not_before, self.c.now)
        for dep in task.depends_on:
            end = self.task_end(dep)
            if end is not None:
                start = max(start, end + task.lag_after_deps)
        return start

    def priority(self, task: TaskSpec) -> tuple:
        earliest = self.earliest(task)
        slack_hours = (self.limit(task, use_buffer=True) - earliest).total_seconds() / 3600
        slack_hours -= self.remaining[task.key] / 60
        urgency = task.weight / max(slack_hours, 0.5)
        return (task.late_window, urgency, -task.deadline.timestamp(), task.weight, task.minutes)

    def day_cap(self, day: date, *, strict: bool) -> int:
        cap = self.c.max_minutes_per_day
        if strict:
            factor = self.prefs.day_factor.get(day.weekday(), 1.0)
            reserve = int(self.capacity.get(day, 0) * (1 - self.c.slack_ratio))
            cap = min(int(cap * factor), reserve)
        return cap

    def _commit(self, p: Placement) -> None:
        pad = timedelta(minutes=self.c.break_minutes)
        hole = Interval(p.start - pad, p.end + pad)
        day = p.day
        remaining_ivs = []
        for iv in self.free.get(day, []):
            if hole.end <= iv.start or hole.start >= iv.end:
                remaining_ivs.append(iv)
                continue
            if hole.start > iv.start:
                remaining_ivs.append(Interval(iv.start, hole.start))
            if hole.end < iv.end:
                remaining_ivs.append(Interval(hole.end, iv.end))
        self.free[day] = [iv for iv in remaining_ivs if iv.minutes > 0]
        self.day_minutes[day] += p.minutes
        if p.kind != "chapter_quiz":
            self.day_course[(day, p.course_id)] += 1
        self.placements.append(p)

    def _place_chunks(self, task: TaskSpec, *, use_buffer: bool, strict: bool) -> None:
        limit = self.limit(task, use_buffer=use_buffer)
        cursor = self.earliest(task)
        session = self.c.session_minutes
        for day in sorted(self.free):
            if self.remaining[task.key] <= 0:
                return
            if day < self.day_of(cursor) or not self.free[day]:
                continue
            if self.free[day][0].start >= limit:
                return
            if strict and self.day_course[(day, task.course_id)] >= self.c.max_same_course_per_day:
                continue
            for iv in list(self.free[day]):
                need = self.remaining[task.key]
                if need <= 0:
                    return
                start = max(iv.start, cursor)
                end_cap = min(iv.end, limit)
                room = int((end_cap - start).total_seconds() // 60)
                cap_left = self.day_cap(day, strict=strict) - self.day_minutes[day]
                length = min(need, session if task.splittable else need, room, cap_left)
                if not task.splittable:
                    if length < need:
                        continue
                elif length < min(task.min_chunk, need):
                    continue
                placement = Placement(
                    task_key=task.key,
                    start=start,
                    end=start + timedelta(minutes=length),
                    day=day,
                    course_id=task.course_id,
                    kind=task.kind,
                    at_risk=not use_buffer,
                )
                self._commit(placement)
                self.remaining[task.key] -= length
                cursor = placement.end + timedelta(minutes=self.c.break_minutes)
                if (
                    strict
                    and self.day_course[(day, task.course_id)] >= self.c.max_same_course_per_day
                ):
                    break

    def place(self, task: TaskSpec) -> None:
        buffer_room = self.limit(task, use_buffer=True) - self.earliest(task)
        buffer_possible = buffer_room >= timedelta(minutes=self.remaining[task.key])
        if buffer_possible:
            self._place_chunks(task, use_buffer=True, strict=True)
            self._place_chunks(task, use_buffer=True, strict=False)
        if self.remaining[task.key] > 0:
            self._place_chunks(task, use_buffer=False, strict=False)
            if any(p.task_key == task.key and p.at_risk for p in self.placements):
                self.at_risk.add(task.key)
        if self.remaining[task.key] > 0:
            self.shortfalls.append(Shortfall(task.key, self.remaining[task.key]))

    def run_greedy(self) -> None:
        pending = {k for k, m in self.remaining.items() if m > 0}
        while pending:
            ready = [
                self.tasks[k]
                for k in pending
                if all(d not in pending for d in self.tasks[k].depends_on)
            ]
            if not ready:
                ready = [self.tasks[k] for k in pending]
            task = max(ready, key=self.priority)
            self.place(task)
            pending.discard(task.key)

    def penalty(self, placements: list[Placement] | None = None) -> float:
        placements = placements if placements is not None else self.placements
        total = 0.0
        counts: dict[tuple[date, int], int] = defaultdict(int)
        max_weight = max((t.weight for t in self.tasks.values()), default=1) or 1
        for p in placements:
            if p.kind == "chapter_quiz":
                continue
            counts[(p.day, p.course_id)] += 1
            task = self.tasks.get(p.task_key)
            weight = (task.weight if task else 1) / max_weight
            total += weight * (p.start - self.c.now).total_seconds() / 86400 * 0.05
            total += (1 - self.prefs.day_factor.get(p.day.weekday(), 1.0)) * 3
            hour = p.start.astimezone(self.c.tz).hour
            if self.prefs.productive_hours and hour not in self.prefs.productive_hours:
                total += 0.5
            if self.prefs.preferred_hours:
                lo, hi = self.prefs.preferred_hours
                if not lo <= hour < hi:
                    total += 1.5
        total += sum(max(0, n - self.c.max_same_course_per_day) * 10 for n in counts.values())
        return total

    def _move_is_valid(self, index: int, start: datetime) -> bool:
        p = self.placements[index]
        task = self.tasks[p.task_key]
        end = start + timedelta(minutes=p.minutes)
        day = self.day_of(start)
        if start < max(task.not_before, self.c.now):
            return False
        if end > self.limit(task, use_buffer=not p.at_risk):
            return False
        if not any(iv.start <= start and end <= iv.end for iv in self.base.get(day, [])):
            return False
        pad = timedelta(minutes=self.c.break_minutes)
        for j, other in enumerate(self.placements):
            if j != index and other.start - pad < end and start < other.end + pad:
                return False
        used = sum(o.minutes for j, o in enumerate(self.placements) if j != index and o.day == day)
        if used + p.minutes > self.day_cap(day, strict=False):
            return False
        for dep in task.depends_on:
            for o in self.placements:
                if (
                    o.task_key == dep
                    and o.kind != "chapter_quiz"
                    and o.end + task.lag_after_deps > start
                ):
                    return False
        for succ in self.successors.get(task.key, []):
            lag = self.tasks[succ].lag_after_deps
            for o in self.placements:
                if o.task_key == succ and end + lag > o.start:
                    return False
        for o in self.placements:
            if o.kind == "chapter_quiz" and o.task_key == task.key and end > o.start:
                return False
        return True

    def improve(self) -> tuple[int, float]:
        started = walltime.monotonic()
        iterations = 0
        current = self.penalty()
        improved = True
        while improved and iterations < MAX_ITERATIONS:
            improved = False
            for index, p in enumerate(self.placements):
                if p.pinned or p.kind == "chapter_quiz":
                    continue
                if iterations >= MAX_ITERATIONS or walltime.monotonic() - started > MAX_SECONDS:
                    return iterations, current
                iterations += 1
                best_start, best_penalty = None, current
                for start in self._candidates(p):
                    if start == p.start or not self._move_is_valid(index, start):
                        continue
                    moved = Placement(**{**p.__dict__, "start": start,
                                         "end": start + timedelta(minutes=p.minutes),
                                         "day": self.day_of(start)})  # fmt: skip
                    trial = self.penalty(
                        self.placements[:index] + [moved] + self.placements[index + 1 :]
                    )
                    if trial < best_penalty - 1e-9:
                        best_start, best_penalty = start, trial
                if best_start is not None:
                    self.placements[index] = Placement(
                        **{
                            **p.__dict__,
                            "start": best_start,
                            "end": best_start + timedelta(minutes=p.minutes),
                            "day": self.day_of(best_start),
                        }  # fmt: skip
                    )
                    current = best_penalty
                    improved = True
        return iterations, current

    def _rebuild_free(self) -> None:
        placements = self.placements
        self.free = {day: list(ivs) for day, ivs in self.base.items()}
        self.day_minutes = defaultdict(int)
        self.day_course = defaultdict(int)
        self.placements = []
        for p in placements:
            self._commit(p)

    def _candidates(self, p: Placement) -> list[datetime]:
        task = self.tasks[p.task_key]
        lo = self.day_of(max(task.not_before, self.c.now))
        hi = self.day_of(self.limit(task, use_buffer=not p.at_risk))
        pad = timedelta(minutes=self.c.break_minutes)
        starts = []
        for day, ivs in self.base.items():
            if not lo <= day <= hi:
                continue
            for iv in ivs:
                starts.append(iv.start)
                starts.append(iv.end - timedelta(minutes=p.minutes))
            starts.extend(o.end + pad for o in self.placements if o.day == day)
        return sorted(set(starts))

    def solve(self, *, local_search: bool = True) -> SolveResult:
        started = walltime.monotonic()
        self.run_greedy()
        iterations, penalty = self.improve() if local_search else (0, self.penalty())
        self._rebuild_free()
        self.placements.sort(key=lambda p: p.start)
        for p in self.placements:
            if p.task_key in self.at_risk:
                p.at_risk = True
        return SolveResult(
            placements=self.placements,
            shortfalls=self.shortfalls,
            at_risk=self.at_risk,
            iterations=iterations,
            elapsed_ms=int((walltime.monotonic() - started) * 1000),
            penalty=round(penalty, 3),
        )


def check_hard_constraints(
    result: SolveResult,
    tasks: list[TaskSpec],
    free: dict[date, list[Interval]],
    constraints: Constraints,
) -> list[str]:
    """Return a list of violations; empty means the plan is valid."""
    problems = []
    by_key = {t.key: t for t in tasks}
    placements = sorted(result.placements, key=lambda p: p.start)
    per_day: dict[date, int] = defaultdict(int)
    for p in placements:
        day = p.start.astimezone(constraints.tz).date()
        if not any(iv.start <= p.start and p.end <= iv.end for iv in free.get(day, [])):
            problems.append(f"{p.task_key} outside availability at {p.start}")
        if p.start < constraints.now and not p.pinned:
            problems.append(f"{p.task_key} scheduled in the past")
        per_day[day] += p.minutes
        task = by_key.get(p.task_key)
        if task and task.splittable and p.minutes > constraints.session_minutes:
            problems.append(f"{p.task_key} longer than the session length")
        if task and p.kind != "chapter_quiz":
            if p.start < task.not_before:
                problems.append(f"{p.task_key} before it is available")
            hard = min(task.deadline, constraints.horizon_end)
            limit = hard if p.at_risk else hard - buffer_for(task, constraints.now)
            if p.end > limit:
                problems.append(f"{p.task_key} ends after its deadline")
            for dep in task.depends_on:
                for other in placements:
                    if (
                        other.task_key == dep
                        and other.kind != "chapter_quiz"
                        and other.end + task.lag_after_deps > p.start
                    ):
                        problems.append(f"{p.task_key} starts before {dep} finishes")
    for a, b in zip(placements, placements[1:], strict=False):
        if b.start < a.end + timedelta(minutes=constraints.break_minutes):
            problems.append(f"{a.task_key} and {b.task_key} overlap or have no break")
    for day, minutes in per_day.items():
        if minutes > constraints.max_minutes_per_day:
            problems.append(f"{day} has {minutes} minutes, over the daily maximum")
    return problems
