from django.db.models import Count, Prefetch, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.clock import now as clock_now
from accounts.models import User

from . import services
from .access import (
    enrolled_student_ids,
    get_assessment,
    get_chapter,
    get_course,
    require_student,
    require_teacher,
    visible_courses,
)
from .models import (
    Assessment,
    Chapter,
    ChapterProgress,
    DiscussionPost,
    QuizAttempt,
    Submission,
    Syllabus,
)
from .serializers import (
    AnswersSerializer,
    AssessmentDetailSerializer,
    AssessmentSerializer,
    AssessmentWriteSerializer,
    ChapterDetailSerializer,
    ChapterListSerializer,
    ChapterWriteSerializer,
    CourseSerializer,
    DiscussionPostSerializer,
    DiscussionSerializer,
    ExcuseSerializer,
    OverrideSerializer,
    PostCreateSerializer,
    QuestionWriteSerializer,
    QuizAttemptSerializer,
    RosterRowSerializer,
    ScoreSerializer,
    SubmissionCreateSerializer,
    SubmissionSerializer,
    SyllabusSerializer,
)
from .signals import emit_change
from .status import deadline_for, is_done, load_state, status_for


def _student_context(user, assessments):
    if user.role != "student":
        return {"now": clock_now(user)}
    return {"now": clock_now(user), "state": load_state(user, [a.id for a in assessments])}


class CourseListView(APIView):
    @extend_schema(responses=CourseSerializer(many=True))
    def get(self, request):
        user = request.user
        courses = list(
            visible_courses(user)
            .select_related("instructor")
            .prefetch_related("meetings")
            .annotate(
                chapters_total=Count("chapters", distinct=True),
                chapters_completed=Count(
                    "chapters__progress",
                    filter=Q(
                        chapters__progress__student=user,
                        chapters__progress__completed_at__isnull=False,
                    ),
                    distinct=True,
                ),
            )
        )
        assessments = list(
            Assessment.objects.filter(course__in=courses, published=True).only(
                "id", "course_id", "title", "type", "due_at", "cutoff_at"
            )
        )
        current = clock_now(user)
        state = load_state(user, [a.id for a in assessments]) if user.is_student else None
        for course in courses:
            upcoming = []
            for a in assessments:
                if a.course_id != course.id:
                    continue
                due = deadline_for(a, state).due_at if state else a.due_at
                if due < current or (state and is_done(status_for(a, state, current))):
                    continue
                upcoming.append((due, a))
            upcoming.sort(key=lambda pair: pair[0])
            course.next_due = (
                {
                    "id": upcoming[0][1].id,
                    "title": upcoming[0][1].title,
                    "type": upcoming[0][1].type,
                    "due_at": upcoming[0][0],
                }
                if upcoming
                else None
            )
        return Response(CourseSerializer(courses, many=True).data)


class CourseDetailView(APIView):
    @extend_schema(responses=CourseSerializer)
    def get(self, request, course_id: int):
        course = get_course(request.user, course_id)
        course = (
            type(course)
            .objects.select_related("instructor")
            .prefetch_related("meetings")
            .annotate(
                chapters_total=Count("chapters", distinct=True),
                chapters_completed=Count(
                    "chapters__progress",
                    filter=Q(
                        chapters__progress__student=request.user,
                        chapters__progress__completed_at__isnull=False,
                    ),
                    distinct=True,
                ),
            )
            .get(pk=course.pk)
        )
        course.next_due = None
        return Response(CourseSerializer(course).data)


class ChapterListView(APIView):
    @extend_schema(responses=ChapterListSerializer(many=True))
    def get(self, request, course_id: int):
        course = get_course(request.user, course_id)
        chapters = list(course.chapters.all())
        progress = {
            p.chapter_id: p
            for p in ChapterProgress.objects.filter(student=request.user, chapter__course=course)
        }
        context = {"now": clock_now(request.user), "progress": progress}
        return Response(ChapterListSerializer(chapters, many=True, context=context).data)

    @extend_schema(request=ChapterWriteSerializer, responses=ChapterDetailSerializer)
    def post(self, request, course_id: int):
        course = get_course(request.user, course_id)
        require_teacher(request.user, course)
        serializer = ChapterWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if course.chapters.filter(order=serializer.validated_data["order"]).exists():
            raise ValidationError({"order": "Another chapter already uses this number."})
        chapter = serializer.save(course=course)
        emit_change(enrolled_student_ids(course), "chapter_created", chapter_id=chapter.id)
        context = {"now": clock_now(request.user), "viewer_role": request.user.role}
        return Response(ChapterDetailSerializer(chapter, context=context).data, status=201)


