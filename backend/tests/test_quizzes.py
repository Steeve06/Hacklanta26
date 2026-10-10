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
from quizzes.models import CheckAttempt, CheckQuestion, Streak, StreakEvent, StudyCheck
from quizzes.services import bank as bank_service
from quizzes.services.checks import pass_mark
from quizzes.services.streaks import sweep_student, week_of
from quizzes.services.windows import sync_checks, window_for

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


def make_check(student, chapters, opens, closes):
    check = StudyCheck.objects.create(
        student=student,
        scheduled_date=opens.date(),
        opens_at=opens,
        closes_at=closes,
        timezone="America/New_York",
    )
    check.chapters.set(chapters)
    for chapter in chapters:
        bank_service.rebuild_bank(chapter)
    return check


def right_choice(check, position):
    attempt = CheckAttempt.objects.filter(study_check=check).order_by("-number").first()
    item = attempt.cards[position]
    return item["order"].index(CheckQuestion.objects.get(pk=item["question_id"]).correct_index)


def take(client, check, *, right=4, gap=5, start=None):
    """Start (or resume) the check and answer all four cards, `right` of them correctly."""
    start = start or timezone.now()
    with time_machine.travel(start, tick=False):
        detail = client.post(f"/api/v1/checks/{check.id}/start")
    assert detail.status_code == 200, detail.data
    response = detail
    for position in range(4):
        with time_machine.travel(start + timedelta(seconds=gap * (position + 1)), tick=False):
            choice = right_choice(check, position)
            if position >= right:
                choice = (choice + 1) % len(detail.data["attempt"]["cards"][position]["options"])
            response = client.post(
                f"/api/v1/checks/{check.id}/answer",
                {"position": position, "choice": choice},
                format="json",
            )
            assert response.status_code == 200, response.data
    return response


class TestBank:
    def test_key_term_fallback_builds_valid_cards(self, setup):
        _, _, chapter = setup
        assert bank_service.rebuild_bank(chapter) >= bank_service.MIN_BANK
        for q in CheckQuestion.objects.filter(chapter=chapter):
            assert len(set(q.options)) == len(q.options)
            assert q.correct_index < len(q.options)
            assert q.origin == "cloze"

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

    def ai_on(self, settings, monkeypatch, count=10):
        settings.AI_PROVIDER, settings.AI_API_KEY = "anthropic", "k"
        from ai import client as ai_client

        def fake(model, system, user, schema, max_tokens):
            assert "check whether a student actually studied" in system
            base = {"type": "multiple_choice", "options": ["Spaced practice", "Cramming", "Rereading", "Napping"],
                    "correct_index": 0, "explanation": "Stated in the chapter."}  # fmt: skip
            return {"questions": [
                {**base, "question": f"Which spreads study out? ({i})", "source_excerpt": "spreads study over several sessions"}
                for i in range(count)
            ] + [{**base, "question": "Invented?", "source_excerpt": "This sentence is not in the chapter at all."}]}, 10, 10  # fmt: skip

        monkeypatch.setitem(ai_client.PROVIDERS, "anthropic", fake)

    def test_model_cards_are_filtered_and_kept(self, setup, settings, monkeypatch):
        _, _, chapter = setup
        self.ai_on(settings, monkeypatch)
        bank_service.rebuild_bank(chapter)
        kept = bank_service.usable(chapter)
        assert kept.count() == 10
        assert all(q.origin == "ai" for q in kept)

    def test_model_cards_replace_key_term_cards_when_ai_is_turned_on(
        self, setup, settings, monkeypatch
    ):
        _, _, chapter = setup
        bank_service.rebuild_bank(chapter, allow_ai=False)
        assert set(bank_service.usable(chapter).values_list("origin", flat=True)) == {"cloze"}
        self.ai_on(settings, monkeypatch)
        bank_service.rebuild_bank(chapter)
        assert set(bank_service.usable(chapter).values_list("origin", flat=True)) == {"ai"}

    def test_too_few_model_cards_are_topped_up_with_key_terms(self, setup, settings, monkeypatch):
        _, _, chapter = setup
        self.ai_on(settings, monkeypatch, count=3)
        bank_service.rebuild_bank(chapter)
        origins = list(bank_service.usable(chapter).values_list("origin", flat=True))
        assert origins.count("ai") == 3 and "cloze" in origins

    def test_edit_retires_old_cards(self, setup):
        _, _, chapter = setup
        bank_service.rebuild_bank(chapter)
        old_ids = set(CheckQuestion.objects.values_list("id", flat=True))
        chapter.body_md = (
            BODY
            + "\n**Self-explanation** asks learners to explain each step in their own words to themselves."
        )
        chapter.save()
        bank_service.rebuild_bank(chapter)
        assert CheckQuestion.objects.filter(id__in=old_ids, retired=False).count() == 0
        assert bank_service.usable(chapter).count() >= bank_service.MIN_BANK


