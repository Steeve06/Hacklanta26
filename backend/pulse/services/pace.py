"""How fast this student works compared with estimates, and when they usually study."""

from collections import Counter

from ..models import Session, StudyTask

PACE_MIN, PACE_MAX = 0.5, 2.0
PRODUCTIVE_TOP_HOURS = 4
MIN_SESSIONS_FOR_HOURS = 6


def measured_pace(student) -> float:
    """Minutes actually logged on finished tasks divided by their estimates, clamped."""
    finished = StudyTask.objects.filter(
        student=student, active=False, sessions__status__in=["done", "partial"]
    ).distinct()
    estimated = actual = 0
    for task in finished:
        logged = sum(
            s.completed_minutes
            for s in task.sessions.filter(schedule__is_active=True, status__in=["done", "partial"])
        )
        if logged:
            estimated += task.est_minutes
            actual += logged
    if estimated == 0:
        return 1.0
    return round(min(PACE_MAX, max(PACE_MIN, actual / estimated)), 2)


def productive_hours(student) -> frozenset[int]:
    done = Session.objects.filter(
        schedule__student=student, schedule__is_active=True, status=Session.Status.DONE
    ).values_list("start", flat=True)
    hours = Counter(start.astimezone(student.tz).hour for start in done)
    if sum(hours.values()) < MIN_SESSIONS_FOR_HOURS:
        return frozenset()
    return frozenset(h for h, _ in hours.most_common(PRODUCTIVE_TOP_HOURS))
