"""The student's class meetings, as times the plan must keep free."""

from datetime import datetime

from lms.meetings import class_times
from lms.selectors import enrolled_courses

from ..planning.types import Interval


def in_class(student, start: datetime, end: datetime) -> list[Interval]:
    return [Interval(c.start, c.end) for c in class_times(enrolled_courses(student), start, end)]
