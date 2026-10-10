from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.clock import now as clock_now
from lms.access import require_student
from lms.models import Chapter

from .models import CheckAttempt, StreakEvent, StudyCheck
from .serializers import (
    AnswerSerializer,
    StreakSerializer,
    StudyCheckDetailSerializer,
    StudyCheckSerializer,
)
from .services.checks import answer, start_attempt
from .services.streaks import FREEZE_EVERY, MILESTONES, get_streak, sweep_student, week_of

CHAPTERS = Prefetch("chapters", queryset=Chapter.objects.select_related("course"))
ATTEMPTS = Prefetch("attempts", queryset=CheckAttempt.objects.prefetch_related("answers"))


def _checks(student):
    return StudyCheck.objects.filter(student=student).prefetch_related(CHAPTERS, ATTEMPTS)


def _own(request, check_id: int) -> StudyCheck:
    require_student(request.user)
    return get_object_or_404(_checks(request.user), pk=check_id)


def _detail(request, check_id: int, milestone: int | None = None) -> Response:
    check = _own(request, check_id)
    context = {"now": clock_now(request.user), "milestone": milestone}
    return Response(StudyCheckDetailSerializer(check, context=context).data)


class CheckListView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter("state", str, enum=["open", "upcoming", "past"], required=False)
        ],
        responses=StudyCheckSerializer(many=True),
    )
    def get(self, request):
        require_student(request.user)
        now = clock_now(request.user)
        sweep_student(request.user, now)
        qs = _checks(request.user)
        state = request.query_params.get("state")
        if state == "open":
            qs = qs.filter(opens_at__lte=now, closes_at__gte=now, passed=False, resolved=False)
        elif state == "upcoming":
            qs = qs.filter(opens_at__gt=now)
        elif state == "past":
            qs = qs.filter(Q(closes_at__lt=now) | Q(passed=True) | Q(resolved=True))
            qs = qs.order_by("-closes_at")[:30]
        return Response(StudyCheckSerializer(qs, many=True, context={"now": now}).data)


class CheckDetailView(APIView):
    @extend_schema(responses=StudyCheckDetailSerializer)
    def get(self, request, check_id: int):
        return _detail(request, check_id)


class CheckStartView(APIView):
    @extend_schema(request=None, responses=StudyCheckDetailSerializer)
    def post(self, request, check_id: int):
        start_attempt(_own(request, check_id))
        return _detail(request, check_id)


class CheckAnswerView(APIView):
    @extend_schema(request=AnswerSerializer, responses=StudyCheckDetailSerializer)
    def post(self, request, check_id: int):
        check = _own(request, check_id)
        serializer = AnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = answer(check, **serializer.validated_data)
        if outcome.milestone:
            from notifications.engine import notify_streak_milestone

            notify_streak_milestone(request.user, check, outcome.milestone)
        return _detail(request, check_id, outcome.milestone)


class StreakView(APIView):
    @extend_schema(responses=StreakSerializer)
    def get(self, request):
        require_student(request.user)
        now = clock_now(request.user)
        sweep_student(request.user, now)
        streak = get_streak(request.user)
        upcoming = [m for m in MILESTONES if m > streak.current]
        return Response(
            StreakSerializer(
                {
                    "current": streak.current,
                    "longest": streak.longest,
                    "freezes": streak.freezes,
                    "toward_next_freeze": FREEZE_EVERY - streak.on_time_toward_freeze,
                    "next_milestone": upcoming[0] if upcoming else None,
                    "week": week_of(request.user, now),
                    "recent": StreakEvent.objects.filter(student=request.user)[:10],
                }
            ).data
        )
