from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
import time_machine
from django.utils import timezone
from rest_framework.test import APIClient

from ai.schemas import QuestionOut
from lms.models import ChapterProgress
from notifications.engine import scan_student
from notifications.models import Notification
from pulse.models import Session
from pulse.services.planner import plan
from quizzes.models import BankQuestion, ChapterQuiz, Streak, StreakEvent
from quizzes.services import bank as bank_service
from quizzes.services.streaks import sweep_student
from quizzes.services.windows import sync_windows, window_for

from .factories import ChapterFactory, CourseFactory, enroll
from .test_pulse import make_student

pytestmark = pytest.mark.django_db
NY = ZoneInfo("America/New_York")

BODY = """## Testing

**Spaced practice** spreads study over several sessions and beats cramming for long-term memory.
**Retrieval practice** means recalling material from memory rather than rereading it.
**Interleaving** mixes problem types so learners must choose the right method each time.
**Elaboration** connects new ideas to things the learner already knows well.
**Dual coding** pairs words with pictures so each supports the other in memory.
**Concrete examples** make abstract ideas easier to understand and remember later.
"""


@pytest.fixture
def setup():
    student = make_student(blocks=[(d, time(9), time(21)) for d in range(7)])
    course = CourseFactory(code="PSY 101")
    enroll(student, course)
    chapter = ChapterFactory(course=course, body_md=BODY, title="Learning Strategies")
    return student, course, chapter


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def make_quiz(student, chapters, opens, closes):
    quiz = ChapterQuiz.objects.create(
        student=student,
        scheduled_date=opens.date(),
        opens_at=opens,
        closes_at=closes,
        timezone="America/New_York",
    )
    quiz.chapters.set(chapters)
    from quizzes.services.windows import assemble

    assemble(quiz)
    return quiz


def take(client, quiz, *, wait=25, correct=True):
    started = client.post(f"/api/v1/quizzes/{quiz.id}/start").data
    assert all("correct" not in q for q in started["questions"])
    with time_machine.travel(timezone.now() + timedelta(seconds=wait)):
        answers = {}
        for item in quiz.questions:
            q = BankQuestion.objects.get(pk=item["bank_id"])
            shown = item["order"].index(q.correct_index)
            answers[str(quiz.questions.index(item))] = (
                shown if correct else (shown + 1) % len(item["order"])
            )
        return client.post(f"/api/v1/quizzes/{quiz.id}/submit", {"answers": answers}, format="json")


class TestBank:
    def test_cloze_fallback_builds_valid_questions(self, setup):
        _, _, chapter = setup
        assert bank_service.rebuild_bank(chapter) >= 5
        for q in BankQuestion.objects.filter(chapter=chapter):
            assert len(set(q.options)) == len(q.options)
            assert q.correct_index < len(q.options)

    def test_grounding_rejects_invented_excerpts(self):
        corpus = bank_service.normalize(BODY)
        good = QuestionOut(question="What spreads study over sessions?", type="multiple_choice",
                           options=["Spaced practice", "Cramming", "Rereading", "Highlighting"], correct_index=0,
                           explanation="The chapter says so.", source_excerpt="spreads study over several sessions")  # fmt: skip
        bad = good.model_copy(update={"source_excerpt": "Spaced practice was invented in 1932."})
        dupes = good.model_copy(update={"options": ["A", "A", "B", "C"]})
        assert bank_service.grounded(good, corpus) and bank_service.valid(good)
        assert not bank_service.grounded(bad, corpus)
        assert not bank_service.valid(dupes)

    def test_ai_questions_are_filtered_and_kept(self, setup, settings, monkeypatch):
        _, _, chapter = setup
        settings.AI_PROVIDER, settings.AI_API_KEY = "anthropic", "k"
        from ai import client as ai_client

        def fake(model, system, user, schema, max_tokens):
            base = {"type": "multiple_choice", "options": ["Spaced practice", "Cramming", "Rereading", "Napping"],
                    "correct_index": 0, "explanation": "Stated in the chapter."}  # fmt: skip
            return {"questions": [
                {**base, "question": f"Which spreads study out? ({i})", "source_excerpt": "spreads study over several sessions"}
                for i in range(6)
            ] + [{**base, "question": "Invented?", "source_excerpt": "This sentence is not in the chapter at all."}]}, 10, 10  # fmt: skip

        monkeypatch.setitem(ai_client.PROVIDERS, "anthropic", fake)
        bank_service.rebuild_bank(chapter)
        kept = BankQuestion.objects.filter(chapter=chapter)
        assert kept.count() == 6
        assert all(q.origin == "ai" for q in kept)

    def test_edit_retires_old_questions(self, setup):
        _, _, chapter = setup
        bank_service.rebuild_bank(chapter)
        old_ids = set(BankQuestion.objects.values_list("id", flat=True))
        chapter.body_md = (
            BODY
            + "\n**Self-explanation** asks learners to explain each step in their own words to themselves."
        )
        chapter.save()
        bank_service.rebuild_bank(chapter)
        assert BankQuestion.objects.filter(id__in=old_ids, retired=False).count() == 0
        assert bank_service.usable(chapter).count() >= 5


