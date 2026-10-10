from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import time_machine
from django.utils import timezone
from rest_framework.test import APIClient

from notifications.engine import scan_student
from notifications.models import Notification
from quizzes.cards import CARDS
from quizzes.models import CardReview, DailyDeck, Flashcard, Streak, StreakEvent
from quizzes.services.cards import DECK_SIZE, pick, sync_cards
from quizzes.services.streaks import settle, streak_component

from .test_pulse import make_student

pytestmark = pytest.mark.django_db
NY = ZoneInfo("America/New_York")
NOON = datetime(2026, 10, 14, 12, 0, tzinfo=NY)


@pytest.fixture
def student():
    return make_student()


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def response_for(deck_id: int, position: int, correct: bool = True) -> dict:
    from seed.quiz_seed import _response

    item = DailyDeck.objects.get(pk=deck_id).items[position]
    ids = item["cards"] if item["type"] == "match" else [item["card"]]
    return _response(item, correct, {c.id: c for c in Flashcard.objects.filter(id__in=ids)}, None)


def send(client, deck_id: int, position: int, response: dict):
    return client.post(
        f"/api/v1/decks/{deck_id}/answer", {"position": position, "response": response},
        format="json",
    )  # fmt: skip


def finish_today(client, *, correct=True, upto=None):
    """Start today's session and answer every question (or the first `upto`)."""
    deck = client.get("/api/v1/decks/today").data
    client.post(f"/api/v1/decks/{deck['id']}/start")
    result = None
    for position in range(len(deck["items"]) if upto is None else upto):
        result = send(client, deck["id"], position, response_for(deck["id"], position, correct))
    return result


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=NY)


class TestLibrary:
    def test_cards_are_seeded_and_cover_every_topic(self):
        assert Flashcard.objects.filter(active=True).count() == len(CARDS)
        assert {c.topic for c in Flashcard.objects.all()} == set(Flashcard.Topic.values) - {
            "course"
        }
        assert len({slug for slug, *_ in CARDS}) == len(CARDS)

    def test_sync_updates_in_place_and_retires_removed_cards(self, monkeypatch):
        extra = Flashcard.objects.create(slug="gone", topic="world", front="?", back="!")
        from quizzes.services import cards as cards_service

        slug, topic, front, _ = CARDS[0]
        monkeypatch.setattr(
            cards_service, "CARDS", [(slug, topic, front, "New answer."), *CARDS[1:]]
        )
        sync_cards()
        assert Flashcard.objects.get(slug=slug).back == "New answer."
        extra.refresh_from_db()
        assert extra.active is False


