from datetime import time, timedelta

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from config.models import TimeStamped

User = settings.AUTH_USER_MODEL
HALF_HOUR = timedelta(minutes=30)


class AvailabilityBlock(TimeStamped):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="availability")
    weekday = models.PositiveSmallIntegerField(help_text="0 = Monday")
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(weekday__gte=0, weekday__lte=6), name="availability_weekday"
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")) | Q(end_time=time(0)),
                name="availability_end_after_start",
            ),
            # At least 30 minutes; an end of 00:00 means midnight at the end of the day.
            models.CheckConstraint(
                condition=(
                    Q(start_time__lt=time(23, 30), end_time__gte=F("start_time") + HALF_HOUR)
                    | Q(end_time=time(0), start_time__lte=time(23, 30))
                ),
                name="availability_min_30_minutes",
            ),
        ]


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


class StatusSnapshot(TimeStamped):
    class State(models.TextChoices):
        GOOD = "good"
        MEDIUM = "medium"
        BAD = "bad"

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="status_snapshots")
    course_id = models.IntegerField(null=True, blank=True, help_text="null = overall")
    score = models.PositiveSmallIntegerField()
    state = models.CharField(max_length=10, choices=State.choices)
    reasons = models.JSONField(default=list)
    components = models.JSONField(default=dict)
    computed_at = models.DateTimeField()

    class Meta:
        ordering = ["-computed_at", "-id"]
        indexes = [models.Index(fields=["student", "course_id", "computed_at"])]


class Onboarding(TimeStamped):
    """Where a student is in the first-run wizard. The answers themselves live in their real
    tables (profile, availability, blackouts); this only remembers progress."""

    STEPS = 5

    student = models.OneToOneField(User, on_delete=models.CASCADE, related_name="onboarding")
    current_step = models.PositiveSmallIntegerField(default=1)
    completed_steps = models.JSONField(default=list)
    inputs_changed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(current_step__gte=1, current_step__lte=5),
                name="onboarding_step_1_to_5",
            )
        ]

    def __str__(self) -> str:
        return f"Onboarding<{self.student_id}:{self.current_step}>"