class TestWindows:
    def test_window_follows_last_study_day(self, setup):
        student, _, chapter = setup
        schedule = plan(student, reason="test")
        sync_windows(student)
        last = max(
            s.start for s in schedule.sessions.filter(task__source_type="chapter", kind="study")
        )
        quiz = ChapterQuiz.objects.get(student=student)
        day = last.astimezone(NY).date()
        assert quiz.scheduled_date == day
        assert (quiz.opens_at, quiz.closes_at) == window_for(day, NY)
        assert quiz.closes_at.astimezone(NY).time() == time(23, 59, 59)

    def test_chapters_on_same_day_share_one_quiz(self, setup):
        student, course, first = setup
        second = ChapterFactory(course=course, body_md=BODY, title="Memory")
        plan(student, reason="test")
        sync_windows(student)
        quizzes = list(ChapterQuiz.objects.filter(student=student))
        days = {q.scheduled_date for q in quizzes}
        assert len(quizzes) == len(days)
        combined = [q for q in quizzes if q.chapters.count() == 2]
        if combined:
            assert len(combined[0].questions) <= 10
        assert {c.id for q in quizzes for c in q.chapters.all()} == {first.id, second.id}

    def test_early_completion_opens_immediately(self, setup):
        student, _, chapter = setup
        plan(student, reason="test")
        client_for(student).post(f"/api/v1/chapters/{chapter.id}/complete")
        sync_windows(student)
        quiz = ChapterQuiz.objects.get(student=student, chapters=chapter)
        assert quiz.kind == "early"
        assert quiz.opens_at <= timezone.now()
        assert quiz.closes_at.astimezone(NY).date() == timezone.localtime(
            timezone.now(), NY
        ).date() + timedelta(days=1)

    @time_machine.travel(datetime(2026, 10, 14, 22, 0, tzinfo=NY))
    def test_replan_moves_unopened_window_but_not_open_one(self, setup):
        student, _, chapter = setup
        schedule = plan(student, reason="test")
        sync_windows(student)
        assert ChapterQuiz.objects.get(student=student).opens_at > timezone.now()
        Session.objects.filter(schedule=schedule, task__source_type="chapter").update(
            start=timezone.now() + timedelta(days=4),
            end=timezone.now() + timedelta(days=4, minutes=20),
        )
        moved = sync_windows(student)
        assert moved[0].scheduled_date == (timezone.now() + timedelta(days=4)).astimezone(NY).date()
        with time_machine.travel(moved[0].opens_at + timedelta(hours=1)):
            Session.objects.filter(schedule=schedule, task__source_type="chapter").update(
                start=timezone.now() + timedelta(days=6),
                end=timezone.now() + timedelta(days=6, minutes=20),
            )
            sync_windows(student)
            assert ChapterQuiz.objects.get(student=student).id == moved[0].id

    def test_timezone_change_does_not_move_open_window(self, setup):
        student, _, chapter = setup
        now = timezone.now()
        quiz = make_quiz(student, [chapter], now - timedelta(hours=1), now + timedelta(hours=5))
        student.timezone = "Asia/Tokyo"
        student.save()
        sync_windows(student)
        quiz.refresh_from_db()
        assert quiz.closes_at == now + timedelta(hours=5)
        assert quiz.timezone == "America/New_York"


