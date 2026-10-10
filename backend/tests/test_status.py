from datetime import time, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from lms.models import Submission
from pulse.models import Schedule, Session
from pulse.services import status
from pulse.services.planner import plan

from .factories import AssessmentFactory, ChapterFactory, CourseFactory, enroll
from .test_pulse import make_student

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("score", "previous", "expected"),
    [
        (80, None, "good"),
        (74, None, "medium"),
        (44, None, "bad"),
        (72, "good", "good"),
        (69, "good", "medium"),
        (78, "medium", "medium"),
        (80, "medium", "good"),
        (41, "medium", "medium"),
        (39, "medium", "bad"),
        (49, "bad", "bad"),
        (50, "bad", "medium"),
    ],
)
def test_bands_with_hysteresis(score, previous, expected):
    assert status.band(score, previous) == expected


def student_in_course(**kwargs):
    student = make_student(**kwargs)
    course = CourseFactory()
    enroll(student, course)
    return student, course


def test_new_student_is_good_with_fresh_start():
    student, course = student_in_course()
    ChapterFactory(course=course, available_from=timezone.now() - timedelta(days=30))
    plan(student, reason="test")
    result = status.compute(student)
    assert result["overall"]["state"] == "good"
    assert result["fresh_start"] is True
    assert result["moment"]["kind"] == "fresh_start"


def test_missed_heavy_item_forces_at_least_medium():
    student, course = student_in_course()
    now = timezone.now()
    AssessmentFactory(
        course=course,
        weight_pct=15,
        due_at=now - timedelta(days=3),
        cutoff_at=now - timedelta(days=2),
    )
    done = AssessmentFactory(
        course=course, weight_pct=5, due_at=now - timedelta(days=4), cutoff_at=None
    )
    Submission.objects.create(
        assessment=done, student=student, status="submitted", submitted_at=now - timedelta(days=5)
    )
    plan(student, reason="test")
    result = status.compute(student)
    assert result["overall"]["state"] in ("medium", "bad")
    assert any("Missed" in r for r in result["overall"]["reasons"])


def with_history(student, course):
    done = AssessmentFactory(course=course, due_at=timezone.now() - timedelta(days=2))
    Submission.objects.create(
        assessment=done, student=student, status="submitted",
        submitted_at=timezone.now() - timedelta(days=3),
    )  # fmt: skip


def test_a_tight_week_is_a_reason_not_a_bad_status():
    student, course = student_in_course(blocks=[(0, time(19), time(19, 30))])
    with_history(student, course)
    AssessmentFactory(
        course=course, title="Big essay", est_minutes=400,
        due_at=timezone.now() + timedelta(days=2),
    )  # fmt: skip
    plan(student, reason="test")
    result = status.compute(student)
    assert result["overall"]["state"] != "bad"
    assert any("Big essay" in r and "won't fully fit" in r for r in result["overall"]["reasons"])


def test_no_study_time_at_all_forces_bad():
    student, course = student_in_course(blocks=[])
    with_history(student, course)
    AssessmentFactory(course=course, due_at=timezone.now() + timedelta(days=2))
    plan(student, reason="test")
    report = Schedule.objects.get(student=student, is_active=True).overload_report
    assert report["suggestions"][0]["text"] == "Add at least one weekly study block."
    assert status.compute(student)["overall"]["state"] == "bad"


def test_reasons_mention_due_soon_and_not_started():
    student, course = student_in_course()
    AssessmentFactory(
        course=course, title="Essay", weight_pct=20, due_at=timezone.now() + timedelta(hours=20)
    )
    old = AssessmentFactory(course=course, due_at=timezone.now() - timedelta(days=2))
    Submission.objects.create(
        assessment=old,
        student=student,
        status="submitted",
        submitted_at=timezone.now() - timedelta(days=3),
    )
    plan(student, reason="test")
    reasons = status.compute(student)["overall"]["reasons"]
    assert any("Essay due in" in r and "not started" in r for r in reasons)


def test_skipped_sessions_lower_adherence_and_cache_invalidates(django_capture_on_commit_callbacks):
    student, course = student_in_course()
    AssessmentFactory(course=course, est_minutes=200, due_at=timezone.now() + timedelta(days=6))
    schedule = plan(student, reason="test")
    client = APIClient()
    client.force_authenticate(student)
    first = client.get("/api/v1/pulse/status").data
    past = timezone.now() - timedelta(days=1)
    for s in schedule.sessions.all()[:3]:
        Session.objects.filter(pk=s.pk).update(
            start=past - timedelta(hours=1), end=past, status="skipped"
        )
    target = schedule.sessions.filter(status="planned").first()
    with django_capture_on_commit_callbacks(execute=True):
        client.patch(f"/api/v1/pulse/sessions/{target.id}", {"status": "skipped"}, format="json")
    second = client.get("/api/v1/pulse/status").data
    assert (
        second["overall"]["components"]["adherence"] < first["overall"]["components"]["adherence"]
    )


def test_celebrate_moment_after_on_time_submission():
    student, course = student_in_course()
    homework = AssessmentFactory(course=course)
    old = AssessmentFactory(course=course, due_at=timezone.now() - timedelta(days=2))
    Submission.objects.create(
        assessment=old,
        student=student,
        status="submitted",
        submitted_at=timezone.now() - timedelta(days=3),
    )
    Submission.objects.create(
        assessment=homework, student=student, status="submitted", submitted_at=timezone.now()
    )
    plan(student, reason="test")
    moment = status.compute(student)["moment"]
    assert moment["kind"] == "celebrate"
    assert moment["key"] == f"submit-{homework.id}"


def test_status_requires_student():
    _, course = student_in_course()
    client = APIClient()
    client.force_authenticate(course.instructor)
    assert client.get("/api/v1/pulse/status").status_code == 403
