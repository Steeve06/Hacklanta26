from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from accounts.clock import now as clock_now
from notifications.models import Notification
from pulse.services.planner import plan

from .factories import AssessmentFactory, CourseFactory, UserFactory, enroll
from .test_pulse import client_for, make_student

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return UserFactory(role="admin", is_staff=True, is_superuser=True)


@pytest.fixture
def behind():
    student = make_student()
    course = CourseFactory(code="PSY 101")
    enroll(student, course)
    AssessmentFactory(course=course, est_minutes=60, due_at=timezone.now() + timedelta(hours=2))
    plan(student, reason="test")
    return student


def test_demo_endpoints_404_when_demo_mode_off(admin):
    with override_settings(DEMO_MODE=False):
        assert client_for(admin).get("/api/v1/demo/students").status_code == 404


def test_students_cannot_use_demo_endpoints(behind):
    response = client_for(behind).post("/api/v1/demo/scan-notifications", {}, format="json")
    assert response.status_code == 403


def test_scan_sends_now_even_in_quiet_hours(admin, behind):
    response = client_for(admin).post(
        "/api/v1/demo/scan-notifications", {"student_id": behind.id}, format="json"
    )
    assert response.status_code == 200
    assert response.data["created"] >= 1
    assert Notification.objects.filter(student=behind, sent_at__isnull=False).exists()


def test_time_travel_moves_only_that_students_clock(admin, behind):
    other = make_student()
    response = client_for(admin).post(
        "/api/v1/demo/time-travel", {"student_id": behind.id, "hours": 24}, format="json"
    )
    assert response.status_code == 200
    assert response.data["offset_minutes"] == 24 * 60
    behind.refresh_from_db()
    assert clock_now(behind) - timezone.now() > timedelta(hours=23)
    assert abs(clock_now(other) - timezone.now()) < timedelta(minutes=1)

    me = client_for(behind).get("/api/v1/me").data
    assert me["demo_mode"] is True

    reset = client_for(admin).post(
        "/api/v1/demo/time-travel", {"student_id": behind.id, "reset": True}, format="json"
    )
    assert reset.data["offset_minutes"] == 0


def test_time_travel_never_goes_before_real_now(admin, behind):
    response = client_for(admin).post(
        "/api/v1/demo/time-travel", {"student_id": behind.id, "hours": -5}, format="json"
    )
    assert response.data["offset_minutes"] == 0


def test_replan_returns_fresh_status(admin, behind):
    response = client_for(admin).post(f"/api/v1/demo/replan/{behind.id}")
    assert response.status_code == 200
    assert response.data["state"] in {"good", "medium", "bad"}
    listing = client_for(admin).get("/api/v1/demo/students")
    assert any(row["id"] == behind.id for row in listing.data)


def test_cron_endpoint_requires_token(behind):
    client = client_for(behind)
    with override_settings(CRON_TOKEN=""):
        assert client.post("/api/cron").status_code == 404
    with override_settings(CRON_TOKEN="s3cret"):
        assert client.post("/api/cron", HTTP_X_CRON_TOKEN="nope").status_code == 403
        response = client.post("/api/cron", HTTP_X_CRON_TOKEN="s3cret")
        assert response.status_code == 200
        assert response.json()["notifications"] >= 1


def test_run_periodic_command(behind):
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command("run_periodic", stdout=out)
    assert "Notifications created" in out.getvalue()


def test_scan_releases_reminders_queued_for_quiet_hours(admin, behind):
    from notifications.engine import scan_student

    queued = scan_student(behind)
    Notification.objects.filter(pk__in=[n.pk for n in queued]).update(
        scheduled_for=timezone.now() + timedelta(hours=8)
    )
    client_for(admin).post(
        "/api/v1/demo/scan-notifications", {"student_id": behind.id}, format="json"
    )
    assert not Notification.objects.filter(student=behind, sent_at__isnull=True).exists()
