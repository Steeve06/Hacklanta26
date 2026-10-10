from django.conf import settings
from django.db import models

from config.models import TimeStamped

User = settings.AUTH_USER_MODEL


class BankQuestion(TimeStamped):
    class Type(models.TextChoices):
        MULTIPLE_CHOICE = "multiple_choice"
        TRUE_FALSE = "true_false"

    class Origin(models.TextChoices):
        AI = "ai"
        CLOZE = "cloze"

    chapter = models.ForeignKey("lms.Chapter", on_delete=models.CASCADE, related_name="bank")
    type = models.CharField(max_length=20, choices=Type.choices)
    prompt = models.TextField()
    options = models.JSONField()
    correct_index = models.PositiveSmallIntegerField()
    explanation = models.TextField()
    source_excerpt = models.TextField()
    content_hash = models.CharField(max_length=64, db_index=True)
    origin = models.CharField(max_length=10, choices=Origin.choices)
    retired = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["chapter", "retired"])]


class ChapterQuiz(TimeStamped):
    class Kind(models.TextChoices):
        SCHEDULED = "scheduled"
        EARLY = "early"

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chapter_quizzes")
    chapters = models.ManyToManyField("lms.Chapter", related_name="chapter_quizzes")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SCHEDULED)
    scheduled_date = models.DateField()
    opens_at = models.DateTimeField(db_index=True)
    closes_at = models.DateTimeField(db_index=True)
    timezone = models.CharField(max_length=64)
    questions = models.JSONField(default=list, help_text="[{bank_id, order: [option indexes]}]")
    started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    counted_for_streak = models.BooleanField(default=False)
    sharp = models.BooleanField(default=False)
    resolved = models.BooleanField(default=False, help_text="streak outcome recorded")

    class Meta:
        ordering = ["opens_at"]
        indexes = [models.Index(fields=["student", "closes_at"])]


class ChapterQuizAnswer(TimeStamped):
    quiz = models.ForeignKey(ChapterQuiz, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(BankQuestion, on_delete=models.CASCADE, related_name="answers")
    chosen_index = models.PositiveSmallIntegerField(help_text="index in the original options")
    correct = models.BooleanField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["quiz", "question"], name="uniq_quiz_answer")
        ]


class Streak(TimeStamped):
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
    quiz = models.OneToOneField(ChapterQuiz, null=True, blank=True, on_delete=models.SET_NULL)
    result = models.CharField(max_length=10, choices=Result.choices)
    streak_after = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at", "-id"]
