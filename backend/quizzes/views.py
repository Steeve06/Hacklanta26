from datetime import timedelta

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.clock import now as clock_now
from lms.access import require_student

from .models import DailyDeck, StreakEvent
from .serializers import (
    DailyDeckDetailSerializer,
    DailyDeckSerializer,
    ReviewSerializer,
    StreakSerializer,
)
from .services.decks import local_day, review, today_deck
from .services.streaks import FREEZE_EVERY, MILESTONES, get_streak, settle

HISTORY = 30
WEEK = 7


def _own(request, deck_id: int) -> DailyDeck:
    require_student(request.user)
    return get_object_or_404(DailyDeck, pk=deck_id, student=request.user)


def _detail(request, deck: DailyDeck, milestone: int | None = None) -> Response:
    context = {"now": clock_now(request.user), "milestone": milestone}
    return Response(DailyDeckDetailSerializer(deck, context=context).data)


class DeckListView(APIView):
    @extend_schema(responses=DailyDeckSerializer(many=True))
    def get(self, request):
        require_student(request.user)
        decks = DailyDeck.objects.filter(student=request.user).select_related("student")[:HISTORY]
        context = {"now": clock_now(request.user)}
        return Response(DailyDeckSerializer(decks, many=True, context=context).data)


class TodayDeckView(APIView):
    @extend_schema(responses=DailyDeckDetailSerializer)
    def get(self, request):
        require_student(request.user)
        settle(request.user)
        return _detail(request, today_deck(request.user))


class DeckDetailView(APIView):
    @extend_schema(responses=DailyDeckDetailSerializer)
    def get(self, request, deck_id: int):
        return _detail(request, _own(request, deck_id))


class DeckReviewView(APIView):
    @extend_schema(request=ReviewSerializer, responses=DailyDeckDetailSerializer)
    def post(self, request, deck_id: int):
        deck = _own(request, deck_id)
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = review(deck, **serializer.validated_data)
        if outcome.milestone:
            from notifications.engine import notify_streak_milestone

            notify_streak_milestone(request.user, outcome.deck, outcome.milestone)
        return _detail(request, outcome.deck, outcome.milestone)


def week_of(student, now) -> list[dict]:
    """The last seven local days, oldest first, with how each went for the streak."""
    today = local_day(student, now)
    first = today - timedelta(days=WEEK - 1)
    done = set(
        DailyDeck.objects.filter(
            student=student, day__gte=first, counted_for_streak=True
        ).values_list("day", flat=True)
    )
    events = dict(
        StreakEvent.objects.filter(student=student, day__gte=first)
        .exclude(result=StreakEvent.Result.ON_TIME)
        .values_list("day", "result")
    )
    days = []
    for offset in range(WEEK):
        day = first + timedelta(days=offset)
        if day in done:
            result = "done"
        elif day in events:
            result = events[day]
        elif day == today:
            result = "open"
        else:
            result = "none"
        days.append({"day": day, "result": result})
    return days


class StreakView(APIView):
    @extend_schema(responses=StreakSerializer)
    def get(self, request):
        require_student(request.user)
        now = clock_now(request.user)
        settle(request.user, now)
        streak = get_streak(request.user)
        upcoming = [m for m in MILESTONES if m > streak.current]
        week = week_of(request.user, now)
        return Response(
            StreakSerializer(
                {
                    "current": streak.current,
                    "longest": streak.longest,
                    "freezes": streak.freezes,
                    "toward_next_freeze": FREEZE_EVERY - streak.on_time_toward_freeze,
                    "next_milestone": upcoming[0] if upcoming else None,
                    "done_today": week[-1]["result"] == "done",
                    "week": week,
                    "recent": StreakEvent.objects.filter(student=request.user)[:10],
                }
            ).data
        )
