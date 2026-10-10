"""Weekly XP leaderboard among classmates (students who share a course with you). XP comes from
study-check tries: 10 per right answer, 20 for answering every card in time."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db.models import Sum

from accounts.models import User
from lms.models import Enrollment
from lms.selectors import enrolled_courses

from ..models import CheckAttempt, Streak

LIMIT = 50


@dataclass
class Row:
    rank: int
    student_id: int
    name: str
    xp: int
    streak: int
    is_me: bool


def week_start(student, now: datetime) -> date:
    today = now.astimezone(student.tz).date()
    return today - timedelta(days=today.weekday())


def display_name(user: User) -> str:
    initial = f" {user.last_name[0]}." if user.last_name else ""
    return f"{user.first_name}{initial}".strip() or "Student"


def classmates(student, course_id: int | None = None):
    courses = enrolled_courses(student)
    if course_id is not None:
        courses = courses.filter(pk=course_id)
    ids = set(
        Enrollment.objects.filter(
            course__in=courses, role=Enrollment.Role.STUDENT, user__is_active=True
        ).values_list("user_id", flat=True)
    )
    ids.add(student.id)
    return User.objects.filter(pk__in=ids)


def board(student, now: datetime, course_id: int | None = None) -> tuple[date, list[Row]]:
    """This week's (Monday to today, in the viewer's time zone) XP for the viewer's classmates,
    highest first. Ties go to the longer streak, then by name. The viewer is always included, even
    outside the top rows."""
    start = week_start(student, now)
    people = list(classmates(student, course_id))
    since = datetime.combine(start, time(0), tzinfo=student.tz)
    xp = dict(
        CheckAttempt.objects.filter(study_check__student__in=people, finished_at__gte=since)
        .values_list("study_check__student_id")
        .annotate(total=Sum("xp"))
        .values_list("study_check__student_id", "total")
    )
    streaks = dict(Streak.objects.filter(student__in=people).values_list("student_id", "current"))
    ordered = sorted(
        people, key=lambda u: (-(xp.get(u.id) or 0), -streaks.get(u.id, 0), display_name(u))
    )
    rows = []
    for position, user in enumerate(ordered, start=1):
        if position > LIMIT and user.id != student.id:
            continue
        rows.append(
            Row(
                position,
                user.id,
                display_name(user),
                xp.get(user.id) or 0,
                streaks.get(user.id, 0),
                user.id == student.id,
            )  # fmt: skip
        )
    return start, rows
