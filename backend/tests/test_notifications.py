import json
import random
from datetime import datetime, time, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
import time_machine
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import StudentProfile
from lms.models import DueDateOverride, Submission
from notifications import delivery
from notifications.copy import COPY, SUPPORTIVE
from notifications.engine import dispatch_due, scan_student
from notifications.guardrails import banned_terms, is_safe
from notifications.models import Notification, NotificationTemplate, PushSubscription
from notifications.services import take_action
from pulse.services.planner import plan

from .factories import AssessmentFactory, CourseFactory, enroll
from .test_pulse import make_student

pytestmark = pytest.mark.django_db
NY = ZoneInfo("America/New_York")
NOON = datetime(2026, 10, 7, 12, 0, tzinfo=NY)
SAMPLE = {
    "first_name": "Sam", "title": "Problem Set 2", "course": "CS 201", "hours_left": 5,
    "weight": "10", "streak_days": 6, "streak_months": 1, "late_hours": 30,
}  # fmt: skip


@pytest.fixture(autouse=True)
def fixed_rng():
    random.seed(7)


@pytest.fixture
def at_noon():
    with time_machine.travel(NOON, tick=False):
        yield NOON


def student_with(*assessments_kwargs, **profile):
    student = make_student(**profile)
    StudentProfile.objects.filter(user=student).update(quiet_start=time(22), quiet_end=time(8))
    student.refresh_from_db()
    course = CourseFactory(code="CS 201")
    enroll(student, course)
    items = [AssessmentFactory(course=course, **kw) for kw in assessments_kwargs]
    return student, course, items


def test_every_seeded_template_passes_guardrails():
    assert NotificationTemplate.objects.filter(active=True).count() >= 250
    for trigger, levels in COPY.items():
        for level, texts in levels.items():
            assert len(texts) >= 6, (trigger, level)
            for text in texts:
                rendered = text.format(**SAMPLE)
                assert is_safe(rendered), (trigger, level, text, banned_terms(rendered))
    for texts in SUPPORTIVE.values():
        assert all(is_safe(t.format(**SAMPLE)) for t in texts)


@pytest.mark.parametrize("text", [
    "You're too lazy for this.", "Your family will hear about this.", "Think about your health.",
    "Your score was 4/10.", "I'll report you to the dean.",
])  # fmt: skip
def test_guardrails_block_banned_topics(text):
    assert not is_safe(text)


def test_deadline_word_is_not_a_false_positive():
    assert is_safe("The deadline passed, but the late window is open.")


def test_final_stretch_notification_and_dedupe(at_noon):
    student, _, (hw,) = student_with(
        {"due_at": at_noon + timedelta(hours=20), "title": "Problem Set 2"}
    )
    first = scan_student(student)
    second = scan_student(student)
    assert [n.trigger for n in first] == ["final_stretch"]
    assert second == []
    dispatch_due(at_noon)
    dispatch_due(at_noon)
    assert Notification.objects.filter(student=student, sent_at__isnull=False).count() == 1
    assert "Problem Set 2" in first[0].text


def test_most_severe_trigger_only(at_noon):
    student, _, _ = student_with({"due_at": at_noon + timedelta(hours=2)})
    triggers = [n.trigger for n in scan_student(student)]
    assert triggers == ["code_red"]
    assert Notification.objects.get().channels == ["inapp", "email"]


def test_submission_cancels_queued_reminder(at_noon, django_capture_on_commit_callbacks):
    student, _, (hw,) = student_with({"due_at": at_noon + timedelta(hours=20)})
    with time_machine.travel(at_noon.replace(hour=23), tick=False):
        queued = scan_student(student)[0]
        assert queued.scheduled_for.astimezone(NY).hour == 8
        Submission.objects.create(
            assessment=hw, student=student, status="submitted", submitted_at=timezone.now()
        )
        dispatch_due(at_noon.replace(hour=23) + timedelta(hours=10))
    queued.refresh_from_db()
    assert queued.cancelled_at is not None
    assert queued.sent_at is None


def test_quiet_hours_override_for_deadlines():
    late_evening = datetime(2026, 10, 7, 23, 0, tzinfo=NY)
    with time_machine.travel(late_evening, tick=False):
        student, _, _ = student_with({"due_at": late_evening + timedelta(hours=2)})
        StudentProfile.objects.filter(user=student).update(quiet_hours_override_for_deadlines=True)
        student.refresh_from_db()
        n = scan_student(student)[0]
    assert n.scheduled_for == late_evening


def test_extension_caps_tier_and_sass(at_noon):
    student, _, (hw,) = student_with({"due_at": at_noon + timedelta(hours=2)})
    DueDateOverride.objects.create(
        assessment=hw, student=student, due_at=at_noon + timedelta(hours=50)
    )
    n = scan_student(student)[0]
    assert n.trigger == "upcoming_due"
    assert n.tier == 1
    assert n.sass_level == 1


def test_excused_gets_nothing(at_noon):
    student, _, (hw,) = student_with({"due_at": at_noon + timedelta(hours=2)})
    Submission.objects.create(assessment=hw, student=student, status="excused")
    assert scan_student(student) == []


def test_supportive_mode_uses_supportive_copy(at_noon):
    student, _, _ = student_with({"due_at": at_noon + timedelta(hours=2)})
    StudentProfile.objects.filter(user=student).update(supportive_mode=True)
    student.refresh_from_db()
    n = scan_student(student)[0]
    assert n.sass_level == 0
    title = n.text.split(" is due soon")[0]
    assert n.text in [t.format(**{**SAMPLE, "title": title}) for t in SUPPORTIVE["code_red"]]


