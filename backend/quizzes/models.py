from django.conf import settings
from django.db import models

from config.models import TimeStamped

User = settings.AUTH_USER_MODEL


class Flashcard(TimeStamped):
    """A flashcard. Course cards are built from a chapter's text; general cards (no chapter) come
    from the built-in library and fill decks when a student has no course material yet."""

    class Topic(models.TextChoices):
        STUDY_SKILLS = "study_skills", "Study skills"
        MEMORY = "memory", "Memory"
        FOCUS = "focus", "Focus"
        WELLBEING = "wellbeing", "Well-being"
        MONEY = "money", "Money"
        DIGITAL = "digital", "Digital life"
        SCIENCE = "science", "Science"
        WORLD = "world", "World"
        COURSE = "course", "Course"

    chapter = models.ForeignKey(
        "lms.Chapter", null=True, blank=True, on_delete=models.CASCADE, related_name="flashcards"
    )
    content_hash = models.CharField(max_length=64, blank=True, help_text="chapter version")
    slug = models.SlugField(max_length=80, unique=True)
    topic = models.CharField(max_length=20, choices=Topic.choices)
    front = models.CharField(max_length=300)
    back = models.TextField()
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["chapter", "active"])]


class DailyDeck(TimeStamped):
    """One short deck per student per local day. Finishing it counts that day toward the streak."""

    class Kind(models.TextChoices):
        UPCOMING = "upcoming", "Prep for an upcoming deadline"
        REVIEW = "review", "Review of course chapters"
        GENERAL = "general", "General study cards"

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="daily_decks")
    day = models.DateField()
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.GENERAL)
    course = models.ForeignKey(
        "lms.Course", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    assessment = models.ForeignKey(
        "lms.Assessment", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cards = models.JSONField(default=list, help_text="flashcard ids in the order shown")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    knew = models.PositiveSmallIntegerField(default=0)
    counted_for_streak = models.BooleanField(default=False)

    class Meta:
        ordering = ["-day"]
        constraints = [models.UniqueConstraint(fields=["student", "day"], name="uniq_daily_deck")]


class CardReview(TimeStamped):
    deck = models.ForeignKey(DailyDeck, on_delete=models.CASCADE, related_name="reviews")
    card = models.ForeignKey(Flashcard, on_delete=models.CASCADE, related_name="reviews")
    knew = models.BooleanField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["deck", "card"], name="uniq_card_review")]


class Streak(TimeStamped):
    student = models.OneToOneField(User, on_delete=models.CASCADE, related_name="streak")
    current = models.PositiveIntegerField(default=0)
    longest = models.PositiveIntegerField(default=0)
    freezes = models.PositiveSmallIntegerField(default=0)
    on_time_toward_freeze = models.PositiveSmallIntegerField(default=0)
    last_day = models.DateField(
        null=True, blank=True, help_text="last local day the streak covered (done or frozen)"
    )


class StreakEvent(TimeStamped):
    class Result(models.TextChoices):
        ON_TIME = "on_time"
        FROZEN = "frozen"
        MISSED = "missed"

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="streak_events")
    deck = models.OneToOneField(DailyDeck, null=True, blank=True, on_delete=models.SET_NULL)
    day = models.DateField(null=True, blank=True)
    result = models.CharField(max_length=10, choices=Result.choices)
    streak_after = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at", "-id"]
