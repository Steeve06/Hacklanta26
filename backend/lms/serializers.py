from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .markdown import render_markdown
from .models import (
    Assessment,
    Chapter,
    Course,
    CourseMeeting,
    DiscussionPost,
    DueDateOverride,
    QuizAttempt,
    QuizQuestion,
    Submission,
    Syllabus,
    SyllabusWeek,
)
from .status import deadline_for, status_for


class NextDueSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    type = serializers.CharField()
    due_at = serializers.DateTimeField()


class MeetingSerializer(serializers.ModelSerializer):
    """A weekly class time in the campus time zone (`timezone`)."""

    timezone = serializers.SerializerMethodField()

    class Meta:
        model = CourseMeeting
        fields = ["weekday", "start_time", "end_time", "location", "timezone"]
        read_only_fields = fields

    def get_timezone(self, obj) -> str:
        from django.conf import settings

        return settings.CAMPUS_TIMEZONE


class CourseSerializer(serializers.ModelSerializer):
    instructor_name = serializers.SerializerMethodField()
    meetings = MeetingSerializer(many=True, read_only=True)
    chapters_total = serializers.IntegerField(read_only=True)
    chapters_completed = serializers.IntegerField(read_only=True)
    next_due = NextDueSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Course
        fields = [
            "id", "code", "title", "color", "instructor_name", "meetings",
            "chapters_total", "chapters_completed", "next_due",
        ]  # fmt: skip
        read_only_fields = fields

    def get_instructor_name(self, obj) -> str:
        return f"{obj.instructor.first_name} {obj.instructor.last_name}".strip()


class LinkSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=120)
    url = serializers.URLField()


class ChapterListSerializer(serializers.ModelSerializer):
    locked = serializers.SerializerMethodField()
    completed_at = serializers.SerializerMethodField()
    opened_at = serializers.SerializerMethodField()

    class Meta:
        model = Chapter
        fields = [
            "id", "order", "title", "reading_minutes", "available_from",
            "locked", "completed_at", "opened_at",
        ]  # fmt: skip
        read_only_fields = fields

    def get_locked(self, obj) -> bool:
        return obj.available_from > self.context["now"]

    def _progress(self, obj):
        return self.context.get("progress", {}).get(obj.id)

    def get_completed_at(self, obj) -> str | None:
        p = self._progress(obj)
        return p.completed_at.isoformat() if p and p.completed_at else None

    def get_opened_at(self, obj) -> str | None:
        p = self._progress(obj)
        return p.first_opened_at.isoformat() if p and p.first_opened_at else None


class ChapterDetailSerializer(ChapterListSerializer):
    body_html = serializers.SerializerMethodField()
    body_md = serializers.SerializerMethodField()
    objectives = serializers.ListField(child=serializers.CharField())
    links = LinkSerializer(many=True)
    course_code = serializers.CharField(source="course.code", read_only=True)
    course_id = serializers.IntegerField(source="course.id", read_only=True)

    class Meta(ChapterListSerializer.Meta):
        fields = ChapterListSerializer.Meta.fields + [
            "body_html", "body_md", "objectives", "links", "course_code", "course_id",
        ]  # fmt: skip
        read_only_fields = fields

    def get_body_html(self, obj) -> str:
        if self.get_locked(obj) and self.context.get("viewer_role") == "student":
            return ""
        return render_markdown(obj.body_md, cache_key=obj.content_hash)

    def get_body_md(self, obj) -> str:
        return "" if self.context.get("viewer_role") == "student" else obj.body_md


class ChapterWriteSerializer(serializers.ModelSerializer):
    objectives = serializers.ListField(child=serializers.CharField(max_length=200), min_length=1)
    links = LinkSerializer(many=True, required=False)

    class Meta:
        model = Chapter
        fields = [
            "order", "title", "body_md", "links", "reading_minutes", "objectives", "available_from",
        ]  # fmt: skip


class AssessmentSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    effective_due_at = serializers.SerializerMethodField()
    effective_cutoff_at = serializers.SerializerMethodField()
    extended = serializers.SerializerMethodField()
    overdue = serializers.SerializerMethodField()
    chapter_ids = serializers.PrimaryKeyRelatedField(source="chapters", many=True, read_only=True)
    course_code = serializers.CharField(source="course.code", read_only=True)

    class Meta:
        model = Assessment
        fields = [
            "id", "course", "course_code", "type", "title", "chapter_ids", "open_at", "due_at",
            "cutoff_at", "points", "weight_pct", "est_minutes", "published", "status",
            "effective_due_at", "effective_cutoff_at", "extended", "overdue",
        ]  # fmt: skip
        read_only_fields = fields

    def _state(self):
        return self.context.get("state")

    def get_status(self, obj) -> str | None:
        state = self._state()
        return status_for(obj, state, self.context["now"]) if state else None

    def get_effective_due_at(self, obj) -> str:
        state = self._state()
        return (deadline_for(obj, state).due_at if state else obj.due_at).isoformat()

    def get_effective_cutoff_at(self, obj) -> str | None:
        state = self._state()
        cutoff = deadline_for(obj, state).cutoff_at if state else obj.cutoff_at
        return cutoff.isoformat() if cutoff else None

    def get_extended(self, obj) -> bool:
        state = self._state()
        return bool(state and deadline_for(obj, state).extended)

    def get_overdue(self, obj) -> bool:
        state = self._state()
        if not state:
            return False
        status = status_for(obj, state, self.context["now"])
        return status in ("not_started", "in_progress") and (
            self.context["now"] > deadline_for(obj, state).due_at
        )


class QuestionPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizQuestion
        fields = ["id", "order", "type", "prompt", "options", "points"]
        read_only_fields = fields


class QuestionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizQuestion
        fields = ["id", "order", "type", "prompt", "options", "correct_index", "points"]

    def validate(self, attrs):
        options = attrs.get("options", [])
        if attrs.get("type") == QuizQuestion.Type.TRUE_FALSE and len(options) != 2:
            raise serializers.ValidationError({"options": "True/false needs exactly 2 options."})
        if attrs.get("type") == QuizQuestion.Type.MULTIPLE_CHOICE and len(options) < 2:
            raise serializers.ValidationError({"options": "Add at least 2 options."})
        if len(set(options)) != len(options):
            raise serializers.ValidationError({"options": "Options must be different."})
        if attrs.get("correct_index", 0) >= len(options):
            raise serializers.ValidationError({"correct_index": "Pick one of the options."})
        return attrs


class SubmissionSerializer(serializers.ModelSerializer):
    file_name = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = ["id", "status", "text", "file_name", "submitted_at", "score", "attempt_no"]
        read_only_fields = fields

    def get_file_name(self, obj) -> str | None:
        return obj.file.name.rsplit("/", 1)[-1] if obj.file else None


class AssessmentDetailSerializer(AssessmentSerializer):
    instructions_html = serializers.SerializerMethodField()
    submissions = serializers.SerializerMethodField()
    discussion_replies_required = serializers.IntegerField()
    time_limit_minutes = serializers.IntegerField()
    max_attempts = serializers.IntegerField()
    attempts_used = serializers.SerializerMethodField()
    questions_count = serializers.SerializerMethodField()

    class Meta(AssessmentSerializer.Meta):
        fields = AssessmentSerializer.Meta.fields + [
            "instructions", "instructions_html", "submissions", "discussion_replies_required",
            "time_limit_minutes", "max_attempts", "attempts_used", "questions_count",
        ]  # fmt: skip
        read_only_fields = fields

    def get_instructions_html(self, obj) -> str:
        return render_markdown(obj.instructions)

    @extend_schema_field(SubmissionSerializer(many=True))
    def get_submissions(self, obj):
        student = self.context.get("student")
        if student is None:
            return []
        rows = Submission.objects.filter(assessment=obj, student=student)[:10]
        return SubmissionSerializer(rows, many=True).data

    def get_attempts_used(self, obj) -> int:
        state = self._state()
        return state.attempts_used.get(obj.id, 0) if state else 0

    def get_questions_count(self, obj) -> int:
        return obj.questions.count()


class AssessmentWriteSerializer(serializers.ModelSerializer):
    chapter_ids = serializers.PrimaryKeyRelatedField(
        source="chapters", many=True, queryset=Chapter.objects.all(), required=False
    )
    questions = QuestionWriteSerializer(many=True, required=False)

    class Meta:
        model = Assessment
        fields = [
            "type", "title", "instructions", "chapter_ids", "open_at", "due_at", "cutoff_at",
            "points", "weight_pct", "est_minutes", "discussion_replies_required",
            "time_limit_minutes", "max_attempts", "published", "questions",
        ]  # fmt: skip

    def validate(self, attrs):
        open_at = attrs.get("open_at", getattr(self.instance, "open_at", None))
        due_at = attrs.get("due_at", getattr(self.instance, "due_at", None))
        cutoff = attrs.get("cutoff_at", getattr(self.instance, "cutoff_at", None))
        if open_at and due_at and open_at >= due_at:
            raise serializers.ValidationError({"due_at": "Due date must be after the open date."})
        if cutoff and due_at and cutoff < due_at:
            raise serializers.ValidationError({"cutoff_at": "Cut-off must be after the due date."})
        max_attempts = attrs.get("max_attempts")
        if max_attempts is not None and not 1 <= max_attempts <= 3:
            raise serializers.ValidationError({"max_attempts": "Allow 1 to 3 attempts."})
        course = self.context["course"]
        for chapter in attrs.get("chapters", []):
            if chapter.course_id != course.id:
                raise serializers.ValidationError(
                    {"chapter_ids": "Chapters must be in this course."}
                )
        return attrs

    def _save_questions(self, assessment, questions):
        if questions is None:
            return
        assessment.questions.all().delete()
        QuizQuestion.objects.bulk_create(
            QuizQuestion(assessment=assessment, **{k: v for k, v in q.items() if k != "id"})
            for q in questions
        )

    def create(self, validated):
        questions = validated.pop("questions", None)
        chapters = validated.pop("chapters", [])
        assessment = Assessment.objects.create(course=self.context["course"], **validated)
        assessment.chapters.set(chapters)
        self._save_questions(assessment, questions)
        return assessment

    def update(self, instance, validated):
        questions = validated.pop("questions", None)
        chapters = validated.pop("chapters", None)
        for key, value in validated.items():
            setattr(instance, key, value)
        instance.save()
        if chapters is not None:
            instance.chapters.set(chapters)
        self._save_questions(instance, questions)
        return instance


class DiscussionPostSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionPost
        fields = ["id", "parent", "body", "author_name", "is_mine", "created_at"]
        read_only_fields = ["author_name", "is_mine", "created_at"]

    def get_author_name(self, obj) -> str:
        return f"{obj.author.first_name} {obj.author.last_name[:1]}".strip()

    def get_is_mine(self, obj) -> bool:
        return obj.author_id == self.context["request"].user.id


class DiscussionProgressSerializer(serializers.Serializer):
    original_posted = serializers.BooleanField()
    replies_made = serializers.IntegerField()
    replies_required = serializers.IntegerField()


class DiscussionSerializer(serializers.Serializer):
    posts = DiscussionPostSerializer(many=True)
    progress = DiscussionProgressSerializer(allow_null=True)


class PostCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000)
    parent = serializers.IntegerField(required=False, allow_null=True)


class SubmissionCreateSerializer(serializers.Serializer):
    text = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    file = serializers.FileField(required=False)


class QuestionResultSerializer(serializers.Serializer):
    question = serializers.IntegerField()
    correct_index = serializers.IntegerField()


class QuizAttemptSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    results = serializers.SerializerMethodField()

    class Meta:
        model = QuizAttempt
        fields = [
            "id", "assessment", "attempt_no", "started_at", "deadline_at", "submitted_at",
            "answers", "score", "auto_submitted", "questions", "results",
        ]  # fmt: skip
        read_only_fields = fields

    @extend_schema_field(QuestionPublicSerializer(many=True))
    def get_questions(self, obj):
        return QuestionPublicSerializer(obj.assessment.questions.all(), many=True).data

    @extend_schema_field(QuestionResultSerializer(many=True, allow_null=True))
    def get_results(self, obj):
        if obj.submitted_at is None:
            return None
        return [
            {"question": q.id, "correct_index": q.correct_index}
            for q in obj.assessment.questions.all()
        ]


class AnswersSerializer(serializers.Serializer):
    answers = serializers.DictField(child=serializers.IntegerField(min_value=0))


class OverrideSerializer(serializers.ModelSerializer):
    student = serializers.IntegerField(source="student_id")

    class Meta:
        model = DueDateOverride
        fields = ["id", "student", "due_at", "cutoff_at", "reason"]


class ExcuseSerializer(serializers.Serializer):
    student = serializers.IntegerField()
    excused = serializers.BooleanField()


class RosterRowSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    status = serializers.CharField()
    effective_due_at = serializers.DateTimeField()
    extended = serializers.BooleanField()
    submission_id = serializers.IntegerField(allow_null=True)
    submitted_at = serializers.DateTimeField(allow_null=True)
    score = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)
    has_file = serializers.BooleanField()


class ScoreSerializer(serializers.Serializer):
    score = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)


class ChapterRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order = serializers.IntegerField()
    title = serializers.CharField()


class SyllabusWeekSerializer(serializers.ModelSerializer):
    chapters = serializers.SerializerMethodField()

    class Meta:
        model = SyllabusWeek
        fields = ["week_number", "start_date", "topic", "chapters"]
        read_only_fields = fields

    @extend_schema_field(ChapterRefSerializer(many=True))
    def get_chapters(self, obj):
        return [{"id": c.id, "order": c.order, "title": c.title} for c in obj.chapters.all()]


class GradingItemSerializer(serializers.Serializer):
    label = serializers.CharField()
    weight_pct = serializers.FloatField()


class PoliciesSerializer(serializers.Serializer):
    late_work = serializers.CharField()
    academic_integrity = serializers.CharField()


class SyllabusSerializer(serializers.ModelSerializer):
    weeks = SyllabusWeekSerializer(many=True)
    grading = GradingItemSerializer(many=True)
    policies = PoliciesSerializer()
    instructor_name = serializers.SerializerMethodField()
    instructor_email = serializers.EmailField(source="course.instructor.email")
    course_code = serializers.CharField(source="course.code")
    course_title = serializers.CharField(source="course.title")
    meetings = MeetingSerializer(source="course.meetings", many=True)

    class Meta:
        model = Syllabus
        fields = [
            "course_code", "course_title", "description", "instructor_name", "instructor_email",
            "meetings", "office_hours", "grading", "policies", "weeks",
        ]  # fmt: skip
        read_only_fields = fields

    def get_instructor_name(self, obj) -> str:
        i = obj.course.instructor
        return f"{i.first_name} {i.last_name}".strip()
