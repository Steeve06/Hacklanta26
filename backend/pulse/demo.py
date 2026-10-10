"""Demo-only controls. Every endpoint 404s unless DEMO_MODE=true, and only admins can call them."""

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.clock import now as clock_now
from accounts.models import StudentProfile, User
from notifications.engine import dispatch_due, scan_student
from notifications.models import Notification
from quizzes.services.streaks import sweep_student
from quizzes.services.windows import sync_checks

from .services import status
from .services.planner import plan


class IsDemoAdmin(BasePermission):
    def has_permission(self, request, view):
        if not settings.DEMO_MODE:
            raise Http404
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or user.role == "admin"))


class DemoStudentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    name = serializers.CharField()
    state = serializers.CharField()
    score = serializers.IntegerField()
    clock = serializers.DateTimeField()
    offset_minutes = serializers.IntegerField()
    sass_level = serializers.IntegerField()
    supportive_mode = serializers.BooleanField()


class ScanSerializer(serializers.Serializer):
    student_id = serializers.IntegerField(required=False)
    ignore_quiet_hours = serializers.BooleanField(default=True)


class ScanResultSerializer(serializers.Serializer):
    created = serializers.IntegerField()
    sent = serializers.IntegerField()


class TravelSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    hours = serializers.IntegerField(required=False, min_value=-24 * 30, max_value=24 * 30)
    reset = serializers.BooleanField(default=False)


def _row(student: User) -> dict:
    current = status.compute(student, save=False)
    profile = student.profile
    return {
        "id": student.id,
        "email": student.email,
        "name": f"{student.first_name} {student.last_name}".strip(),
        "state": current["overall"]["state"],
        "score": current["overall"]["score"],
        "clock": clock_now(student),
        "offset_minutes": profile.clock_offset_minutes,
        "sass_level": profile.sass_level,
        "supportive_mode": profile.supportive_mode,
    }


def _settle(student: User) -> None:
    """After moving the clock: settle closed checks, rebuild the plan, refresh status."""
    sweep_student(student)
    if student.profile.onboarding_done:
        plan(student, reason="demo")
    sync_checks(student)
    status.invalidate(student.id)


class DemoStudentsView(APIView):
    permission_classes = [IsDemoAdmin]

    @extend_schema(responses=DemoStudentSerializer(many=True))
    def get(self, request):
        students = (
            User.objects.filter(role=User.Role.STUDENT, profile__onboarding_done=True)
            .select_related("profile")
            .order_by("first_name")[:50]
        )
        return Response(DemoStudentSerializer([_row(s) for s in students], many=True).data)


class DemoScanView(APIView):
    permission_classes = [IsDemoAdmin]

    @extend_schema(request=ScanSerializer, responses=ScanResultSerializer)
    def post(self, request):
        serializer = ScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        students = User.objects.filter(
            role=User.Role.STUDENT, profile__onboarding_done=True
        ).select_related("profile")
        if data.get("student_id"):
            students = students.filter(pk=data["student_id"])
        created = sent = 0
        for student in students:
            created += len(scan_student(student))
            if data["ignore_quiet_hours"]:
                Notification.objects.filter(
                    student=student, sent_at__isnull=True, cancelled_at__isnull=True
                ).update(scheduled_for=clock_now(student))
            sent += dispatch_due(clock_now(student), student=student)
        return Response({"created": created, "sent": sent})


class DemoReplanView(APIView):
    permission_classes = [IsDemoAdmin]

    @extend_schema(request=None, responses=DemoStudentSerializer)
    def post(self, request, student_id: int):
        student = get_object_or_404(
            User.objects.select_related("profile"), pk=student_id, role=User.Role.STUDENT
        )
        _settle(student)
        return Response(DemoStudentSerializer(_row(student)).data)


class DemoTimeTravelView(APIView):
    permission_classes = [IsDemoAdmin]

    @extend_schema(request=TravelSerializer, responses=DemoStudentSerializer)
    def post(self, request):
        serializer = TravelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        profile = get_object_or_404(StudentProfile, user_id=data["student_id"])
        if data["reset"]:
            profile.clock_offset_minutes = 0
        else:
            profile.clock_offset_minutes = max(
                0, profile.clock_offset_minutes + data.get("hours", 0) * 60
            )
        profile.save(update_fields=["clock_offset_minutes", "updated_at"])
        student = User.objects.select_related("profile").get(pk=data["student_id"])
        _settle(student)
        return Response(DemoStudentSerializer(_row(student)).data)
