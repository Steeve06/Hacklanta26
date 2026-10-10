"""Free study time: weekly wall-clock blocks turned into absolute intervals, minus blackouts."""

from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta

from .types import Interval


def _wall(day: date, at: time, tz) -> datetime:
    """A wall-clock time on a local day. Ambiguous times take the first occurrence; times inside
    a spring-forward gap move forward by the gap. Returned in UTC so that adding minutes means
    elapsed time, not wall-clock time."""
    return datetime.combine(day, at).replace(tzinfo=tz, fold=0).astimezone(UTC)


def day_bounds(day: date, tz) -> Interval:
    return Interval(_wall(day, time(0), tz), _wall(day + timedelta(days=1), time(0), tz))


def subtract(intervals: list[Interval], holes: Iterable[Interval]) -> list[Interval]:
    result = intervals
    for hole in holes:
        next_result = []
        for iv in result:
            if hole.end <= iv.start or hole.start >= iv.end:
                next_result.append(iv)
                continue
            if hole.start > iv.start:
                next_result.append(Interval(iv.start, hole.start))
            if hole.end < iv.end:
                next_result.append(Interval(hole.end, iv.end))
        result = next_result
    return result


def round_up(moment: datetime, minutes: int = 5) -> datetime:
    discard = timedelta(
        minutes=moment.minute % minutes, seconds=moment.second, microseconds=moment.microsecond
    )
    if not discard:
        return moment
    return moment - discard + timedelta(minutes=minutes)


def free_time(
    blocks: Iterable[tuple[int, time, time]],
    blackouts: Iterable[Interval],
    *,
    tz,
    start: datetime,
    end: datetime,
    earliest: time,
    latest: time,
) -> dict[date, list[Interval]]:
    """Available intervals per local date between `start` and `end`."""
    by_weekday: dict[int, list[tuple[time, time]]] = {}
    for weekday, s, e in blocks:
        lo, hi = max(s, earliest), min(e, latest)
        if lo < hi:
            by_weekday.setdefault(weekday, []).append((lo, hi))
    holes = sorted(
        (Interval(b.start.astimezone(UTC), b.end.astimezone(UTC)) for b in blackouts),
        key=lambda b: b.start,
    )
    first_day = start.astimezone(tz).date()
    last_day = end.astimezone(tz).date()
    result: dict[date, list[Interval]] = {}
    day = first_day
    lower = round_up(start.astimezone(UTC))
    end = end.astimezone(UTC)
    while day <= last_day:
        raw = [
            Interval(_wall(day, s, tz), _wall(day, e, tz))
            for s, e in sorted(by_weekday.get(day.weekday(), []))
        ]
        merged: list[Interval] = []
        for iv in raw:
            if merged and iv.start <= merged[-1].end:
                merged[-1] = Interval(merged[-1].start, max(merged[-1].end, iv.end))
            else:
                merged.append(iv)
        clipped = [
            Interval(max(iv.start, lower), min(iv.end, end))
            for iv in merged
            if iv.end > lower and iv.start < end
        ]
        free = [iv for iv in subtract(clipped, holes) if iv.minutes >= 10]
        if free:
            result[day] = free
        day += timedelta(days=1)
    return result
