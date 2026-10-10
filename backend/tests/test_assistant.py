from datetime import time, timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from ai import client as ai_client
from assistant import actions, context, fallback
from assistant.models import ChatMessage, Conversation
from pulse.models import Blackout, Schedule, Session
from pulse.services.planner import plan

from .factories import AssessmentFactory, ChapterFactory, CourseFactory, StudentFactory, enroll
from .test_pulse import client_for, make_student

pytestmark = pytest.mark.django_db
URL = "/api/v1/assistant"


@pytest.fixture
def student():
    student = make_student(blocks=[(d, time(8), time(22)) for d in range(7)])
    course = CourseFactory(code="PSY 101")
    enroll(student, course)
    chapter = ChapterFactory(course=course)
    homework = AssessmentFactory(
        course=course, est_minutes=180, due_at=timezone.now() + timedelta(days=6)
    )
    homework.chapters.set([chapter])
    plan(student, reason="test")
    return student


def upcoming(student):
    return (
        Session.objects.filter(
            schedule__student=student,
            schedule__is_active=True,
            status="planned",
            start__gt=timezone.now(),
        )
        .exclude(kind="chapter_quiz")
        .order_by("start")
    )


def send(client, capture, text):
    with capture(execute=True):
        response = client.post(f"{URL}/messages", {"text": text}, format="json")
    assert response.status_code == 202, response.data
    return client.get(f"{URL}/conversation").data["messages"][-1]


@pytest.fixture
def ai_on(settings):
    settings.AI_PROVIDER = "anthropic"
    settings.AI_API_KEY = "test-key"
    cache.clear()
    return settings


def model_answers(monkeypatch, answer, calls=None):
    def call(model, system, user, schema, max_tokens):
        if calls is not None:
            calls.append(user)
        return answer, 100, 40

    monkeypatch.setitem(ai_client.PROVIDERS, "anthropic", call)


class TestConversation:
    def test_students_must_finish_onboarding(self):
        newcomer = StudentFactory()
        assert client_for(newcomer).get(f"{URL}/conversation").status_code == 403

    def test_empty_until_the_first_message(self, student):
        data = client_for(student).get(f"{URL}/conversation").data
        assert data["id"] is None and data["messages"] == []

    def test_skip_is_proposed_then_applied_on_confirm(
        self, student, django_capture_on_commit_callbacks
    ):
        client = client_for(student)
        target = upcoming(student).first()
        reply = send(client, django_capture_on_commit_callbacks, "Can you skip my next session?")
        assert reply["state"] == "done" and reply["proposal"] == "pending"
        assert [c["type"] for c in reply["changes"]] == ["skip_session"]
        assert target.title in reply["changes"][0]["summary"]
        target.refresh_from_db()
        assert target.status == "planned"

        done = client.post(f"{URL}/messages/{reply['id']}/confirm")
        assert done.status_code == 200 and done.data["proposal"] == "applied"
        target.refresh_from_db()
        assert target.status == "skipped"
        again = client.post(f"{URL}/messages/{reply['id']}/confirm")
        assert again.status_code == 400

    def test_decline_changes_nothing(self, student, django_capture_on_commit_callbacks):
        client = client_for(student)
        reply = send(client, django_capture_on_commit_callbacks, "I'm busy tomorrow evening")
        assert client.post(f"{URL}/messages/{reply['id']}/decline").data["proposal"] == "declined"
        assert not Blackout.objects.filter(student=student).exists()

    def test_busy_time_becomes_a_blackout(self, student, django_capture_on_commit_callbacks):
        client = client_for(student)
        reply = send(client, django_capture_on_commit_callbacks, "I'm working a shift tomorrow")
        assert [c["type"] for c in reply["changes"]] == ["block_time"]
        client.post(f"{URL}/messages/{reply['id']}/confirm")
        blackout = Blackout.objects.get(student=student)
        tomorrow = (timezone.now().astimezone(student.tz) + timedelta(days=1)).date()
        assert blackout.start.astimezone(student.tz).date() == tomorrow

    def test_one_message_at_a_time(self, student):
        client = client_for(student)
        conversation = Conversation.objects.create(student=student)
        ChatMessage.objects.create(
            conversation=conversation, role="assistant", state=ChatMessage.State.PENDING
        )
        response = client.post(f"{URL}/messages", {"text": "hello"}, format="json")
        assert response.status_code == 400

    def test_a_new_suggestion_replaces_the_open_one(
        self, student, django_capture_on_commit_callbacks
    ):
        client = client_for(student)
        first = send(client, django_capture_on_commit_callbacks, "skip my next session")
        send(client, django_capture_on_commit_callbacks, "I'm busy tomorrow evening")
        old = ChatMessage.objects.get(pk=first["id"])
        assert old.proposal == "declined"

    def test_other_students_cannot_touch_my_suggestions(
        self, student, django_capture_on_commit_callbacks
    ):
        reply = send(client_for(student), django_capture_on_commit_callbacks, "skip my next one")
        intruder = make_student()
        assert client_for(intruder).post(f"{URL}/messages/{reply['id']}/confirm").status_code == 404

    def test_starting_over_closes_the_conversation(
        self, student, django_capture_on_commit_callbacks
    ):
        client = client_for(student)
        send(client, django_capture_on_commit_callbacks, "what's next?")
        assert client.delete(f"{URL}/conversation").status_code == 204
        assert client.get(f"{URL}/conversation").data["messages"] == []
        assert Conversation.objects.filter(student=student, closed_at__isnull=False).count() == 1