class ChapterDetailView(APIView):
    def _context(self, request, chapter):
        progress = ChapterProgress.objects.filter(student=request.user, chapter=chapter).first()
        return {
            "now": clock_now(request.user),
            "progress": {chapter.id: progress} if progress else {},
            "viewer_role": request.user.role,
        }

    @extend_schema(responses=ChapterDetailSerializer)
    def get(self, request, chapter_id: int):
        chapter = get_chapter(request.user, chapter_id)
        if request.user.is_student and chapter.available_from <= clock_now(request.user):
            services.open_chapter(request.user, chapter)
        return Response(
            ChapterDetailSerializer(chapter, context=self._context(request, chapter)).data
        )

    @extend_schema(request=ChapterWriteSerializer, responses=ChapterDetailSerializer)
    def patch(self, request, chapter_id: int):
        chapter = get_chapter(request.user, chapter_id)
        require_teacher(request.user, chapter.course)
        serializer = ChapterWriteSerializer(chapter, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_order = serializer.validated_data.get("order")
        if (
            new_order
            and chapter.course.chapters.filter(order=new_order).exclude(pk=chapter.pk).exists()
        ):
            raise ValidationError({"order": "Another chapter already uses this number."})
        chapter = serializer.save()
        emit_change(enrolled_student_ids(chapter.course), "chapter_updated", chapter_id=chapter.id)
        return Response(
            ChapterDetailSerializer(chapter, context=self._context(request, chapter)).data
        )

    @extend_schema(responses={204: None})
    def delete(self, request, chapter_id: int):
        chapter = get_chapter(request.user, chapter_id)
        require_teacher(request.user, chapter.course)
        students = enrolled_student_ids(chapter.course)
        chapter_id_value = chapter.id
        chapter.delete()
        emit_change(students, "chapter_deleted", chapter_id=chapter_id_value)
        return Response(status=204)


class ChapterCompleteView(APIView):
    @extend_schema(request=None, responses=ChapterListSerializer)
    def post(self, request, chapter_id: int):
        require_student(request.user)
        chapter = get_chapter(request.user, chapter_id)
        progress = services.complete_chapter(request.user, chapter)
        context = {"now": clock_now(request.user), "progress": {chapter.id: progress}}
        return Response(ChapterListSerializer(chapter, context=context).data)


class AssessmentListView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter("type", str, required=False),
            OpenApiParameter("status", str, required=False),
        ],
        responses=AssessmentSerializer(many=True),
    )
    def get(self, request, course_id: int):
        course = get_course(request.user, course_id)
        qs = course.assessments.select_related("course").prefetch_related(
            Prefetch("chapters", queryset=Chapter.objects.only("id"))
        )
        if request.user.is_student:
            qs = qs.filter(published=True)
        if kind := request.query_params.get("type"):
            qs = qs.filter(type=kind)
        assessments = list(qs)
        context = _student_context(request.user, assessments)
        data = AssessmentSerializer(assessments, many=True, context=context).data
        if wanted := request.query_params.get("status"):
            data = [row for row in data if row["status"] == wanted]
        data.sort(key=lambda row: row["effective_due_at"])
        return Response(data)

    @extend_schema(request=AssessmentWriteSerializer, responses=AssessmentDetailSerializer)
    def post(self, request, course_id: int):
        course = get_course(request.user, course_id)
        require_teacher(request.user, course)
        serializer = AssessmentWriteSerializer(data=request.data, context={"course": course})
        serializer.is_valid(raise_exception=True)
        assessment = serializer.save()
        emit_change(enrolled_student_ids(course), "assessment_created", assessment_id=assessment.id)
        context = {"now": clock_now(request.user)}
        return Response(AssessmentDetailSerializer(assessment, context=context).data, status=201)


