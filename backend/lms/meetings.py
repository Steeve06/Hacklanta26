"""Class meeting times as real moments: each weekly meeting of a course, between two instants,
within the course's term."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings

from .models import CourseMeeting


@dataclass(frozen=True)
class ClassTime:
    course_id: int
    course_code: str
    start: datetime
    end: datetime
    location: str


def campus_tz() -> ZoneInfo:
    return ZoneInfo(settings.CAMPUS_TIMEZONE)


def class_times(courses, start: datetime, end: datetime) -> list[ClassTime]:
    """Every class meeting of `courses` that overlaps [start, end), soonest first."""
    tz = campus_tz()
    meetings = CourseMeeting.objects.filter(course__in=courses).select_related("course__term")
    out: list[ClassTime] = []
    first: date = start.astimezone(tz).date() - timedelta(days=1)
    last: date = end.astimezone(tz).date()
    for m in meetings:
        term = m.course.term
        day = max(first, term.start_date)
        while day <= min(last, term.end_date):
            if day.weekday() == m.weekday:
                begins = datetime.combine(day, m.start_time, tzinfo=tz)
                ends = datetime.combine(day, m.end_time, tzinfo=tz)
                if begins < end and ends > start:
                    out.append(ClassTime(m.course_id, m.course.code, begins, ends, m.location))
            day += timedelta(days=1)
    return sorted(out, key=lambda c: c.start)
