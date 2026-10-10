from datetime import timedelta

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.clock import now as clock_now
from lms.access import require_student

from .models import DailyDeck, StreakEvent
from .serializers import (
    AnswerSerializer,
    DailyDeckDetailSerializer,
    DailyDeckSerializer,
    LeaderboardSerializer,
    StreakSerializer,
)
from .services import decks as deck_service
from .services.decks import local_day, today_deck
from .services.streaks import FREEZE_EVERY, MILESTONES, get_streak, settle

HISTORY = 30
WEEK = 7


def _own(request, deck_id: int) -> DailyDeck:
    require_student(request.user)
    return get_object_or_404(
        DailyDeck.objects.select_related("student", "course", "assessment"),
        pk=deck_id,
        student=request.user,
    )


def _detail(request, deck: DailyDeck, milestone: int | None = None) -> Response:
    if milestone:
        from notifications.engine import notify_streak_milestone

        notify_streak_milestone(request.user, deck, milestone)
    context = {"now": clock_now(request.user), "milestone": milestone}
    return Response(DailyDeckDetailSerializer(deck, context=context).data)


def _settled(request, outcome: deck_service.AnswerOutcome) -> Response:
    return _detail(request, outcome.deck, outcome.milestone)


class DeckListView(APIView):
    @extend_schema(responses=DailyDeckSerializer(many=True))
    def get(self, request):
        require_student(request.user)
        decks = DailyDeck.objects.filter(student=request.user).select_related(
            "student", "course", "assessment"
        )[:HISTORY]
        context = {"now": clock_now(request.user)}
        return Response(DailyDeckSerializer(decks, many=True, context=context).data)


class TodayDeckView(APIView):
    @extend_schema(responses=DailyDeckDetailSerializer)
    def get(self, request):
        require_student(request.user)
        settle(request.user)
        return _settled(request, deck_service.expire_if_due(today_deck(request.user)))


class DeckDetailView(APIView):
    @extend_schema(responses=DailyDeckDetailSerializer)
    def get(self, request, deck_id: int):
        return _settled(request, deck_service.expire_if_due(_own(request, deck_id)))


class DeckStartView(APIView):
    @extend_schema(request=None, responses=DailyDeckDetailSerializer)
    def post(self, request, deck_id: int):
        return _detail(request, deck_service.start(_own(request, deck_id)))


class DeckFinishView(APIView):
    @extend_schema(request=None, responses=DailyDeckDetailSerializer)
    def post(self, request, deck_id: int):
        return _settled(request, deck_service.finish(_own(request, deck_id)))


class DeckAnswerView(APIView):
    @extend_schema(request=AnswerSerializer, responses=DailyDeckDetailSerializer)
    def post(self, request, deck_id: int):
        deck = _own(request, deck_id)
        serializer = AnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = deck_service.answer(deck, **serializer.validated_data)
        return _settled(request, outcome)


class LeaderboardView(APIView):
    @extend_schema(
        parameters=[OpenApiParameter("course_id", int, required=False)],
        responses=LeaderboardSerializer,
    )
    def get(self, request):
        from lms.selectors import enrolled_courses

        from .services.leaderboard import board

        require_student(request.user)
        course_id = request.query_params.get("course_id")
        course_id = int(course_id) if course_id and course_id.isdigit() else None
        courses = list(enrolled_courses(request.user).order_by("code").values("id", "code"))
        if course_id not in {c["id"] for c in courses}:
            course_id = None
        start, rows = board(request.user, clock_now(request.user), course_id)
        return Response(
            LeaderboardSerializer(
                {"week_start": start, "course_id": course_id, "courses": courses, "rows": rows}
            ).data
        )


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
