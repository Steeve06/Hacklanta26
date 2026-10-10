from django.conf import settings
from django.db import models

from config.models import TimeStamped

User = settings.AUTH_USER_MODEL


class CheckQuestion(TimeStamped):
    """One question in a chapter's bank. Multiple choice and true/false are written by the model
    from the chapter text (and checked against it), or built from the chapter's key terms when the
    model isn't available. Short answers ("type the missing term") always come from the key terms;
    they also make up matching cards."""

    class Type(models.TextChoices):
        MULTIPLE_CHOICE = "multiple_choice"
        TRUE_FALSE = "true_false"
        SHORT_ANSWER = "short_answer"

    class Origin(models.TextChoices):
        AI = "ai"
        CLOZE = "cloze"
        TERM = "term"

    chapter = models.ForeignKey("lms.Chapter", on_delete=models.CASCADE, related_name="bank")
    type = models.CharField(max_length=20, choices=Type.choices)
    prompt = models.TextField()
    options = models.JSONField(default=list)
    correct_index = models.PositiveSmallIntegerField(default=0)
    answer = models.CharField(
        max_length=120, blank=True, help_text="the key term, for short answers"
    )
    explanation = models.TextField()
    source_excerpt = models.TextField()
    content_hash = models.CharField(max_length=64, db_index=True, help_text="chapter version")
    origin = models.CharField(max_length=10, choices=Origin.choices)
    retired = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["chapter", "retired"])]


class StudyCheck(TimeStamped):
    """Four flashcards on the chapters a student studied on one day. It opens on the day the
    schedule gives the chapter (or when the student finishes it early) and closes at the end of
    the next day. Passing it inside that window extends the streak."""

    class Kind(models.TextChoices):
        SCHEDULED = "scheduled"
        EARLY = "early"

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="study_checks")
    chapters = models.ManyToManyField("lms.Chapter", related_name="study_checks")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SCHEDULED)
    scheduled_date = models.DateField()
    opens_at = models.DateTimeField(db_index=True)
    closes_at = models.DateTimeField(db_index=True)
    timezone = models.CharField(max_length=64, help_text="the student's zone when it was made")
    passed = models.BooleanField(default=False)
    counted_for_streak = models.BooleanField(default=False)
    resolved = models.BooleanField(default=False, help_text="streak outcome recorded")

    class Meta:
        ordering = ["opens_at"]
        indexes = [models.Index(fields=["student", "closes_at"])]


class CheckAttempt(TimeStamped):
    """One timed go at a check: four cards, picked from the chapters' banks when it starts. Each
    card is {kind: choice, question_id, order}, {kind: short, question_id} or
    {kind: match, question_ids, clues} (clues are the same ids in the order shown)."""

    study_check = models.ForeignKey(StudyCheck, on_delete=models.CASCADE, related_name="attempts")
    number = models.PositiveSmallIntegerField()
    cards = models.JSONField(default=list)
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True, help_text="when the clock runs out")
    last_answer_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    correct = models.PositiveSmallIntegerField(default=0)
    xp = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["study_check", "number"], name="uniq_check_attempt"),
            models.CheckConstraint(
                condition=models.Q(number__gte=1, number__lte=2), name="check_attempt_1_or_2"
            ),
        ]


class CheckAnswer(TimeStamped):
    attempt = models.ForeignKey(CheckAttempt, on_delete=models.CASCADE, related_name="answers")
    position = models.PositiveSmallIntegerField()
    question = models.ForeignKey(
        CheckQuestion, on_delete=models.CASCADE, related_name="answers",
        help_text="for a matching card, its first question",
    )  # fmt: skip
    chosen_index = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="index in the original options (choice cards)"
    )
    response = models.JSONField(default=dict, help_text="typed text or matched pairs")
    correct = models.BooleanField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["attempt", "position"], name="uniq_check_answer")
        ]


class Streak(TimeStamped):
    """Checks passed in a row. Days without a check don't count either way."""

    student = models.OneToOneField(User, on_delete=models.CASCADE, related_name="streak")
    current = models.PositiveIntegerField(default=0)
    longest = models.PositiveIntegerField(default=0)
    freezes = models.PositiveSmallIntegerField(default=0)
    on_time_toward_freeze = models.PositiveSmallIntegerField(default=0)


class StreakEvent(TimeStamped):
    class Result(models.TextChoices):
        ON_TIME = "on_time"
        FROZEN = "frozen"
        MISSED = "missed"

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="streak_events")
    study_check = models.OneToOneField(
        StudyCheck, null=True, blank=True, on_delete=models.SET_NULL, related_name="event"
    )
    assessment = models.ForeignKey(
        "lms.Assessment", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="streak_events", help_text="a deadline that passed without a submission",
    )  # fmt: skip
    day = models.DateField(null=True, blank=True)
    result = models.CharField(max_length=10, choices=Result.choices)
    streak_after = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "assessment"],
                condition=models.Q(assessment__isnull=False),
                name="one_streak_event_per_missed_deadline",
            )
        ]