class TestWindows:
    def test_check_follows_last_study_day(self, setup):
        student, _, chapter = setup
        schedule = plan(student, reason="test")
        sync_checks(student)
        last = max(
            s.start for s in schedule.sessions.filter(task__source_type="chapter", kind="study")
        )
        check = StudyCheck.objects.get(student=student)
        day = last.astimezone(NY).date()
        assert check.scheduled_date == day
        assert (check.opens_at, check.closes_at) == window_for(day, NY)
        assert check.closes_at.astimezone(NY).time() == time(23, 59, 59)

    def test_schedule_has_a_short_check_session_after_the_chapter(self, setup):
        student, _, _ = setup
        schedule = plan(student, reason="test")
        checks = schedule.sessions.filter(kind=Session.Kind.CHAPTER_QUIZ)
        study = schedule.sessions.filter(task__source_type="chapter", kind="study")
        assert checks.count() == 1
        session = checks.get()
        assert session.title.startswith("Study check")
        assert (session.end - session.start) == timedelta(minutes=5)
        assert session.start >= max(s.end for s in study)

    def test_chapters_on_same_day_share_one_check(self, setup):
        student, course, first = setup
        second = ChapterFactory(course=course, body_md=BODY, title="Memory")
        plan(student, reason="test")
        sync_checks(student)
        checks = list(StudyCheck.objects.filter(student=student))
        assert len(checks) == len({c.scheduled_date for c in checks})
        assert {ch.id for c in checks for ch in c.chapters.all()} == {first.id, second.id}

    def test_combined_check_mixes_cards_from_both_chapters(self, setup):
        student, course, first = setup
        second = ChapterFactory(course=course, body_md=BODY, title="Memory")
        now = timezone.now()
        check = make_check(
            student, [first, second], now - timedelta(hours=1), now + timedelta(hours=9)
        )
        detail = client_for(student).post(f"/api/v1/checks/{check.id}/start").data
        cards = detail["attempt"]["cards"]
        assert len(cards) == 4
        assert {c["chapter_id"] for c in cards} == {first.id, second.id}

    def test_early_completion_opens_immediately(self, setup):
        student, _, chapter = setup
        plan(student, reason="test")
        client_for(student).post(f"/api/v1/chapters/{chapter.id}/complete")
        sync_checks(student)
        check = StudyCheck.objects.get(student=student, chapters=chapter)
        assert check.kind == "early"
        assert check.opens_at <= timezone.now()
        assert check.closes_at.astimezone(NY).date() == timezone.localtime(
            timezone.now(), NY
        ).date() + timedelta(days=1)

    @time_machine.travel(datetime(2026, 10, 14, 22, 0, tzinfo=NY))
    def test_replan_moves_unopened_check_but_not_open_one(self, setup):
        student, _, chapter = setup
        schedule = plan(student, reason="test")
        sync_checks(student)
        assert StudyCheck.objects.get(student=student).opens_at > timezone.now()
        Session.objects.filter(schedule=schedule, task__source_type="chapter").update(
            start=timezone.now() + timedelta(days=4),
            end=timezone.now() + timedelta(days=4, minutes=20),
        )
        moved = sync_checks(student)
        assert moved[0].scheduled_date == (timezone.now() + timedelta(days=4)).astimezone(NY).date()
        with time_machine.travel(moved[0].opens_at + timedelta(hours=1)):
            Session.objects.filter(schedule=schedule, task__source_type="chapter").update(
                start=timezone.now() + timedelta(days=6),
                end=timezone.now() + timedelta(days=6, minutes=20),
            )
            sync_checks(student)
            assert StudyCheck.objects.get(student=student).id == moved[0].id

    def test_timezone_change_does_not_move_open_check(self, setup):
        student, _, chapter = setup
        now = timezone.now()
        check = make_check(student, [chapter], now - timedelta(hours=1), now + timedelta(hours=5))
        student.timezone = "Asia/Tokyo"
        student.save()
        sync_checks(student)
        check.refresh_from_db()
        assert check.closes_at == now + timedelta(hours=5)
        assert check.timezone == "America/New_York"