class AssessmentDetailView(APIView):
    @extend_schema(responses=AssessmentDetailSerializer)
    def get(self, request, assessment_id: int):
        assessment = get_assessment(request.user, assessment_id)
        context = _student_context(request.user, [assessment])
        if request.user.is_student:
            context["student"] = request.user
        return Response(AssessmentDetailSerializer(assessment, context=context).data)

    @extend_schema(request=AssessmentWriteSerializer, responses=AssessmentDetailSerializer)
    def patch(self, request, assessment_id: int):
        assessment = get_assessment(request.user, assessment_id)
        require_teacher(request.user, assessment.course)
        serializer = AssessmentWriteSerializer(
            assessment, data=request.data, partial=True, context={"course": assessment.course}
        )
        serializer.is_valid(raise_exception=True)
        was_published = assessment.published
        assessment = serializer.save()
        emit_change(
            enrolled_student_ids(assessment.course),
            "assessment_updated",
            assessment_id=assessment.id,
        )
        if assessment.published and not was_published:
            emit_change(
                enrolled_student_ids(assessment.course),
                "assessment_published",
                assessment_id=assessment.id,
            )
        context = {"now": clock_now(request.user)}
        return Response(AssessmentDetailSerializer(assessment, context=context).data)

    @extend_schema(responses={204: None})
    def delete(self, request, assessment_id: int):
        assessment = get_assessment(request.user, assessment_id)
        require_teacher(request.user, assessment.course)
        students = enrolled_student_ids(assessment.course)
        removed_id = assessment.id
        assessment.delete()
        emit_change(students, "assessment_deleted", assessment_id=removed_id)
        return Response(status=204)


class AssessmentQuestionsView(APIView):
    @extend_schema(responses=QuestionWriteSerializer(many=True))
    def get(self, request, assessment_id: int):
        assessment = get_assessment(request.user, assessment_id)
        require_teacher(request.user, assessment.course)
        return Response(QuestionWriteSerializer(assessment.questions.all(), many=True).data)


class SubmissionCreateView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(request=SubmissionCreateSerializer, responses=SubmissionSerializer)
    def post(self, request, assessment_id: int):
        require_student(request.user)
        assessment = get_assessment(request.user, assessment_id)
        serializer = SubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submission = services.submit_homework(
            request.user,
            assessment,
            text=serializer.validated_data.get("text", ""),
            upload=serializer.validated_data.get("file"),
        )
        return Response(SubmissionSerializer(submission).data, status=201)


class SubmissionFileView(APIView):
    @extend_schema(responses={(200, "application/octet-stream"): bytes})
    def get(self, request, submission_id: int):
        submission = get_object_or_404(
            Submission.objects.select_related("assessment__course"), pk=submission_id
        )
        is_owner = submission.student_id == request.user.id
        is_teacher = submission.assessment.course.instructor_id == request.user.id
        if not (is_owner or is_teacher or request.user.is_superuser) or not submission.file:
            raise NotFound("File not found.")
        name = submission.file.name.rsplit("/", 1)[-1]
        return FileResponse(submission.file.open("rb"), as_attachment=True, filename=name)


class SubmissionScoreView(APIView):
    @extend_schema(request=ScoreSerializer, responses=SubmissionSerializer)
    def patch(self, request, submission_id: int):
        submission = get_object_or_404(
            Submission.objects.select_related("assessment__course"), pk=submission_id
        )
        require_teacher(request.user, submission.assessment.course)
        serializer = ScoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.grade(submission, serializer.validated_data["score"])
        emit_change([submission.student_id], "graded", assessment_id=submission.assessment_id)
        return Response(SubmissionSerializer(submission).data)


class DiscussionView(APIView):
    @extend_schema(responses=DiscussionSerializer)
    def get(self, request, assessment_id: int):
        assessment = get_assessment(request.user, assessment_id)
        posts = DiscussionPost.objects.filter(assessment=assessment).select_related("author")
        progress = (
            services.discussion_progress(request.user, assessment)
            if request.user.is_student
            else None
        )
        return Response(
            {
                "posts": DiscussionPostSerializer(
                    posts, many=True, context={"request": request}
                ).data,
                "progress": progress,
            }
        )

    @extend_schema(request=PostCreateSerializer, responses=DiscussionPostSerializer)
    def post(self, request, assessment_id: int):
        require_student(request.user)
        assessment = get_assessment(request.user, assessment_id)
        serializer = PostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = services.add_discussion_post(
            request.user,
            assessment,
            serializer.validated_data["body"],
            serializer.validated_data.get("parent"),
        )
        return Response(
            DiscussionPostSerializer(post, context={"request": request}).data, status=201
        )


class QuizAttemptStartView(APIView):
    @extend_schema(request=None, responses=QuizAttemptSerializer)
    def post(self, request, assessment_id: int):
        require_student(request.user)
        assessment = get_assessment(request.user, assessment_id)
        attempt = services.start_quiz(request.user, assessment)
        return Response(QuizAttemptSerializer(attempt).data, status=201)


