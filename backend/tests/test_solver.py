from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pulse.planning.feedback import parse_feedback
from pulse.planning.slots import free_time
from pulse.planning.solver import Solver, buffer_for, check_hard_constraints
from pulse.planning.types import Constraints, Interval, TaskSpec

NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


def constraints(**kw):
    base = dict(
        tz=NY, now=NOW, horizon_end=NOW + timedelta(days=30),
        max_minutes_per_day=180, session_minutes=50,
    )  # fmt: skip
    return Constraints(**{**base, **kw})


def task(key, minutes, deadline_days, *, deps=(), weight=5.0, splittable=True, lag=0, course=1):
    return TaskSpec(
        key=key, source_type="assessment", source_id=hash(key) % 1000, part="x", course_id=course,
        course_code="TST", title=key, kind="assignment", minutes=minutes,
        min_chunk=min(25, minutes), splittable=splittable, not_before=NOW,
        deadline=NOW + timedelta(days=deadline_days), weight=weight, depends_on=list(deps),
        lag_after_deps=timedelta(hours=lag),
    )  # fmt: skip


def evenings(days=7, start=time(18), end=time(21)):
    return [(d, start, end) for d in range(days)]


def solve(tasks, blocks, c=None, blackouts=()):
    c = c or constraints()
    free = free_time(blocks, blackouts, tz=c.tz, start=c.now, end=c.horizon_end,
                     earliest=time(6), latest=time(23, 59))  # fmt: skip
    result = Solver(tasks, free, c).solve()
    return result, check_hard_constraints(result, tasks, free, c), free


def placed_minutes(result, key):
    return sum(
        p.minutes for p in result.placements if p.task_key == key and p.kind != "chapter_quiz"
    )


def test_simple_plan_meets_all_hard_constraints():
    tasks = [task("a", 120, 5), task("b", 60, 3, deps=["a"]), task("c", 45, 10)]
    result, problems, _ = solve(tasks, evenings())
    assert problems == []
    assert not result.shortfalls
    a_end = max(p.end for p in result.placements if p.task_key == "a")
    b_start = min(p.start for p in result.placements if p.task_key == "b")
    assert b_start >= a_end


def test_sessions_respect_length_and_break():
    result, problems, _ = solve([task("a", 200, 10)], evenings())
    assert problems == []
    assert all(p.minutes <= 50 for p in result.placements)


def test_buffer_is_respected():
    t = task("a", 50, 4)
    result, problems, _ = solve([t], evenings())
    assert problems == []
    assert max(p.end for p in result.placements) <= t.deadline - buffer_for(t, NOW)


def test_overload_reports_shortfall_instead_of_dropping():
    tasks = [task("big", 600, 2), task("small", 30, 2)]
    result, problems, _ = solve(tasks, evenings(), constraints(max_minutes_per_day=60))
    assert problems == []
    reported = {s.task_key: s.minutes for s in result.shortfalls}
    for t in tasks:
        assert placed_minutes(result, t.key) + reported.get(t.key, 0) == t.minutes


def test_due_inside_buffer_is_scheduled_early_and_flagged():
    t = task("urgent", 30, 0.4)
    result, problems, _ = solve([t], [(d, time(0), time(23, 59)) for d in range(7)])
    assert problems == []
    assert placed_minutes(result, "urgent") == 30
    assert "urgent" in result.at_risk


def test_higher_weight_first_when_due_together():
    heavy = task("heavy", 50, 1.4, weight=20)
    light = task("light", 50, 1.4, weight=2)
    result, _, _ = solve([light, heavy], evenings(), constraints(max_minutes_per_day=50))
    assert placed_minutes(result, "heavy") == 50
    assert any(s.task_key == "light" for s in result.shortfalls)


def test_reply_lag_after_original_post():
    original = task("orig", 30, 6, splittable=False)
    replies = task("replies", 20, 6, deps=["orig"], lag=24, splittable=False)
    result, problems, _ = solve([original, replies], evenings())
    assert problems == []
    o_end = max(p.end for p in result.placements if p.task_key == "orig")
    r_start = min(p.start for p in result.placements if p.task_key == "replies")
    assert r_start >= o_end + timedelta(hours=24)


def test_blackouts_are_avoided():
    blackout = Interval(NOW, NOW + timedelta(days=3))
    result, problems, _ = solve([task("a", 100, 10)], evenings(), blackouts=[blackout])
    assert problems == []
    assert all(p.start >= blackout.end for p in result.placements)


def test_unsplittable_task_longer_than_any_block_is_reported():
    t = task("long", 240, 10, splittable=False)
    result, _, _ = solve([t], evenings())
    assert result.shortfalls[0].task_key == "long"


def test_feedback_less_on_weekends():
    factors, hours = parse_feedback("less on weekends and more mornings")
    assert factors == {5: 0.5, 6: 0.5}
    assert hours == (6, 12)
    assert parse_feedback("no fridays")[0] == {4: 0.0}


