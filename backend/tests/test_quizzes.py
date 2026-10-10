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


def finish_today(client, *, knew=True):
    deck = client.get("/api/v1/decks/today").data
    response = None
    for card in deck["cards"]:
        response = client.post(
            f"/api/v1/decks/{deck['id']}/review",
            {"card_id": card["id"], "knew": knew},
            format="json",
        )
    return response


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=NY)


class TestLibrary:
    def test_cards_are_seeded_and_cover_every_topic(self):
        assert Flashcard.objects.filter(active=True).count() == len(CARDS)
        assert {c.topic for c in Flashcard.objects.all()} == set(Flashcard.Topic.values)
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


class TestTakingDecks:
    @time_machine.travel(NOON, tick=False)
    def test_today_is_one_deck_and_finishing_counts_once(self, student):
        client = client_for(student)
        deck = client.get("/api/v1/decks/today").data
        assert client.get("/api/v1/decks/today").data["id"] == deck["id"]
        assert deck["state"] == "open"
        assert all(c["knew"] is None and c["back"] for c in deck["cards"])
        done = finish_today(client)
        assert done.status_code == 200
        assert done.data["state"] == "done"
        assert done.data["counted_for_streak"] is True
        assert done.data["knew"] == DECK_SIZE
        again = client.post(
            f"/api/v1/decks/{deck['id']}/review",
            {"card_id": deck["cards"][0]["id"], "knew": False},
            format="json",
        )
        assert again.data["completed_at"] == done.data["completed_at"]
        streak = Streak.objects.get(student=student)
        assert (streak.current, streak.last_day) == (1, NOON.date())
        assert StreakEvent.objects.filter(student=student).count() == 1

    @time_machine.travel(NOON, tick=False)
    def test_still_learning_cards_still_finish_the_deck(self, student):
        response = finish_today(client_for(student), knew=False)
        assert response.data["counted_for_streak"] is True
        assert response.data["knew"] == 0
        assert response.data["streak"] == 1

    @time_machine.travel(NOON, tick=False)
    def test_card_not_in_deck_is_rejected(self, student):
        client = client_for(student)
        deck = client.get("/api/v1/decks/today").data
        stranger = Flashcard.objects.exclude(id__in=[c["id"] for c in deck["cards"]]).first()
        response = client.post(
            f"/api/v1/decks/{deck['id']}/review", {"card_id": stranger.id, "knew": True},
            format="json",
        )  # fmt: skip
        assert response.status_code == 400

    def test_started_before_midnight_and_finished_in_grace_counts(self, student):
        day = NOON.date()
        client = client_for(student)
        with time_machine.travel(at(day, 23, 55), tick=False):
            deck = client.get("/api/v1/decks/today").data
            client.post(
                f"/api/v1/decks/{deck['id']}/review",
                {"card_id": deck["cards"][0]["id"], "knew": True}, format="json",
            )  # fmt: skip
        with time_machine.travel(at(day, 23, 55) + timedelta(minutes=10), tick=False):
            for card in deck["cards"][1:]:
                last = client.post(
                    f"/api/v1/decks/{deck['id']}/review",
                    {"card_id": card["id"], "knew": True}, format="json",
                )  # fmt: skip
        assert last.data["counted_for_streak"] is True
        assert Streak.objects.get(student=student).last_day == day

    def test_old_deck_finished_late_is_practice(self, student):
        day = NOON.date()
        client = client_for(student)
        with time_machine.travel(at(day, 10), tick=False):
            deck = client.get("/api/v1/decks/today").data
        with time_machine.travel(at(day, 10) + timedelta(days=1), tick=False):
            for card in deck["cards"]:
                last = client.post(
                    f"/api/v1/decks/{deck['id']}/review",
                    {"card_id": card["id"], "knew": True}, format="json",
                )  # fmt: skip
        assert last.data["state"] == "done"
        assert last.data["counted_for_streak"] is False
        assert Streak.objects.get_or_create(student=student)[0].current == 0

    def test_other_students_cannot_open_a_deck(self, student):
        deck = client_for(student).get("/api/v1/decks/today").data
        other = make_student()
        assert client_for(other).get(f"/api/v1/decks/{deck['id']}").status_code == 404


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
def test_deck_list_and_review_are_fast(student, django_assert_max_num_queries):
    client = client_for(student)
    deck = client.get("/api/v1/decks/today").data
    assert [d["id"] for d in client.get("/api/v1/decks").data] == [deck["id"]]
    with django_assert_max_num_queries(16):
        client.post(
            f"/api/v1/decks/{deck['id']}/review",
            {"card_id": deck["cards"][0]["id"], "knew": True}, format="json",
        )  # fmt: skip