def _own_attempt(request, attempt_id: int) -> QuizAttempt:
    attempt = (
        QuizAttempt.objects.select_related("assessment", "student")
        .filter(pk=attempt_id, student=request.user)
        .first()
    )
    if attempt is None:
        raise NotFound("Attempt not found.")
    return attempt


class QuizAttemptView(APIView):
    @extend_schema(responses=QuizAttemptSerializer)
    def get(self, request, attempt_id: int):
        attempt = _own_attempt(request, attempt_id)
        if attempt.submitted_at is None and clock_now(request.user) > attempt.deadline_at:
            attempt = services.finalize_attempt(attempt, auto=True)
        return Response(QuizAttemptSerializer(attempt).data)

    @extend_schema(request=AnswersSerializer, responses=QuizAttemptSerializer)
    def patch(self, request, attempt_id: int):
        attempt = _own_attempt(request, attempt_id)
        serializer = AnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = services.save_quiz_answers(attempt, serializer.validated_data["answers"])
        return Response(QuizAttemptSerializer(attempt).data)


class QuizAttemptSubmitView(APIView):
    @extend_schema(request=AnswersSerializer, responses=QuizAttemptSerializer)
    def post(self, request, attempt_id: int):
        attempt = _own_attempt(request, attempt_id)
        serializer = AnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = services.submit_quiz(attempt, serializer.validated_data["answers"])
        return Response(QuizAttemptSerializer(attempt).data)


class OverrideView(APIView):
    @extend_schema(request=OverrideSerializer, responses=OverrideSerializer)
    def post(self, request, assessment_id: int):
        assessment = get_assessment(request.user, assessment_id)
        require_teacher(request.user, assessment.course)
        serializer = OverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        student = _enrolled_student(assessment, data["student_id"])
        override = services.set_override(
            assessment, student, data["due_at"], data.get("cutoff_at"), data.get("reason", "")
        )
        return Response(OverrideSerializer(override).data, status=201)


class ExcuseView(APIView):
    @extend_schema(request=ExcuseSerializer, responses={204: None})
    def post(self, request, assessment_id: int):
        assessment = get_assessment(request.user, assessment_id)
        require_teacher(request.user, assessment.course)
        serializer = ExcuseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = _enrolled_student(assessment, serializer.validated_data["student"])
        services.set_excused(assessment, student, serializer.validated_data["excused"])
        return Response(status=status.HTTP_204_NO_CONTENT)


def _enrolled_student(assessment: Assessment, student_id: int) -> User:
    if student_id not in enrolled_student_ids(assessment.course):
        raise ValidationError({"student": "That student isn't enrolled in this course."})
    return User.objects.get(pk=student_id)


class RosterView(APIView):
    @extend_schema(responses=RosterRowSerializer(many=True))
    def get(self, request, assessment_id: int):
        assessment = get_assessment(request.user, assessment_id)
        require_teacher(request.user, assessment.course)
        students = User.objects.filter(pk__in=enrolled_student_ids(assessment.course)).order_by(
            "first_name"
        )
        rows = []
        for student in students:
            state = load_state(student, [assessment.id])
            latest = state.latest.get(assessment.id)
            deadline = deadline_for(assessment, state)
            rows.append(
                {
                    "student_id": student.id,
                    "name": f"{student.first_name} {student.last_name}".strip(),
                    "email": student.email,
                    "status": status_for(assessment, state, clock_now(student)),
                    "effective_due_at": deadline.due_at,
                    "extended": deadline.extended,
                    "submission_id": latest.id if latest else None,
                    "submitted_at": latest.submitted_at if latest else None,
                    "score": latest.score if latest else None,
                    "has_file": bool(latest and latest.file),
                }
            )
        return Response(RosterRowSerializer(rows, many=True).data)


class SyllabusView(APIView):
    @extend_schema(responses=SyllabusSerializer)
    def get(self, request, course_id: int):
        course = get_course(request.user, course_id)
        syllabus = (
            Syllabus.objects.select_related("course__instructor")
            .prefetch_related("weeks__chapters", "course__meetings")
            .filter(course=course)
            .first()
        )
        if syllabus is None:
            raise NotFound("This course has no syllabus yet.")
        return Response(SyllabusSerializer(syllabus).data)