class TestTakingChecks:
    def open_check(self, setup, hours=10):
        student, _, chapter = setup
        now = timezone.now()
        return student, make_check(
            student, [chapter], now - timedelta(hours=1), now + timedelta(hours=hours)
        )

    def test_answers_stay_hidden_until_each_card_is_answered(self, setup):
        student, check = self.open_check(setup)
        client = client_for(student)
        started = client.post(f"/api/v1/checks/{check.id}/start").data
        assert all(c["result"] is None for c in started["attempt"]["cards"])
        assert "correct_index" not in str(started)
        with time_machine.travel(timezone.now() + timedelta(seconds=5), tick=False):
            choice = right_choice(check, 0)
            after = client.post(
                f"/api/v1/checks/{check.id}/answer",
                {"position": 0, "choice": choice},
                format="json",
            ).data
        first, second = after["attempt"]["cards"][:2]
        assert first["result"]["correct"] is True and first["result"]["answer"] == choice
        assert first["result"]["explanation"] and first["result"]["source_excerpt"]
        assert second["result"] is None

    def test_three_of_four_passes_and_extends_the_streak_once(self, setup):
        student, check = self.open_check(setup)
        client = client_for(student)
        done = take(client, check, right=3)
        assert done.data["state"] == "passed"
        assert done.data["counted_for_streak"] is True
        assert done.data["streak"] == 1
        again = client.post(
            f"/api/v1/checks/{check.id}/answer", {"position": 3, "choice": 0}, format="json"
        )
        assert again.status_code == 200
        assert Streak.objects.get(student=student).current == 1
        assert StreakEvent.objects.filter(student=student).count() == 1
        assert client.post(f"/api/v1/checks/{check.id}/start").status_code == 400

    def test_failing_once_leaves_a_retry_with_new_cards(self, setup):
        student, check = self.open_check(setup)
        client = client_for(student)
        failed = take(client, check, right=2)
        assert failed.data["state"] == "open" and failed.data["tries_left"] == 1
        first_ids = {c["question_id"] for c in check.attempts.get(number=1).cards}
        passed = take(client, check, right=4, start=timezone.now() + timedelta(minutes=5))
        second_ids = {c["question_id"] for c in check.attempts.get(number=2).cards}
        assert not first_ids & second_ids
        assert passed.data["state"] == "passed"
        assert Streak.objects.get(student=student).current == 1

    def test_failing_twice_breaks_the_streak_unless_frozen(self, setup):
        student, check = self.open_check(setup)
        Streak.objects.create(student=student, current=4, longest=4, freezes=1)
        client = client_for(student)
        take(client, check, right=1)
        done = take(client, check, right=2, start=timezone.now() + timedelta(minutes=5))
        assert done.data["state"] == "not_passed" and done.data["tries_left"] == 0
        streak = Streak.objects.get(student=student)
        assert (streak.current, streak.freezes) == (4, 0)
        assert StreakEvent.objects.get(study_check=check).result == "frozen"
        third = client.post(f"/api/v1/checks/{check.id}/start")
        assert third.status_code == 400

    def test_tapping_through_without_reading_is_rejected(self, setup):
        student, check = self.open_check(setup)
        client = client_for(student)
        client.post(f"/api/v1/checks/{check.id}/start")
        response = client.post(
            f"/api/v1/checks/{check.id}/answer", {"position": 0, "choice": 0}, format="json"
        )
        assert response.status_code == 400

    def test_cards_must_be_answered_in_order(self, setup):
        student, check = self.open_check(setup)
        client = client_for(student)
        client.post(f"/api/v1/checks/{check.id}/start")
        with time_machine.travel(timezone.now() + timedelta(seconds=10)):
            response = client.post(
                f"/api/v1/checks/{check.id}/answer", {"position": 2, "choice": 0}, format="json"
            )
        assert response.status_code == 400

    def test_started_before_close_and_finished_within_grace_counts(self, setup):
        student, _, chapter = setup
        now = timezone.now()
        check = make_check(student, [chapter], now - timedelta(hours=5), now + timedelta(seconds=3))
        client = client_for(student)
        client.post(f"/api/v1/checks/{check.id}/start")
        done = take(client, check, gap=120)
        assert done.data["counted_for_streak"] is True

    def test_closed_check_cannot_be_started(self, setup):
        student, _, chapter = setup
        now = timezone.now()
        check = make_check(student, [chapter], now - timedelta(days=2), now - timedelta(hours=1))
        response = client_for(student).post(f"/api/v1/checks/{check.id}/start")
        assert response.status_code == 400
        assert client_for(student).get(f"/api/v1/checks/{check.id}").data["state"] == "missed"

    def test_missed_check_breaks_streak_unless_frozen(self, setup):
        student, _, chapter = setup
        Streak.objects.create(student=student, current=4, longest=4, freezes=1)
        now = timezone.now()
        make_check(student, [chapter], now - timedelta(days=2), now - timedelta(hours=1))
        sweep_student(student)
        streak = Streak.objects.get(student=student)
        assert (streak.current, streak.freezes) == (4, 0)
        make_check(student, [chapter], now - timedelta(days=2), now - timedelta(hours=1))
        sweep_student(student)
        assert Streak.objects.get(student=student).current == 0

    def test_freezes_earned_every_five_and_capped(self, setup):
        student, _, chapter = setup
        client = client_for(student)
        now = timezone.now()
        for i in range(12):
            check = make_check(
                student, [chapter], now - timedelta(hours=1), now + timedelta(hours=10)
            )
            take(client, check, start=now + timedelta(minutes=i))
        streak = Streak.objects.get(student=student)
        assert streak.current == 12
        assert streak.freezes == 2

    def test_milestone_sends_win(self, setup):
        student, check = self.open_check(setup)
        Streak.objects.create(student=student, current=2, longest=2)
        response = take(client_for(student), check)
        assert response.data["milestone"] == 3
        assert Notification.objects.filter(
            student=student, trigger="win", source_type="study_check"
        ).exists()

    def test_streak_at_risk_and_lost_notifications(self, setup):
        student, _, chapter = setup
        Streak.objects.create(student=student, current=5, longest=5)
        now = timezone.now()
        check = make_check(student, [chapter], now - timedelta(hours=20), now + timedelta(hours=3))
        assert "streak_at_risk" in [n.trigger for n in scan_student(student)]
        with time_machine.travel(check.closes_at + timedelta(hours=1)):
            from quizzes.tasks import sweep_checks

            sweep_checks()
        assert Notification.objects.filter(student=student, trigger="streak_lost").exists()

    def test_days_without_a_check_are_neutral(self, setup):
        student, _, _ = setup
        Streak.objects.create(student=student, current=3, longest=3)
        sweep_student(student, timezone.now() + timedelta(days=10))
        assert Streak.objects.get(student=student).current == 3

    def test_other_students_cannot_open_a_check(self, setup):
        student, check = self.open_check(setup)
        assert client_for(make_student()).get(f"/api/v1/checks/{check.id}").status_code == 404

    def test_list_and_start_are_fast(self, setup, django_assert_max_num_queries):
        student, check = self.open_check(setup)
        client = client_for(student)
        assert [c["id"] for c in client.get("/api/v1/checks?state=open").data] == [check.id]
        with django_assert_max_num_queries(30):
            client.post(f"/api/v1/checks/{check.id}/start")


