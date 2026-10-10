import hashlib

from django.conf import settings
from django.db import models

from config.models import TimeStamped

User = settings.AUTH_USER_MODEL


class Term(TimeStamped):
    name = models.CharField(max_length=80)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self) -> str:
        return self.name


class Course(TimeStamped):
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="courses")
    code = models.CharField(max_length=20)
    title = models.CharField(max_length=120)
    instructor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="teaching")
    color = models.CharField(max_length=7, default="#1f6f5c")

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["term", "code"], name="uniq_course_code")]

    def __str__(self) -> str:
        return self.code


class Enrollment(TimeStamped):
    class Role(models.TextChoices):
        STUDENT = "student"
        INSTRUCTOR = "instructor"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "course"], name="uniq_enrollment")]


class Syllabus(TimeStamped):
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name="syllabus")
    description = models.TextField()
    office_hours = models.CharField(max_length=200)
    grading = models.JSONField(default=list, help_text="[{label, weight_pct}] summing to 100")
    policies = models.JSONField(default=dict, help_text="{late_work, academic_integrity}")


class Chapter(TimeStamped):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="chapters")
    order = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=160)
    body_md = models.TextField()
    links = models.JSONField(default=list, blank=True, help_text="[{label, url}]")
    reading_minutes = models.PositiveSmallIntegerField(default=10)
    objectives = models.JSONField(default=list)
    available_from = models.DateTimeField()
    content_hash = models.CharField(max_length=64, editable=False, db_index=True)

    class Meta:
        ordering = ["course", "order"]
        constraints = [
            models.UniqueConstraint(fields=["course", "order"], name="uniq_chapter_order")
        ]

    def __str__(self) -> str:
        return f"{self.course.code} Ch {self.order}: {self.title}"

    def compute_hash(self) -> str:
        source = "\n".join([self.title, self.body_md, "|".join(self.objectives)])
        return hashlib.sha256(source.encode()).hexdigest()

    def save(self, *args, **kwargs):
        self.content_hash = self.compute_hash()
        super().save(*args, **kwargs)


class SyllabusWeek(TimeStamped):
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE, related_name="weeks")
    week_number = models.PositiveSmallIntegerField()
    start_date = models.DateField()
    topic = models.CharField(max_length=160)
    chapters = models.ManyToManyField(Chapter, blank=True, related_name="syllabus_weeks")

    class Meta:
        ordering = ["week_number"]
        constraints = [
            models.UniqueConstraint(fields=["syllabus", "week_number"], name="uniq_syllabus_week")
        ]


class ChapterProgress(TimeStamped):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chapter_progress")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="progress")
    first_opened_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "chapter"], name="uniq_chapter_progress")
        ]


class Assessment(TimeStamped):
    class Type(models.TextChoices):
        QUIZ = "quiz"
        HOMEWORK = "homework"
        DISCUSSION = "discussion"

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assessments")
    type = models.CharField(max_length=20, choices=Type.choices)
    title = models.CharField(max_length=160)
    instructions = models.TextField()
    chapters = models.ManyToManyField(Chapter, blank=True, related_name="assessments")
    open_at = models.DateTimeField()
    due_at = models.DateTimeField(db_index=True)
    cutoff_at = models.DateTimeField(null=True, blank=True)
    points = models.PositiveSmallIntegerField(default=10)
    weight_pct = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    est_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    discussion_replies_required = models.PositiveSmallIntegerField(default=2)
    time_limit_minutes = models.PositiveSmallIntegerField(default=20)
    max_attempts = models.PositiveSmallIntegerField(default=1)
    published = models.BooleanField(default=True)

    class Meta:
        ordering = ["due_at", "id"]

    def __str__(self) -> str:
        return f"{self.course.code} {self.title}"


class DueDateOverride(TimeStamped):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="overrides")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="due_overrides")
    due_at = models.DateTimeField()
    cutoff_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["assessment", "student"], name="uniq_override")
        ]


class Submission(TimeStamped):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started"
        IN_PROGRESS = "in_progress"
        SUBMITTED = "submitted"
        LATE = "late"
        MISSED = "missed"
        EXCUSED = "excused"
        GRADED = "graded"

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="submissions")
    status = models.CharField(max_length=20, choices=Status.choices)
    text = models.TextField(blank=True)
    file = models.FileField(upload_to="submissions/%Y/%m/", blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    attempt_no = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["-attempt_no", "-id"]
        indexes = [models.Index(fields=["student", "assessment"])]


class DiscussionPost(TimeStamped):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="discussion_posts")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at", "id"]


class QuizQuestion(TimeStamped):
    class Type(models.TextChoices):
        MULTIPLE_CHOICE = "multiple_choice"
        TRUE_FALSE = "true_false"

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveSmallIntegerField()
    type = models.CharField(max_length=20, choices=Type.choices)
    prompt = models.TextField()
    options = models.JSONField()
    correct_index = models.PositiveSmallIntegerField()
    points = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["order"]


class QuizAttempt(TimeStamped):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quiz_attempts")
    attempt_no = models.PositiveSmallIntegerField()
    started_at = models.DateTimeField()
    deadline_at = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    answers = models.JSONField(default=dict)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    auto_submitted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "student", "attempt_no"], name="uniq_quiz_attempt"
            )
        ]
