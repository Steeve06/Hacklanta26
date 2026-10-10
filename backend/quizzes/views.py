from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.clock import now as clock_now
from lms.access import require_student
from lms.models import Chapter

from .models import ChapterQuiz, StreakEvent
from .serializers import (
    ChapterQuizDetailSerializer,
    ChapterQuizSerializer,
    QuizAnswersSerializer,
    StreakSerializer,
)
from .services.attempts import start, submit
from .services.streaks import FREEZE_EVERY, MILESTONES, get_streak

CHAPTERS = Prefetch("chapters", queryset=Chapter.objects.select_related("course"))


def _own(request, quiz_id: int) -> ChapterQuiz:
    require_student(request.user)
    return get_object_or_404(
        ChapterQuiz.objects.select_related("streakevent").prefetch_related(CHAPTERS, "answers"),
        pk=quiz_id,
        student=request.user,
    )


class QuizListView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter("state", str, enum=["open", "upcoming", "closed"], required=False)
        ],
        responses=ChapterQuizSerializer(many=True),
    )
    def get(self, request):
        require_student(request.user)
        now = clock_now(request.user)
        qs = (
            ChapterQuiz.objects.filter(student=request.user)
            .select_related("streakevent")
            .prefetch_related(CHAPTERS)
        )
        state = request.query_params.get("state")
        if state == "open":
            qs = qs.filter(opens_at__lte=now, closes_at__gte=now, submitted_at__isnull=True)
        elif state == "upcoming":
            qs = qs.filter(opens_at__gt=now)
        elif state == "closed":
            qs = qs.filter(closes_at__lt=now) | qs.filter(submitted_at__isnull=False)
            qs = qs.order_by("-closes_at")[:30]
        return Response(ChapterQuizSerializer(qs, many=True, context={"now": now}).data)


class QuizDetailView(APIView):
    @extend_schema(responses=ChapterQuizDetailSerializer)
    def get(self, request, quiz_id: int):
        quiz = _own(request, quiz_id)
        return Response(
            ChapterQuizDetailSerializer(quiz, context={"now": clock_now(request.user)}).data
        )


class QuizStartView(APIView):
    @extend_schema(request=None, responses=ChapterQuizDetailSerializer)
    def post(self, request, quiz_id: int):
        quiz = start(_own(request, quiz_id))
        return Response(
            ChapterQuizDetailSerializer(quiz, context={"now": clock_now(request.user)}).data
        )


class QuizSubmitView(APIView):
    @extend_schema(request=QuizAnswersSerializer, responses=ChapterQuizDetailSerializer)
    def post(self, request, quiz_id: int):
        quiz = _own(request, quiz_id)
        serializer = QuizAnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = submit(quiz, serializer.validated_data["answers"])
        if outcome.milestone:
            from notifications.engine import notify_streak_milestone

            notify_streak_milestone(request.user, outcome.quiz, outcome.milestone)
        quiz = _own(request, quiz_id)
        context = {"now": clock_now(request.user), "milestone": outcome.milestone}
        return Response(ChapterQuizDetailSerializer(quiz, context=context).data)


class StreakView(APIView):
    @extend_schema(responses=StreakSerializer)
    def get(self, request):
        require_student(request.user)
        streak = get_streak(request.user)
        upcoming = [m for m in MILESTONES if m > streak.current]
        events = StreakEvent.objects.filter(student=request.user)[:10]
        return Response(
            StreakSerializer(
                {
                    "current": streak.current,
                    "longest": streak.longest,
                    "freezes": streak.freezes,
                    "toward_next_freeze": FREEZE_EVERY - streak.on_time_toward_freeze,
                    "next_milestone": upcoming[0] if upcoming else None,
                    "recent": events,
                }
            ).data
        )