class TestPicking:
    def test_deck_is_stable_for_a_day_and_spreads_topics(self, student):
        day = date(2026, 10, 14)
        first = pick(student, day)
        assert first == pick(student, day)
        assert len(first) == DECK_SIZE
        topics = [Flashcard.objects.get(pk=c).topic for c in first]
        assert len(set(topics)) == DECK_SIZE
        assert pick(student, day + timedelta(days=1)) != first

    def test_still_learning_cards_come_back_and_known_ones_wait(self, student):
        day = date(2026, 10, 14)
        cards = pick(student, day)
        deck = DailyDeck.objects.create(student=student, day=day, cards=cards)
        for i, card_id in enumerate(cards):
            CardReview.objects.create(deck=deck, card_id=card_id, knew=i >= 2)
        tomorrow = pick(student, day + timedelta(days=1))
        assert tomorrow[:2] == cards[:2]
        assert not set(tomorrow[2:]) & set(cards)

    def test_runs_out_of_new_cards_gracefully(self, student):
        day = date(2026, 1, 1)
        for i in range(len(CARDS) // DECK_SIZE + 2):
            d = day + timedelta(days=i)
            deck = DailyDeck.objects.create(student=student, day=d, cards=pick(student, d))
            CardReview.objects.bulk_create(
                CardReview(deck=deck, card_id=c, knew=True) for c in deck.cards
            )
        later = pick(student, day + timedelta(days=60))
        assert len(set(later)) == DECK_SIZE


class TestSessions:
    @time_machine.travel(NOON, tick=False)
    def test_one_session_a_day_and_finishing_counts_once(self, student):
        client = client_for(student)
        deck = client.get("/api/v1/decks/today").data
        assert client.get("/api/v1/decks/today").data["id"] == deck["id"]
        assert deck["state"] == "open"
        assert (deck["question_count"], deck["time_limit_seconds"]) == (5, 180)
        assert all(i["solution"] is None for i in deck["items"])
        done = finish_today(client)
        assert done.status_code == 200
        assert done.data["state"] == "done"
        assert done.data["counted_for_streak"] is True
        assert done.data["knew"] == 5
        assert done.data["xp"] == 5 * 10 + 20
        assert all(i["correct"] and i["solution"] for i in done.data["items"])
        again = send(client, deck["id"], 0, {"knew": False, "choice": 0})
        assert again.data["completed_at"] == done.data["completed_at"]
        streak = Streak.objects.get(student=student)
        assert (streak.current, streak.last_day) == (1, NOON.date())

    @time_machine.travel(NOON, tick=False)
    def test_general_session_mixes_multiple_choice_and_flashcards(self, student):
        deck = client_for(student).get("/api/v1/decks/today").data
        types = [i["type"] for i in deck["items"]]
        assert {"mcq", "flashcard"} <= set(types)
        mcq = next(i for i in deck["items"] if i["type"] == "mcq")
        assert len(mcq["options"]) == 4 and mcq["back"] is None

    @time_machine.travel(NOON, tick=False)
    def test_wrong_answers_still_finish_and_count_the_day(self, student):
        response = finish_today(client_for(student), correct=False)
        assert response.data["counted_for_streak"] is True
        assert (response.data["knew"], response.data["xp"]) == (0, 20)
        assert response.data["streak"] == 1

    @time_machine.travel(NOON, tick=False)
    def test_answers_need_a_started_session_and_a_real_question(self, student):
        client = client_for(student)
        deck = client.get("/api/v1/decks/today").data
        assert send(client, deck["id"], 0, response_for(deck["id"], 0)).status_code == 400
        client.post(f"/api/v1/decks/{deck['id']}/start")
        assert send(client, deck["id"], 99, {"knew": True}).status_code == 400
        assert send(client, deck["id"], 0, {}).status_code == 400

    def test_time_up_finishes_with_what_was_answered(self, student):
        client = client_for(student)
        with time_machine.travel(NOON, tick=False):
            finish_today(client, upto=2)
            early = client.post(f"/api/v1/decks/{DailyDeck.objects.get().id}/finish")
            assert early.status_code == 400
        with time_machine.travel(NOON + timedelta(minutes=4), tick=False):
            deck = client.get("/api/v1/decks/today").data
            late = send(client, deck["id"], 3, response_for(deck["id"], 3))
        assert deck["state"] == "done"
        assert deck["completed_at"] == deck["deadline"]
        assert deck["knew"] == 2 and deck["counted_for_streak"] is True
        assert late.data["knew"] == 2
        assert sum(1 for i in deck["items"] if i["answered"]) == 2
        assert all(i["solution"] for i in deck["items"])

    def test_time_up_with_nothing_answered_does_not_count(self, student):
        client = client_for(student)
        with time_machine.travel(NOON, tick=False):
            deck = client.get("/api/v1/decks/today").data
            client.post(f"/api/v1/decks/{deck['id']}/start")
        with time_machine.travel(NOON + timedelta(minutes=5), tick=False):
            done = client.post(f"/api/v1/decks/{deck['id']}/finish").data
        assert done["state"] == "done" and done["counted_for_streak"] is False

    def test_started_before_midnight_and_finished_in_grace_counts(self, student):
        day = NOON.date()
        client = client_for(student)
        with time_machine.travel(at(day, 23, 58), tick=False):
            finish_today(client, upto=1)
        with time_machine.travel(at(day, 23, 58) + timedelta(minutes=2), tick=False):
            deck = DailyDeck.objects.get()
            for position in range(1, len(deck.items)):
                last = send(client, deck.id, position, response_for(deck.id, position))
        assert last.data["counted_for_streak"] is True
        assert Streak.objects.get(student=student).last_day == day

    def test_old_session_finished_late_is_practice(self, student):
        day = NOON.date()
        client = client_for(student)
        with time_machine.travel(at(day, 10), tick=False):
            deck = client.get("/api/v1/decks/today").data
        with time_machine.travel(at(day, 10) + timedelta(days=1), tick=False):
            client.post(f"/api/v1/decks/{deck['id']}/start")
            for position in range(len(deck["items"])):
                last = send(client, deck["id"], position, response_for(deck["id"], position))
        assert last.data["state"] == "done"
        assert last.data["counted_for_streak"] is False
        assert Streak.objects.get_or_create(student=student)[0].current == 0

    def test_other_students_cannot_open_a_session(self, student):
        deck = client_for(student).get("/api/v1/decks/today").data
        other = make_student()
        assert client_for(other).get(f"/api/v1/decks/{deck['id']}").status_code == 404


class TestGrading:
    @pytest.mark.parametrize(
        ("given", "ok"),
        [("hash function", True), ("Hash Functions", True), ("the hash function", True),
         ("hash funtcion", True), ("hash", False), ("", False)],
    )  # fmt: skip
    def test_short_answers_forgive_small_slips(self, given, ok):
        from quizzes.services.items import close_enough

        assert close_enough(given, "Hash function") is ok

    def test_matching_grades_each_pair(self):
        from quizzes.services.items import grade

        cards = {1: None, 2: None, 3: None}
        item = {"type": "match", "cards": [1, 2, 3], "clues": [3, 1, 2]}
        assert grade(item, {"pairs": [1, 2, 0]}, cards) == (True, {1: True, 2: True, 3: True})
        assert grade(item, {"pairs": [2, 1, 0]}, cards)[1] == {1: False, 2: False, 3: True}

    def test_solutions_explain_with_the_full_sentence(self):
        from quizzes.services.items import solution

        course = Flashcard(id=1, answer="Collision", back="Collision\n\nTwo keys share a bucket.")
        general = Flashcard(id=2, back="Grouping items.")
        item = {"type": "mcq", "card": 1, "options": ["Heap", "Collision"]}
        assert solution(item, {1: course}) == {
            "answer": "Collision", "explanation": "Two keys share a bucket.", "choice": 1,
        }  # fmt: skip
        assert solution({"type": "flashcard", "card": 2}, {2: general})["explanation"] == (
            "Grouping items."
        )


class TestStreaks:
    def test_consecutive_days_grow_streak_and_earn_capped_freezes(self, student):
        client = client_for(student)
        for i in range(12):
            with time_machine.travel(NOON + timedelta(days=i), tick=False):
                finish_today(client)
        streak = Streak.objects.get(student=student)
        assert (streak.current, streak.longest, streak.freezes) == (12, 12, 2)

    def test_two_decks_same_day_is_impossible_and_day_counts_once(self, student):
        client = client_for(student)
        with time_machine.travel(NOON, tick=False):
            finish_today(client)
        with time_machine.travel(NOON + timedelta(hours=6), tick=False):
            finish_today(client)
        assert DailyDeck.objects.filter(student=student).count() == 1
        assert Streak.objects.get(student=student).current == 1

    def test_missed_day_spends_a_freeze_then_resets(self, student):
        Streak.objects.create(
            student=student, current=4, longest=4, freezes=1, last_day=date(2026, 10, 10)
        )
        events = settle(student, at(date(2026, 10, 12), 9))
        assert [e.result for e in events] == ["frozen"]
        streak = Streak.objects.get(student=student)
        assert (streak.current, streak.freezes, streak.last_day) == (4, 0, date(2026, 10, 11))
        events = settle(student, at(date(2026, 10, 13), 9))
        assert [e.result for e in events] == ["missed"]
        assert Streak.objects.get(student=student).current == 0
        assert settle(student, at(date(2026, 10, 20), 9)) == []

    def test_settle_waits_for_today_and_the_grace_period(self, student):
        Streak.objects.create(student=student, current=3, longest=3, last_day=date(2026, 10, 13))
        assert settle(student, at(date(2026, 10, 14), 23)) == []
        assert settle(student, at(date(2026, 10, 15), 0, 10)) == []
        assert [e.result for e in settle(student, at(date(2026, 10, 15), 0, 20))] == ["missed"]

    def test_finishing_after_a_gap_restarts_at_one(self, student):
        Streak.objects.create(student=student, current=5, longest=5, last_day=date(2026, 10, 1))
        with time_machine.travel(NOON, tick=False):
            response = finish_today(client_for(student))
        assert response.data["streak"] == 1
        streak = Streak.objects.get(student=student)
        assert (streak.current, streak.longest) == (1, 5)
        assert StreakEvent.objects.filter(student=student, result="missed").count() == 1

    def test_milestone_sends_win(self, student):
        Streak.objects.create(
            student=student, current=2, longest=2, last_day=NOON.date() - timedelta(days=1)
        )
        with time_machine.travel(NOON, tick=False):
            response = finish_today(client_for(student))
        assert response.data["milestone"] == 3
        assert Notification.objects.filter(
            student=student, trigger="win", source_type="daily_deck"
        ).exists()

    def test_at_risk_in_the_evening_and_lost_after_midnight(self, student):
        Streak.objects.create(
            student=student, current=5, longest=5, last_day=NOON.date() - timedelta(days=1)
        )
        with time_machine.travel(NOON, tick=False):
            assert "streak_at_risk" not in [n.trigger for n in scan_student(student)]
        with time_machine.travel(at(NOON.date(), 21), tick=False):
            assert "streak_at_risk" in [n.trigger for n in scan_student(student)]
            assert streak_component(student, timezone.now())[0] == 0.5
        with time_machine.travel(at(NOON.date(), 21) + timedelta(hours=4), tick=False):
            from quizzes.tasks import sweep_streaks

            assert sweep_streaks() == 1
            assert streak_component(student, timezone.now())[0] == 0.0
        assert Notification.objects.filter(student=student, trigger="streak_lost").exists()

    def test_streak_endpoint_shows_the_week(self, student):
        client = client_for(student)
        with time_machine.travel(NOON - timedelta(days=2), tick=False):
            finish_today(client)
        with time_machine.travel(NOON, tick=False):
            data = client.get("/api/v1/streak").data
        assert [d["result"] for d in data["week"]][-3:] == ["done", "missed", "open"]
        assert data["current"] == 0
        assert data["done_today"] is False
        assert data["next_milestone"] == 3

    def test_no_streak_is_neutral_for_status(self, student):
        assert streak_component(student, NOON)[0] == 1.0
        assert settle(student, NOON) == []


@time_machine.travel(NOON, tick=False)
def test_session_list_and_answers_are_fast(student, django_assert_max_num_queries):
    client = client_for(student)
    deck = client.get("/api/v1/decks/today").data
    client.post(f"/api/v1/decks/{deck['id']}/start")
    assert [d["id"] for d in client.get("/api/v1/decks").data] == [deck["id"]]
    response = response_for(deck["id"], 0)
    with django_assert_max_num_queries(25):
        send(client, deck["id"], 0, response)


HASHING = """## Hashing

A **hash table** answers lookups in constant time on average.
A **hash function** turns each key into an integer called its hash.
Different keys can land in one bucket, which is called a **collision** between them.
**Separate chaining** stores a small list in each bucket of the table.
**Open addressing** looks for another free slot when a bucket is full.
It is **fast** to compute.
"""

HEAPS = """## Heaps

A **binary heap** is a complete binary tree stored in an array.
The **heap property** says every parent is smaller than its children in a min-heap.
Restoring order after an insert is called **sifting up** through the tree.
"""


@pytest.fixture
def enrolled():
    from .factories import ChapterFactory, CourseFactory, enroll

    student = make_student()
    course = CourseFactory(code="CS 201")
    enroll(student, course)
    hashing = ChapterFactory(course=course, body_md=HASHING, title="Hashing", order=5)
    heaps = ChapterFactory(course=course, body_md=HEAPS, title="Heaps", order=7)
    return student, course, hashing, heaps


class TestCourseCards:
    def test_key_terms_become_fill_in_the_blank_cards(self, enrolled):
        from quizzes.services import chapter_cards

        _, _, hashing, _ = enrolled
        ids = chapter_cards.ensure(hashing)
        cards = Flashcard.objects.filter(id__in=ids)
        assert len(ids) == 5  # "fast" is emphasis, not a key term
        card = cards.get(back__startswith="Hash function")
        assert (
            card.front
            == "Fill in the blank: A _____ turns each key into an integer called its hash."
        )
        assert card.topic == "course" and card.chapter == hashing
        assert chapter_cards.ensure(hashing) == ids

    def test_editing_a_chapter_retires_its_old_cards(self, enrolled):
        from quizzes.services import chapter_cards

        _, _, hashing, _ = enrolled
        old = chapter_cards.ensure(hashing)
        hashing.body_md = (
            HASHING + "\nA **load factor** is the number of entries divided by buckets.\n"
        )
        hashing.save()
        new = chapter_cards.ensure(hashing)
        assert len(new) == 6
        assert not Flashcard.objects.filter(id__in=old, active=True).exclude(id__in=new).exists()


class TestCourseFocus:
    def test_upcoming_quiz_drives_the_deck(self, enrolled):
        from .factories import AssessmentFactory

        student, course, hashing, heaps = enrolled
        quiz = AssessmentFactory(course=course, type="quiz", title="Quiz 2: Hashing",
                                 due_at=timezone.now() + timedelta(days=2))  # fmt: skip
        quiz.chapters.set([hashing])
        deck = client_for(student).get("/api/v1/decks/today").data
        assert deck["focus"]["kind"] == "upcoming"
        assert deck["focus"]["assessment_title"] == "Quiz 2: Hashing"
        assert deck["focus"]["course_code"] == "CS 201"
        assert deck["focus"]["due_at"]
        assert deck["question_count"] == 8 and deck["time_limit_seconds"] == 300
        assert deck["items"][0]["chapter_id"] == hashing.id
        assert deck["items"][0]["source"] == "CS 201 · Ch 5: Hashing"
        hashing_items = [i for i in deck["items"] if i["chapter_id"] == hashing.id]
        assert len(hashing_items) >= 4  # every Hashing card is used before anything else
        assert {"mcq", "short", "match"} <= {i["type"] for i in deck["items"]}
        assert all(i["solution"] is None for i in deck["items"])

    def test_homework_due_soon_keeps_the_three_minute_session(self, enrolled):
        from .factories import AssessmentFactory

        student, course, hashing, _ = enrolled
        homework = AssessmentFactory(course=course, due_at=timezone.now() + timedelta(days=2))
        homework.chapters.set([hashing])
        deck = client_for(student).get("/api/v1/decks/today").data
        assert deck["focus"]["kind"] == "upcoming"
        assert deck["question_count"] == 5 and deck["time_limit_seconds"] == 180

    def test_quiz_beats_sooner_homework_and_far_deadlines_are_ignored(self, enrolled):
        from .factories import AssessmentFactory

        student, course, hashing, heaps = enrolled
        homework = AssessmentFactory(course=course, due_at=timezone.now() + timedelta(days=1))
        homework.chapters.set([hashing])
        quiz = AssessmentFactory(
            course=course, type="quiz", due_at=timezone.now() + timedelta(days=4)
        )
        quiz.chapters.set([heaps])
        later = AssessmentFactory(
            course=course, type="quiz", due_at=timezone.now() + timedelta(days=20)
        )
        later.chapters.set([hashing])
        deck = client_for(student).get("/api/v1/decks/today").data
        assert deck["focus"]["assessment_id"] == quiz.id
        assert deck["items"][0]["chapter_id"] == heaps.id
        assert {i["chapter_id"] for i in deck["items"]} >= {heaps.id, hashing.id}

    def test_submitted_quiz_no_longer_drives_the_deck(self, enrolled):
        from lms.models import Submission

        from .factories import AssessmentFactory

        student, course, hashing, _ = enrolled
        quiz = AssessmentFactory(
            course=course, type="quiz", due_at=timezone.now() + timedelta(days=2)
        )
        quiz.chapters.set([hashing])
        Submission.objects.create(assessment=quiz, student=student, status="submitted",
                                  submitted_at=timezone.now())  # fmt: skip
        deck = client_for(student).get("/api/v1/decks/today").data
        assert deck["focus"]["kind"] == "review"

    def test_quiet_week_reviews_released_course_chapters(self, enrolled):
        from .factories import ChapterFactory

        student, course, hashing, heaps = enrolled
        ChapterFactory(course=course, body_md=HEAPS.replace("binary heap", "treap"), order=9,
                       available_from=timezone.now() + timedelta(days=10))  # fmt: skip
        deck = client_for(student).get("/api/v1/decks/today").data
        assert deck["focus"]["kind"] == "review"
        assert deck["focus"]["assessment_id"] is None
        assert deck["question_count"] == 5
        assert {i["chapter_id"] for i in deck["items"]} == {hashing.id, heaps.id}

    def test_no_courses_falls_back_to_general_cards(self, student):
        deck = client_for(student).get("/api/v1/decks/today").data
        assert deck["focus"]["kind"] == "general"
        assert all(i["chapter_id"] is None for i in deck["items"])
        assert {i["type"] for i in deck["items"]} <= {"mcq", "flashcard"}


class TestLeaderboard:
    @pytest.fixture
    def classes(self):
        from .factories import CourseFactory, enroll

        me = make_student()
        cs, math, other = (CourseFactory(code=c) for c in ("CS 201", "MATH 210", "BIO 101"))
        enroll(me, cs)
        enroll(me, math)
        ana, ben, cat, stranger = (make_student() for _ in range(4))
        enroll(ana, cs)
        enroll(ben, math)
        enroll(cat, cs)
        enroll(stranger, other)
        return me, cs, math, (ana, ben, cat, stranger)

    @staticmethod
    def earn(student, day, xp):
        DailyDeck.objects.create(student=student, day=day, xp=xp, items=[], cards=[])

    def test_ranks_classmates_by_this_weeks_xp(self, classes):
        me, cs, math, (ana, ben, cat, stranger) = classes
        monday = date(2026, 10, 12)
        self.earn(ana, monday, 90)
        self.earn(ana, monday - timedelta(days=1), 500)  # last week doesn't count
        self.earn(ben, monday + timedelta(days=1), 40)
        self.earn(stranger, monday, 999)
        Streak.objects.create(student=cat, current=6)
        with time_machine.travel(NOON, tick=False):
            client = client_for(me)
            finish_today(client)
            data = client.get("/api/v1/leaderboard").data
        assert data["week_start"] == "2026-10-12"
        assert [c["code"] for c in data["courses"]] == ["CS 201", "MATH 210"]
        rows = data["rows"]
        ids = [r["student_id"] for r in rows]
        assert stranger.id not in ids
        assert ids[0] == ana.id and rows[0]["xp"] == 90 and rows[0]["rank"] == 1
        mine = next(r for r in rows if r["is_me"])
        assert mine["xp"] >= 20 and mine["streak"] == 1
        assert ids == [ana.id, me.id, ben.id, cat.id]

    def test_names_show_first_name_and_initial_only(self):
        from accounts.models import User
        from quizzes.services.leaderboard import display_name

        assert display_name(User(first_name="Priya", last_name="Raman")) == "Priya R."
        assert display_name(User(first_name="Kwame")) == "Kwame"
        assert display_name(User()) == "Student"

    def test_course_filter_and_unknown_courses(self, classes):
        me, cs, math, (ana, ben, cat, stranger) = classes
        client = client_for(me)
        only_cs = client.get(f"/api/v1/leaderboard?course_id={cs.id}").data
        assert only_cs["course_id"] == cs.id
        assert {r["student_id"] for r in only_cs["rows"]} == {me.id, ana.id, cat.id}
        other = client.get("/api/v1/leaderboard?course_id=999999").data
        assert other["course_id"] is None
        assert len(other["rows"]) == 4

    def test_viewer_always_appears_beyond_the_limit(self, classes, monkeypatch):
        from quizzes.services import leaderboard

        me, *_ = classes
        monkeypatch.setattr(leaderboard, "LIMIT", 1)
        rows = client_for(me).get("/api/v1/leaderboard").data["rows"]
        assert any(r["is_me"] for r in rows)
        assert len(rows) <= 2