class TestChecks:
    def test_sessions_of_other_students_are_rejected(self, student):
        other = make_student()
        enroll(other, CourseFactory())
        AssessmentFactory(course=other.enrollments.first().course, est_minutes=60)
        plan(other, reason="test")
        foreign = Session.objects.filter(schedule__student=other).first()
        with pytest.raises(actions.Rejected):
            actions.check(student, {"type": "skip_session", "session_id": foreign.id})

    def test_moves_must_land_in_free_time(self, student):
        session = upcoming(student).first()
        day = (timezone.now() + timedelta(days=2)).astimezone(student.tz).date()
        night = f"{day.isoformat()}T03:00"
        with pytest.raises(actions.Rejected, match="free study time"):
            actions.check(
                student, {"type": "move_session", "session_id": session.id, "start": night}
            )

    def test_a_moved_session_stays_put_when_the_plan_is_rebuilt(self, student):
        session = upcoming(student).first()
        day = (timezone.now() + timedelta(days=3)).astimezone(student.tz).date()
        free_slot = f"{day.isoformat()}T08:00"
        checked = actions.check(
            student, {"type": "move_session", "session_id": session.id, "start": free_slot}
        )
        actions.apply_all(student, [checked.data])
        plan(student, reason="test")
        active = Schedule.objects.get(student=student, is_active=True)
        kept = active.sessions.get(start=checked.data["start"])
        assert kept.locked is True

    @pytest.mark.parametrize(
        ("change", "message"),
        [
            ({"max_hours_per_week": 50}, "between 2 and 40"),
            ({"max_hours_per_day": 0.5}, "between 1 and 12"),
            ({"session_minutes": 30}, "25, 50 or 90"),
            ({"max_hours_per_week": 3, "max_hours_per_day": 4}, "can't be more"),
            ({"earliest_time": "22:00", "latest_time": "07:00"}, "after the earliest"),
        ],
    )
    def test_limit_changes_are_checked(self, student, change, message):
        with pytest.raises(actions.Rejected, match=message):
            actions.check(student, {"type": "set_limits", **change})

    def test_cannot_remove_all_study_time(self):
        lonely = make_student(blocks=[(2, time(18), time(21))])
        with pytest.raises(actions.Rejected, match="no study time"):
            actions.check(lonely, {"type": "set_day_availability", "weekday": 2, "blocks": []})

    def test_confirm_rechecks_and_applies_nothing_if_any_change_fails(self, student):
        first, second = upcoming(student)[:2]
        stored = [
            actions.check(student, {"type": "skip_session", "session_id": first.id}).data,
            actions.check(student, {"type": "skip_session", "session_id": second.id}).data,
        ]
        Session.objects.filter(pk=second.pk).update(status="done")
        conversation = Conversation.objects.create(student=student)
        message = ChatMessage.objects.create(
            conversation=conversation, role="assistant", actions=stored,
            proposal=ChatMessage.Proposal.PENDING,
        )  # fmt: skip
        response = client_for(student).post(f"{URL}/messages/{message.id}/confirm")
        assert response.data["proposal"] == "failed"
        assert "already marked done" in response.data["proposal_note"]
        first.refresh_from_db()
        assert first.status == "planned"


class TestModel:
    def test_model_reply_keeps_valid_changes_and_explains_the_rest(
        self, student, ai_on, monkeypatch, django_capture_on_commit_callbacks
    ):
        session = upcoming(student).first()
        calls = []
        model_answers(
            monkeypatch,
            {
                "reply": "Done deal: I'll skip it and lighten Fridays.",
                "actions": [
                    {"type": "skip_session", "session_id": session.id},
                    {"type": "skip_session", "session_id": 999999},
                ],
            },
            calls,
        )
        reply = send(client_for(student), django_capture_on_commit_callbacks, "skip it please")
        assert [c["type"] for c in reply["changes"]] == ["skip_session"]
        assert "couldn't set up part of that" in reply["text"]
        assert ChatMessage.objects.get(pk=reply["id"]).used_ai is True
        assert student.email not in calls[0]
        assert "skip it please" in calls[0]

    def test_bad_model_output_falls_back_to_keywords(
        self, student, ai_on, monkeypatch, django_capture_on_commit_callbacks
    ):
        monkeypatch.setattr(ai_client.time, "sleep", lambda s: None)
        model_answers(monkeypatch, {"reply": "", "actions": "nope"})
        reply = send(client_for(student), django_capture_on_commit_callbacks, "skip my next one")
        assert [c["type"] for c in reply["changes"]] == ["skip_session"]
        assert ChatMessage.objects.get(pk=reply["id"]).used_ai is False

    def test_context_has_times_in_the_students_zone_and_no_personal_details(self, student):
        conversation = Conversation.objects.create(student=student)
        data = context.build(student, conversation, before_id=10**9)
        assert data["timezone"] == str(student.tz)
        assert data["sessions"] and "id" in data["sessions"][0]
        flat = str(data)
        assert student.email not in flat and student.first_name not in flat


class TestFallback:
    def test_recurring_preferences_rebuild_the_plan(self, student):
        result = fallback.answer(student, "Please keep Sundays free")
        assert [a["type"] for a in result.actions] == ["schedule_note"]

    def test_evening_busy_time_covers_only_the_evening(self, student):
        result = fallback.answer(student, "I'm busy Friday evening")
        action = result.actions[0]
        assert action["type"] == "block_time"
        latest = student.profile.latest_time.strftime("%H:%M")
        assert action["start"][11:] >= "17:00"
        assert action["end"][11:] == min(latest, "23:59")

    def test_questions_get_an_answer_without_changes(self, student):
        result = fallback.answer(student, "what's next?")
        assert result.actions == [] and "Next up" in result.text

    def test_unknown_requests_get_help(self, student):
        result = fallback.answer(student, "hello there")
        assert result.actions == [] and "skip or move a session" in result.text
