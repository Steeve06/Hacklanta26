"""Coursework that passed its due date without a submission. Each one counts against the streak
once (a freeze, or a reset), and the plan moves on rather than filling up with catch-up work."""

from datetime import datetime, timedelta

from lms.selectors import student_snapshot

from ..models import StreakEvent

RECENT = timedelta(days=7)


def missed_deadlines(student, now: datetime) -> list[dict]:
    snapshot = student_snapshot(student, now)
    rows = [
        a
        for a in snapshot.assessments
        if not a.done and a.status != "excused" and now - RECENT <= a.due_at < now
    ]
    counted = dict(
        StreakEvent.objects.filter(
            student=student, assessment_id__in=[a.id for a in rows]
        ).values_list("assessment_id", "result")
    )
    return [
        {
            "assessment_id": a.id,
            "course_id": a.course_id,
            "course_code": a.course_code,
            "title": a.title,
            "due_at": a.due_at,
            "late_until": a.closes_at if a.closes_at > now else None,
            "streak_result": counted.get(a.id),
        }
        for a in sorted(rows, key=lambda a: a.due_at, reverse=True)
    ]
