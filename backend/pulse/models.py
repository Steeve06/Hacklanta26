from django.conf import settings
from django.db import models
from django.db.models import Q

from config.models import TimeStamped

User = settings.AUTH_USER_MODEL


class AvailabilityBlock(TimeStamped):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="availability")
    weekday = models.PositiveSmallIntegerField(help_text="0 = Monday")
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["weekday", "start_time"]


class Blackout(TimeStamped):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blackouts")
    start = models.DateTimeField()
    end = models.DateTimeField()
    label = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["start"]


class StudyTask(TimeStamped):
    class Source(models.TextChoices):
        CHAPTER = "chapter"
        ASSESSMENT = "assessment"

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="study_tasks")
    course_id = models.IntegerField()
    source_type = models.CharField(max_length=20, choices=Source.choices)
    source_id = models.IntegerField()
    key = models.CharField(max_length=80, help_text="stable id within the source, e.g. 'draft'")
    title = models.CharField(max_length=200)
    est_minutes = models.PositiveIntegerField()
    min_chunk_minutes = models.PositiveIntegerField(default=25)
    splittable = models.BooleanField(default=True)
    depends_on = models.ManyToManyField("self", symmetrical=False, blank=True)
    ai_generated = models.BooleanField(default=False)
    cache_key = models.CharField(max_length=64, db_index=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "source_type", "source_id", "key"], name="uniq_study_task"
            )
        ]
        indexes = [models.Index(fields=["student", "active"])]


class Schedule(TimeStamped):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="schedules")
    version = models.PositiveIntegerField()
    is_active = models.BooleanField(default=False)
    generated_at = models.DateTimeField()
    horizon_end = models.DateTimeField()
    summary = models.TextField(blank=True)
    overload_report = models.JSONField(null=True, blank=True)
    solver_meta = models.JSONField(default=dict)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(fields=["student", "version"], name="uniq_schedule_version"),
            models.UniqueConstraint(
                fields=["student"], condition=Q(is_active=True), name="one_active_schedule"
            ),
        ]


class Session(TimeStamped):
    class Kind(models.TextChoices):
        STUDY = "study"
        ASSIGNMENT = "assignment"
        DISCUSSION = "discussion"
        QUIZ = "quiz"
        CHAPTER_QUIZ = "chapter_quiz"

    class Status(models.TextChoices):
        PLANNED = "planned"
        DONE = "done"
        PARTIAL = "partial"
        SKIPPED = "skipped"
        RESCHEDULED = "rescheduled"

    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name="sessions")
    task = models.ForeignKey(StudyTask, on_delete=models.CASCADE, related_name="sessions")
    start = models.DateTimeField(db_index=True)
    end = models.DateTimeField()
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    completed_minutes = models.PositiveIntegerField(default=0)
    at_risk = models.BooleanField(default=False)

    class Meta:
        ordering = ["start"]
        indexes = [models.Index(fields=["schedule", "start"])]

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


class PlanJob(TimeStamped):
    class Kind(models.TextChoices):
        GENERATE = "generate"
        REPLAN = "replan"

    class State(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        DONE = "done"
        FAILED = "failed"
        CANCELLED = "cancelled"

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="plan_jobs")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    state = models.CharField(max_length=20, choices=State.choices, default=State.QUEUED)
    progress = models.PositiveSmallIntegerField(default=0)
    stage = models.CharField(max_length=40, default="queued")
    reason = models.CharField(max_length=60, blank=True)
    feedback = models.CharField(max_length=300, blank=True)
    error = models.TextField(blank=True)
    schedule = models.ForeignKey(Schedule, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(state__in=["queued", "running"]),
                name="one_open_plan_job",
            )
        ]
