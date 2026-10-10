from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from lms.meetings import class_times
from lms.models import CourseMeeting
from pulse.services import sessions as session_service
from pulse.services.planner import plan

from .factories import AssessmentFactory, CourseFactory, enroll
from .test_pulse import client_for, make_student

pytestmark = pytest.mark.django_db
NY = ZoneInfo("America/New_York")


@pytest.fixture
def course_with_class():
    course = CourseFactory(code="CS 201")
    term = course.term
    term.start_date = date.today() - timedelta(days=30)
    term.end_date = date.today() + timedelta(days=60)
    term.save()
    for day in range(7):
        CourseMeeting.objects.create(
            course=course, weekday=day, start_time=time(10), end_time=time(12), location="Room 1"
        )
    return course


def test_class_times_are_real_moments_in_the_campus_zone(course_with_class):
    start = datetime(2026, 10, 12, tzinfo=NY)
    times = class_times([course_with_class], start, start + timedelta(days=2))
    assert [(t.start.astimezone(NY).hour, t.end.astimezone(NY).hour) for t in times] == [
        (10, 12)
    ] * 2
    assert times[0].location == "Room 1" and times[0].course_code == "CS 201"


def test_class_times_stay_inside_the_term(course_with_class):
    term = course_with_class.term
    after = datetime.combine(term.end_date + timedelta(days=1), time(0), tzinfo=NY)
    assert class_times([course_with_class], after, after + timedelta(days=7)) == []


def test_the_plan_never_overlaps_class(course_with_class):
    student = make_student(blocks=[(d, time(8), time(14)) for d in range(7)])
    enroll(student, course_with_class)
    AssessmentFactory(
        course=course_with_class, est_minutes=600, due_at=timezone.now() + timedelta(days=5)
    )
    schedule = plan(student, reason="test")
    sessions = list(schedule.sessions.all())
    assert sessions
    for s in sessions:
        local_start, local_end = s.start.astimezone(NY), s.end.astimezone(NY)
        assert local_end.time() <= time(10) or local_start.time() >= time(12), s


def test_a_session_cannot_be_moved_into_class(course_with_class):
    student = make_student(blocks=[(d, time(8), time(14)) for d in range(7)])
    enroll(student, course_with_class)
    AssessmentFactory(
        course=course_with_class, est_minutes=120, due_at=timezone.now() + timedelta(days=5)
    )
    session = plan(student, reason="test").sessions.filter(start__gt=timezone.now()).first()
    day = (timezone.now() + timedelta(days=2)).astimezone(NY).date()
    with pytest.raises(Exception, match="in class"):
        session_service.check_move(student, session, datetime.combine(day, time(10, 30), tzinfo=NY))


def test_courses_syllabus_and_calendar_show_class_times(course_with_class):
    student = make_student()
    enroll(student, course_with_class)
    client = client_for(student)
    course = client.get(f"/api/v1/courses/{course_with_class.id}").data
    assert course["meetings"][0] == {
        "weekday": 0, "start_time": "10:00:00", "end_time": "12:00:00",
        "location": "Room 1", "timezone": "America/New_York",
    }  # fmt: skip
    week = client.get("/api/v1/pulse/course-calendar").data
    assert len(week["classes"]) == 7 and week["classes"][0]["course_code"] == "CS 201"