class TestTakingQuizzes:
    def test_on_time_extends_streak_and_double_submit_is_idempotent(self, setup):
        student, _, chapter = setup
        now = timezone.now()
        quiz = make_quiz(student, [chapter], now - timedelta(hours=1), now + timedelta(hours=10))
        client = client_for(student)
        first = take(client, quiz)
        assert first.status_code == 200
        assert first.data["counted_for_streak"] is True
        assert first.data["sharp"] is True
        assert first.data["results"][0]["explanation"]
        again = client.post(f"/api/v1/quizzes/{quiz.id}/submit", {"answers": {}}, format="json")
        assert again.data["submitted_at"] == first.data["submitted_at"]
        assert Streak.objects.get(student=student).current == 1
        assert StreakEvent.objects.filter(student=student).count() == 1

    def test_too_fast_submission_is_rejected(self, setup):
        student, _, chapter = setup
        now = timezone.now()
        quiz = make_quiz(student, [chapter], now - timedelta(hours=1), now + timedelta(hours=10))
        response = take(client_for(student), quiz, wait=5)
        assert response.status_code == 400

    def test_started_before_close_and_submitted_within_grace_counts(self, setup):
        student, _, chapter = setup
        now = timezone.now()
        quiz = make_quiz(student, [chapter], now - timedelta(hours=5), now + timedelta(seconds=10))
        client = client_for(student)
        client.post(f"/api/v1/quizzes/{quiz.id}/start")
        with time_machine.travel(now + timedelta(minutes=10)):
            response = take(client, quiz, wait=1)
        assert response.data["counted_for_streak"] is True

    def test_after_window_it_is_practice(self, setup):
        student, _, chapter = setup
        now = timezone.now()
        quiz = make_quiz(student, [chapter], now - timedelta(days=2), now - timedelta(hours=1))
        response = take(client_for(student), quiz)
        assert response.data["counted_for_streak"] is False
        assert Streak.objects.get_or_create(student=student)[0].current == 0

    def test_missed_window_breaks_streak_unless_frozen(self, setup):
        student, _, chapter = setup
        Streak.objects.create(student=student, current=4, longest=4, freezes=1)
        now = timezone.now()
        make_quiz(student, [chapter], now - timedelta(days=2), now - timedelta(hours=1))
        sweep_student(student)
        streak = Streak.objects.get(student=student)
        assert (streak.current, streak.freezes) == (4, 0)
        make_quiz(student, [chapter], now - timedelta(days=2), now - timedelta(hours=1))
        sweep_student(student)
        assert Streak.objects.get(student=student).current == 0

    def test_freezes_earned_every_five_and_capped(self, setup):
        student, _, chapter = setup
        client = client_for(student)
        now = timezone.now()
        for _ in range(12):
            take(
                client,
                make_quiz(student, [chapter], now - timedelta(hours=1), now + timedelta(hours=10)),
            )
        streak = Streak.objects.get(student=student)
        assert streak.current == 12
        assert streak.freezes == 2

    def test_milestone_sends_win(self, setup):
        student, _, chapter = setup
        Streak.objects.create(student=student, current=2, longest=2)
        now = timezone.now()
        response = take(
            client_for(student),
            make_quiz(student, [chapter], now - timedelta(hours=1), now + timedelta(hours=9)),
        )
        assert response.data["milestone"] == 3
        assert Notification.objects.filter(
            student=student, trigger="win", source_type="chapter_quiz"
        ).exists()

    def test_streak_at_risk_and_lost_notifications(self, setup):
        student, _, chapter = setup
        Streak.objects.create(student=student, current=5, longest=5)
        now = timezone.now()
        quiz = make_quiz(student, [chapter], now - timedelta(hours=20), now + timedelta(hours=3))
        assert "streak_at_risk" in [n.trigger for n in scan_student(student)]
        with time_machine.travel(quiz.closes_at + timedelta(hours=1)):
            from quizzes.tasks import sweep_windows

            sweep_windows()
        assert Notification.objects.filter(student=student, trigger="streak_lost").exists()

    def test_days_without_quiz_are_neutral(self, setup):
        student, _, _ = setup
        Streak.objects.create(student=student, current=3, longest=3)
        sweep_student(student, timezone.now() + timedelta(days=10))
        assert Streak.objects.get(student=student).current == 3

    def test_other_students_cannot_open_quiz(self, setup):
        student, _, chapter = setup
        now = timezone.now()
        quiz = make_quiz(student, [chapter], now - timedelta(hours=1), now + timedelta(hours=10))
        other = make_student()
        assert client_for(other).get(f"/api/v1/quizzes/{quiz.id}").status_code == 404

    def test_quiz_list_and_open_is_fast(self, setup, django_assert_max_num_queries):
        student, _, chapter = setup
        now = timezone.now()
        quiz = make_quiz(student, [chapter], now - timedelta(hours=1), now + timedelta(hours=10))
        client = client_for(student)
        assert [q["id"] for q in client.get("/api/v1/quizzes?state=open").data] == [quiz.id]
        with django_assert_max_num_queries(12):
            client.post(f"/api/v1/quizzes/{quiz.id}/start")


def test_progress_marks_and_quiz_streak_status_component(setup):
    student, _, chapter = setup
    ChapterProgress.objects.create(student=student, chapter=chapter, completed_at=timezone.now())
    from quizzes.services.streaks import streak_component

    assert streak_component(student, datetime.now(tz=NY))[0] == 1.0