class TestDST:
    def test_spring_forward_day_has_no_duplicates_or_gaps(self):
        now = datetime(2027, 3, 13, 5, 0, tzinfo=UTC)
        c = constraints(now=now, horizon_end=now + timedelta(days=3))
        blocks = [(d, time(1), time(4)) for d in range(7)]
        free = free_time(blocks, [], tz=NY, start=now, end=c.horizon_end,
                         earliest=time(0), latest=time(23, 59))  # fmt: skip
        sunday = free[date(2027, 3, 14)]
        assert sum(iv.minutes for iv in sunday) == 120
        result = Solver([task("a", 300, 3)], free, c).solve()
        assert check_hard_constraints(result, [task("a", 300, 3)], free, c) == []
        starts = [p.start for p in result.placements]
        assert len(starts) == len(set(starts))

    def test_fall_back_day_keeps_wall_clock_block(self):
        now = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
        blocks = [(6, time(1), time(3))]
        free = free_time(blocks, [], tz=NY, start=now, end=now + timedelta(days=2),
                         earliest=time(0), latest=time(23, 59))  # fmt: skip
        sunday = free[date(2026, 11, 1)]
        assert sunday[0].start.astimezone(NY).hour == 1
        assert sum(iv.minutes for iv in sunday) == 180

    def test_evening_block_same_local_time_across_dst(self):
        now = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
        free = free_time([(d, time(18), time(19)) for d in range(7)], [], tz=NY, start=now,
                         end=now + timedelta(days=5), earliest=time(0), latest=time(23, 59))  # fmt: skip
        assert {ivs[0].start.astimezone(NY).hour for ivs in free.values()} == {18}


task_strategy = st.builds(
    lambda i, minutes, days, weight, splittable: task(
        f"t{i}", minutes, days, weight=weight, splittable=splittable or minutes <= 50, course=i % 3
    ),
    i=st.integers(0, 10_000),
    minutes=st.integers(10, 240),
    days=st.floats(0.2, 25),
    weight=st.floats(0.5, 30),
    splittable=st.booleans(),
)
block_strategy = st.tuples(
    st.integers(0, 6),
    st.integers(6, 20).map(lambda h: time(h)),
    st.integers(1, 4),
).map(lambda b: (b[0], b[1], time(min(23, b[1].hour + b[2]))))


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    tasks=st.lists(task_strategy, min_size=1, max_size=12, unique_by=lambda t: t.key),
    blocks=st.lists(block_strategy, min_size=0, max_size=10),
    max_hours=st.integers(1, 6),
    week_hours=st.integers(2, 40),
    session=st.sampled_from([25, 50, 90]),
    dep_pairs=st.lists(st.tuples(st.integers(0, 11), st.integers(0, 11)), max_size=6),
)
def test_property_no_hard_constraint_is_ever_violated(
    tasks, blocks, max_hours, week_hours, session, dep_pairs
):
    for a, b in dep_pairs:
        if a < b < len(tasks):
            tasks[b].depends_on.append(tasks[a].key)
    c = constraints(
        max_minutes_per_day=max_hours * 60,
        session_minutes=session,
        max_minutes_per_week=week_hours * 60,
    )
    blocks = [(d, s, e) for d, s, e in blocks if e > s]
    result, problems, _ = solve(tasks, blocks, c)
    assert problems == []
    shortfall = {s.task_key: s.minutes for s in result.shortfalls}
    for t in tasks:
        assert placed_minutes(result, t.key) + shortfall.get(t.key, 0) == t.minutes


def week_totals(result, c):
    totals = {}
    for p in result.placements:
        week = c.week_of(p.day)
        totals[week] = totals.get(week, 0) + p.minutes
    return totals


def test_weekly_limit_is_never_exceeded_and_overflow_is_reported():
    c = constraints(max_minutes_per_week=4 * 60, max_minutes_per_day=180)
    tasks = [task(f"t{i}", 120, 12, course=i % 3) for i in range(6)]
    result, problems, _ = solve(tasks, evenings(14), c)
    assert problems == []
    assert all(minutes <= 4 * 60 for minutes in week_totals(result, c).values())
    assert result.shortfalls, "12 hours of work can't fit in two 4-hour weeks"


def test_time_already_spent_this_week_counts_toward_the_limit():
    monday = constraints().week_of(NOW.astimezone(NY).date())
    c = constraints(max_minutes_per_week=3 * 60, week_used={monday: 150})
    result, problems, _ = solve([task("a", 120, 4)], evenings(7), c)
    assert problems == []
    this_week = [p for p in result.placements if c.week_of(p.day) == monday]
    assert sum(p.minutes for p in this_week) <= 30


def suggestions_for(tasks, c, days=6):
    from pulse.services.overload import _capacity_suggestions

    result, _, free = solve(tasks, evenings(7), c)
    return [s["type"] for s in _capacity_suggestions(result, free, c, NOW + timedelta(days=days))]


def test_overload_names_the_weekly_limit_when_it_is_full():
    c = constraints(max_minutes_per_week=2 * 60)
    assert suggestions_for([task(f"t{i}", 120, 6) for i in range(3)], c) == ["raise_weekly_limit"]


def test_overload_names_the_daily_limit_when_free_time_is_left():
    c = constraints(max_minutes_per_day=60)
    assert suggestions_for([task(f"t{i}", 120, 3) for i in range(3)], c, days=3) == [
        "raise_daily_limit"
    ]


def test_overload_suggests_more_free_time_only_when_it_is_used_up():
    c = constraints(max_minutes_per_day=600)
    kinds = suggestions_for([task(f"t{i}", 180, 3) for i in range(4)], c, days=3)
    assert kinds and set(kinds) == {"add_availability"}