def test_three_missed_items_switch_on_supportive_mode(at_noon):
    gone = {"due_at": at_noon - timedelta(days=3), "cutoff_at": at_noon - timedelta(days=2)}
    student, _, _ = student_with(gone, gone, gone)
    scan_student(student)
    student.profile.refresh_from_db()
    assert student.profile.supportive_mode is True


def test_dismissing_supportive_mode_sticks(at_noon):
    gone = {"due_at": at_noon - timedelta(days=3), "cutoff_at": at_noon - timedelta(days=2)}
    student, _, _ = student_with(gone, gone, gone)
    StudentProfile.objects.filter(user=student).update(supportive_mode=True)
    client = APIClient()
    client.force_authenticate(student)
    client.patch("/api/v1/me/profile", {"profile": {"supportive_mode": False}}, format="json")
    scan_student(student)
    student.profile.refresh_from_db()
    assert student.profile.supportive_mode is False


def test_daily_and_per_assignment_caps(at_noon):
    many = [{"due_at": at_noon + timedelta(hours=60 + i)} for i in range(8)]
    student, _, _ = student_with(*many)
    created = scan_student(student)
    assert len([n for n in created if n.trigger != "digest"]) <= 5


def test_storm_collapses_into_a_digest(at_noon):
    many = [{"due_at": at_noon + timedelta(hours=10 + i)} for i in range(5)]
    student, _, _ = student_with(*many)
    created = scan_student(student)
    digests = [n for n in created if n.trigger == "digest"]
    assert len(digests) == 1
    assert all(n.channels == ["inapp"] for n in created if n.trigger != "digest")
    assert "push" in digests[0].channels or "email" in digests[0].channels


def test_no_repeated_text_within_14_days(at_noon):
    student, _, _ = student_with()
    texts = set()
    for day in range(6):
        when = at_noon + timedelta(days=day)
        with time_machine.travel(when, tick=False):
            AssessmentFactory(
                course=student.enrollments.first().course, due_at=when + timedelta(hours=20)
            )
            for n in scan_student(student):
                assert n.text not in texts
                texts.add(n.text)


def test_tone_it_down_and_supportive_after_five(at_noon):
    student, _, _ = student_with({"due_at": at_noon + timedelta(hours=20)})
    n = scan_student(student)[0]
    profile = take_action(student, n, "tone_down")
    assert profile.sass_level == 2
    for _ in range(4):
        profile = take_action(student, n, "tone_down")
    assert profile.sass_level == 1
    assert profile.supportive_mode is True


def test_open_resets_tone_down_streak(at_noon):
    student, _, _ = student_with({"due_at": at_noon + timedelta(hours=20)})
    n = scan_student(student)[0]
    take_action(student, n, "tone_down")
    profile = take_action(student, n, "open")
    assert profile.tone_down_streak == 0


def test_snooze_hides_then_resends(at_noon):
    student, _, _ = student_with({"due_at": at_noon + timedelta(hours=20)})
    scan_student(student)
    dispatch_due(at_noon)
    n = Notification.objects.get()
    client = APIClient()
    client.force_authenticate(student)
    client.post(f"/api/v1/notifications/{n.id}/action", {"action": "snooze"}, format="json")
    assert client.get("/api/v1/notifications").data["results"] == []
    with time_machine.travel(at_noon + timedelta(hours=1, minutes=1), tick=False):
        dispatch_due(at_noon + timedelta(hours=1, minutes=1))
        assert len(client.get("/api/v1/notifications").data["results"]) == 1


def test_win_on_time_submission(at_noon, django_capture_on_commit_callbacks):
    student, _, (hw,) = student_with({"due_at": at_noon + timedelta(days=2), "title": "Essay"})
    client = APIClient()
    client.force_authenticate(student)
    with django_capture_on_commit_callbacks(execute=True):
        client.post(f"/api/v1/assessments/{hw.id}/submissions", {"text": "done"}, format="json")
    win = Notification.objects.get(trigger="win")
    assert "Essay" in win.text


def test_push_payload_has_no_scores_and_expired_subscription_falls_back(at_noon, settings):
    settings.VAPID_PUBLIC_KEY = "pub"
    settings.VAPID_PRIVATE_KEY = "priv"
    student, _, _ = student_with({"due_at": at_noon + timedelta(hours=20)})
    PushSubscription.objects.create(
        user=student, endpoint="https://push.example/abc", keys={"p256dh": "x", "auth": "y"}
    )
    n = scan_student(student)[0]
    payload = json.loads(delivery.push_payload(n))
    assert not any(word in payload["body"].lower() for word in ("score", "/10", "out of"))
    from pywebpush import WebPushException

    gone = WebPushException("gone", response=mock.Mock(status_code=410))
    with mock.patch("pywebpush.webpush", side_effect=gone):
        dispatch_due(at_noon)
    assert not PushSubscription.objects.exists()
    assert len(mail.outbox) == 1


def test_session_reminders(at_noon):
    student, _, _ = student_with({"due_at": at_noon + timedelta(days=6), "est_minutes": 60})
    schedule = plan(student, reason="test")
    first = schedule.sessions.order_by("start").first()
    with time_machine.travel(first.start - timedelta(minutes=5), tick=False):
        assert "session_starting" in [n.trigger for n in scan_student(student)]
    with time_machine.travel(first.end + timedelta(minutes=35), tick=False):
        assert "session_ignored" in [n.trigger for n in scan_student(student)]


def test_inbox_is_private():
    student, _, _ = student_with()
    other = make_student()
    n = Notification.objects.create(
        student=student, trigger="win", tier=0, text="Nice", scheduled_for=timezone.now(),
        sent_at=timezone.now(), dedupe_key="x",
    )  # fmt: skip
    client = APIClient()
    client.force_authenticate(other)
    assert client.post(f"/api/v1/notifications/{n.id}/read").status_code == 404
    assert client.get("/api/v1/notifications").data["results"] == []