def test_pass_mark_scales_for_small_banks():
    assert [pass_mark(n) for n in (1, 2, 3, 4)] == [1, 2, 3, 3]


def test_streak_endpoint_shows_the_week(setup):
    student, _, chapter = setup
    now = timezone.now()
    check = make_check(student, [chapter], now - timedelta(hours=1), now + timedelta(hours=10))
    client = client_for(student)
    assert week_of(student, now)[-1]["result"] in {"open", "none"}
    take(client, check)
    data = client.get("/api/v1/streak").data
    assert data["current"] == 1
    assert len(data["week"]) == 7
    assert {"day": check.scheduled_date, "result": "done"} in [
        {"day": datetime.fromisoformat(d["day"]).date() if isinstance(d["day"], str) else d["day"],
         "result": d["result"]}
        for d in data["week"]
    ]  # fmt: skip


def test_progress_marks_and_streak_status_component(setup):
    student, _, chapter = setup
    ChapterProgress.objects.create(student=student, chapter=chapter, completed_at=timezone.now())
    from quizzes.services.streaks import streak_component

    assert streak_component(student, datetime.now(tz=NY))[0] == 1.0


class TestMissedDeadlines:
    def test_a_missed_deadline_spends_a_freeze_then_resets_once_each(self, setup):
        from .factories import AssessmentFactory

        student, course, _ = setup
        now = timezone.now()
        late = AssessmentFactory(course=course, title="Late essay",
                                 due_at=now - timedelta(hours=5), cutoff_at=now + timedelta(days=1))  # fmt: skip
        AssessmentFactory(course=course, title="Ancient", due_at=now - timedelta(days=20))
        Streak.objects.update_or_create(student=student, defaults={"current": 4, "freezes": 1})
        client = client_for(student)

        data = client.get("/api/v1/streak").data
        assert [m["title"] for m in data["missed_deadlines"]] == ["Late essay"]
        assert data["missed_deadlines"][0]["late_until"] is not None
        assert data["missed_deadlines"][0]["streak_result"] == "frozen"
        assert (data["current"], data["freezes"]) == (4, 0)

        again = client.get("/api/v1/streak").data
        assert (again["current"], again["freezes"]) == (4, 0)

        AssessmentFactory(course=course, title="Quiz 3", due_at=now - timedelta(hours=1))
        reset = client.get("/api/v1/streak").data
        assert reset["current"] == 0
        assert {m["title"]: m["streak_result"] for m in reset["missed_deadlines"]} == {
            "Late essay": "frozen",
            "Quiz 3": "missed",
        }
        assert late.pk in StreakEvent.objects.filter(student=student).values_list(
            "assessment_id", flat=True
        )

    def test_excused_and_extended_work_does_not_count(self, setup):
        from lms.models import DueDateOverride, Submission

        from .factories import AssessmentFactory

        student, course, _ = setup
        now = timezone.now()
        excused = AssessmentFactory(course=course, due_at=now - timedelta(hours=2))
        Submission.objects.create(assessment=excused, student=student, status="excused")
        extended = AssessmentFactory(course=course, due_at=now - timedelta(hours=2))
        DueDateOverride.objects.create(
            assessment=extended, student=student, due_at=now + timedelta(days=2)
        )
        Streak.objects.update_or_create(student=student, defaults={"current": 3})
        data = client_for(student).get("/api/v1/streak").data
        assert data["missed_deadlines"] == [] and data["current"] == 3
