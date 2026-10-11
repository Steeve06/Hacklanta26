"""The teacher dashboard: what each course has so far and what needs the teacher, plus the admin
side that pre-registers courses for teachers to claim."""

from django.db import IntegrityError
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.clock import now as clock_now
from accounts.models import User

from .access import get_course, require_teacher, visible_courses
from .models import Assessment, Enrollment, Submission, Syllabus
from .registration import (
    DEFAULT_POLICIES,
    Meeting,
    Registration,
    is_pending_teacher,
    register_course,
)
from .serializers import MeetingSerializer, NextDueSerializer, SyllabusSerializer

HEX = r"^#[0-9a-fA-F]{6}$"


class TeachingCourseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    title = serializers.CharField()
    color = serializers.CharField()
    term = serializers.CharField()
    meetings = MeetingSerializer(many=True)
    students = serializers.IntegerField()
    chapters = serializers.IntegerField()
    homework = serializers.IntegerField()
    discussions = serializers.IntegerField()
    quizzes = serializers.IntegerField()
    hidden = serializers.IntegerField(help_text="Assignments not yet visible to students")
    to_grade = serializers.IntegerField(help_text="Submissions waiting for a score")
    next_due = NextDueSerializer(allow_null=True)


class TeachingOverviewView(APIView):
    @extend_schema(responses=TeachingCourseSerializer(many=True))
    def get(self, request):
        user = request.user
        if user.role == User.Role.STUDENT:
            raise PermissionDenied("Only teachers have a teaching dashboard.")
        courses = (
            visible_courses(user)
            .select_related("term")
            .prefetch_related("meetings")
            .annotate(
                n_students=Count(
                    "enrollments",
                    filter=Q(enrollments__role=Enrollment.Role.STUDENT),
                    distinct=True,
                ),
                n_chapters=Count("chapters", distinct=True),
            )
        )
        now = clock_now(user)
        rows = []
        for course in courses:
            by_type = dict(
                Assessment.objects.filter(course=course).values_list("type").annotate(n=Count("id"))
            )
            upcoming = (
                Assessment.objects.filter(course=course, published=True, due_at__gte=now)
                .order_by("due_at")
                .first()
            )
            rows.append(
                {
                    "id": course.id,
                    "code": course.code,
                    "title": course.title,
                    "color": course.color,
                    "term": course.term.name,
                    "meetings": course.meetings.all(),
                    "students": course.n_students,
                    "chapters": course.n_chapters,
                    "homework": by_type.get("homework", 0),
                    "discussions": by_type.get("discussion", 0),
                    "quizzes": by_type.get("quiz", 0),
                    "hidden": Assessment.objects.filter(course=course, published=False).count(),
                    "to_grade": Submission.objects.filter(
                        assessment__course=course,
                        assessment__type=Assessment.Type.HOMEWORK,
                        status__in=[Submission.Status.SUBMITTED, Submission.Status.LATE],
                        score__isnull=True,
                    ).count(),
                    "next_due": {
                        "id": upcoming.id,
                        "title": upcoming.title,
                        "type": upcoming.type,
                        "due_at": upcoming.due_at,
                    }
                    if upcoming
                    else None,
                }
            )
        return Response(TeachingCourseSerializer(rows, many=True).data)


class SyllabusUpdateSerializer(serializers.Serializer):
    description = serializers.CharField(allow_blank=True, required=False, max_length=4000)
    office_hours = serializers.CharField(allow_blank=True, required=False, max_length=200)
    grading = serializers.ListField(child=serializers.DictField(), required=False)

    def validate_grading(self, value):
        cleaned = []
        for item in value:
            label = str(item.get("label", "")).strip()
            try:
                weight = float(item.get("weight_pct"))
            except (TypeError, ValueError):
                raise serializers.ValidationError("Each weight must be a number.") from None
            if not label or not 0 <= weight <= 100:
                raise serializers.ValidationError("Each item needs a label and a 0–100 weight.")
            cleaned.append({"label": label[:80], "weight_pct": weight})
        if cleaned and round(sum(i["weight_pct"] for i in cleaned), 2) != 100:
            raise serializers.ValidationError("Weights must add up to 100%.")
        return cleaned


class SyllabusEditView(APIView):
    @extend_schema(request=SyllabusUpdateSerializer, responses=SyllabusSerializer)
    def patch(self, request, course_id: int):
        course = get_course(request.user, course_id)
        require_teacher(request.user, course)
        serializer = SyllabusUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        syllabus, _ = Syllabus.objects.get_or_create(
            course=course,
            defaults={"description": "", "office_hours": "", "policies": DEFAULT_POLICIES},
        )
        for key, value in serializer.validated_data.items():
            setattr(syllabus, key, value)
        syllabus.save()
        return Response(SyllabusSerializer(syllabus).data)


class MeetingWriteSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    location = serializers.CharField(max_length=80, allow_blank=True, required=False, default="")

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": "Class must end after it starts."})
        return attrs


class RegistrationSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    title = serializers.CharField(max_length=120)
    teacher_email = serializers.EmailField()
    teacher_first_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    teacher_last_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    color = serializers.RegexField(HEX, required=False, default="#1f6f5c")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    office_hours = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )
    meetings = MeetingWriteSerializer(many=True, required=False, default=list)


class RegisteredCourseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    title = serializers.CharField()
    term = serializers.CharField(source="term.name")
    teacher_email = serializers.EmailField(source="instructor.email")
    claimed = serializers.SerializerMethodField()

    def get_claimed(self, obj) -> bool:
        return not is_pending_teacher(obj.instructor)


def _require_admin(user) -> None:
    if not (user.is_superuser or user.role == User.Role.ADMIN):
        raise PermissionDenied("Only admins can register courses.")


class CourseRegistrationView(APIView):
    @extend_schema(responses=RegisteredCourseSerializer(many=True))
    def get(self, request):
        _require_admin(request.user)
        courses = visible_courses(request.user).select_related("term", "instructor")
        return Response(RegisteredCourseSerializer(courses, many=True).data)

    @extend_schema(request=RegistrationSerializer, responses={201: RegisteredCourseSerializer})
    def post(self, request):
        _require_admin(request.user)
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        meetings = [
            Meeting(m["weekday"], m["start_time"], m["end_time"], m.get("location", ""))
            for m in data.pop("meetings")
        ]
        try:
            course = register_course(Registration(**data, meetings=meetings))
        except IntegrityError as exc:
            raise ValidationError(
                {"code": "A course with this code already exists this term."}
            ) from exc
        except ValueError as exc:
            raise ValidationError({"teacher_email": str(exc)}) from exc
        return Response(RegisteredCourseSerializer(course).data, status=201)
