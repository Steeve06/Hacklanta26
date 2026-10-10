from datetime import datetime, time, timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.clock import now as clock_now
from accounts.models import StudentProfile
from config.throttles import RegenerateThrottle
from lms.access import require_student
from lms.selectors import student_snapshot

from .models import AvailabilityBlock, Blackout, PlanJob
from .serializers import (
    AvailabilitySerializer,
    BlackoutSerializer,
    GenerateSerializer,
    PlanJobSerializer,
    ScheduleSerializer,
    SessionSerializer,
    SessionUpdateSerializer,
    StatusSerializer,
)
from .services import sessions as session_service
from .services import status as status_service
from .services.replan import request_replan, start_generate_job

UPCOMING_COUNT = 6


class StudentView(APIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_student(request.user)


class AvailabilityView(StudentView):
    @extend_schema(responses=AvailabilitySerializer)
    def get(self, request):
        blocks = AvailabilityBlock.objects.filter(student=request.user)
        return Response(AvailabilitySerializer({"blocks": blocks}).data)

    @extend_schema(request=AvailabilitySerializer, responses=AvailabilitySerializer)
    def put(self, request):
        serializer = AvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            AvailabilityBlock.objects.filter(student=request.user).delete()
            AvailabilityBlock.objects.bulk_create(
                AvailabilityBlock(student=request.user, **b)
                for b in serializer.validated_data["blocks"]
            )
        request_replan(request.user, "availability")
        blocks = AvailabilityBlock.objects.filter(student=request.user)
        return Response(AvailabilitySerializer({"blocks": blocks}).data)


class BlackoutListView(StudentView):
    @extend_schema(responses=BlackoutSerializer(many=True))
    def get(self, request):
        rows = Blackout.objects.filter(student=request.user, end__gte=clock_now(request.user))
        return Response(BlackoutSerializer(rows, many=True).data)

    @extend_schema(request=BlackoutSerializer, responses=BlackoutSerializer)
    def post(self, request):
        serializer = BlackoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        blackout = serializer.save(student=request.user)
        request_replan(request.user, "blackout")
        return Response(BlackoutSerializer(blackout).data, status=201)


class BlackoutDetailView(StudentView):
    @extend_schema(responses={204: None})
    def delete(self, request, blackout_id: int):
        get_object_or_404(Blackout, pk=blackout_id, student=request.user).delete()
        request_replan(request.user, "blackout")
        return Response(status=204)


class GenerateView(StudentView):
    throttle_classes = [RegenerateThrottle]

    @extend_schema(request=GenerateSerializer, responses={202: PlanJobSerializer})
    def post(self, request):
        serializer = GenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not AvailabilityBlock.objects.filter(student=request.user).exists():
            raise ValidationError(
                {"code": "no_availability", "detail": "Add at least one weekly study block first."}
            )
        profile, _ = StudentProfile.objects.get_or_create(user=request.user)
        if "feedback" in serializer.validated_data:
            profile.plan_feedback = serializer.validated_data["feedback"]
            profile.save(update_fields=["plan_feedback", "updated_at"])
        job = start_generate_job(request.user, profile.plan_feedback)
        return Response(PlanJobSerializer(job).data, status=202)


class JobView(StudentView):
    @extend_schema(responses=PlanJobSerializer)
    def get(self, request, job_id: int):
        job = get_object_or_404(PlanJob, pk=job_id, student=request.user)
        return Response(PlanJobSerializer(job).data)


class LatestJobView(StudentView):
    @extend_schema(responses=PlanJobSerializer)
    def get(self, request):
        job = (
            PlanJob.objects.filter(student=request.user, kind=PlanJob.Kind.GENERATE)
            .order_by("-id")
            .first()
        )
        if job is None:
            raise NotFound("No schedule has been generated yet.")
        return Response(PlanJobSerializer(job).data)


class JobCancelView(StudentView):
    @extend_schema(request=None, responses=PlanJobSerializer)
    def post(self, request, job_id: int):
        job = get_object_or_404(PlanJob, pk=job_id, student=request.user)
        if job.state in (PlanJob.State.QUEUED, PlanJob.State.RUNNING):
            job.state = PlanJob.State.CANCELLED
            job.save(update_fields=["state", "updated_at"])
        return Response(PlanJobSerializer(job).data)


def _range(
    view: str, raw_from: str | None, user, snapshot
) -> tuple[datetime | None, datetime | None]:
    tz = user.tz
    if raw_from:
        try:
            anchor = datetime.fromisoformat(raw_from).date()
        except ValueError as exc:
            raise ValidationError({"from": "Use YYYY-MM-DD."}) from exc
    else:
        anchor = clock_now(user).astimezone(tz).date()
    if view == "today":
        start = datetime.combine(anchor, time(0), tzinfo=tz)
        return start, datetime.combine(anchor + timedelta(days=1), time(0), tzinfo=tz)
    if view == "week":
        monday = anchor - timedelta(days=anchor.weekday())
        start = datetime.combine(monday, time(0), tzinfo=tz)
        return start, datetime.combine(monday + timedelta(days=7), time(0), tzinfo=tz)
    return None, None


def _deadline(a, snapshot) -> dict:
    return {
        "id": a.id,
        "course": a.course_id,
        "course_code": snapshot.course(a.course_id).code,
        "title": a.title,
        "type": a.type,
        "due_at": a.due_at,
        "closes_at": a.closes_at,
        "status": a.status,
        "weight_pct": float(a.weight_pct),
        "extended": a.extended,
    }


class ScheduleView(StudentView):
    @extend_schema(
        parameters=[
            OpenApiParameter("view", str, enum=["today", "week", "overall"], required=False),
            OpenApiParameter("from", str, required=False, description="Local date YYYY-MM-DD"),
        ],
        responses=ScheduleSerializer,
    )
    def get(self, request):
        user = request.user
        schedule = session_service.active_schedule(user)
        if schedule is None:
            raise NotFound("No schedule yet.")
        view = request.query_params.get("view", "week")
        snapshot = student_snapshot(user, clock_now(user))
        start, end = _range(view, request.query_params.get("from"), user, snapshot)
        sessions = schedule.sessions.select_related("task")
        deadlines = [a for a in snapshot.assessments if a.status != "excused"]
        if start and end:
            sessions = sessions.filter(start__lt=end, end__gt=start)
            deadlines = [a for a in deadlines if start <= a.due_at < end]
        now = clock_now(user)
        upcoming = [
            a
            for a in snapshot.assessments
            if not a.done and a.status != "missed" and a.closes_at > now
        ][:UPCOMING_COUNT]
        data = {
            "id": schedule.id,
            "version": schedule.version,
            "generated_at": schedule.generated_at,
            "horizon_end": schedule.horizon_end,
            "summary": schedule.summary,
            "overload_report": schedule.overload_report,
            "sessions": list(sessions),
            "deadlines": [_deadline(a, snapshot) for a in deadlines],
            "upcoming": [_deadline(a, snapshot) for a in upcoming],
            "courses": [c.__dict__ for c in snapshot.courses],
            "term_start": snapshot.term_start,
            "term_end": snapshot.term_end,
        }
        return Response(ScheduleSerializer(data).data)


class StatusView(StudentView):
    @extend_schema(responses=StatusSerializer)
    def get(self, request):
        return Response(StatusSerializer(status_service.current(request.user)).data)


class SessionView(StudentView):
    @extend_schema(request=SessionUpdateSerializer, responses=SessionSerializer)
    def patch(self, request, session_id: int):
        session = session_service.active_session(request.user, session_id)
        serializer = SessionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = session_service.update_status(
            request.user,
            session,
            serializer.validated_data["status"],
            serializer.validated_data.get("completed_minutes"),
        )
        return Response(SessionSerializer(updated).data)


class SessionRescheduleView(StudentView):
    @extend_schema(request=None, responses=SessionSerializer)
    def post(self, request, session_id: int):
        session = session_service.active_session(request.user, session_id)
        return Response(SessionSerializer(session_service.reschedule(request.user, session)).data)
