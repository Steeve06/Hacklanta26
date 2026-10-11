from django.conf import settings
from django.db import models

from config.models import TimeStamped

User = settings.AUTH_USER_MODEL


class Trigger(models.TextChoices):
    SESSION_STARTING = "session_starting"
    SESSION_IGNORED = "session_ignored"
    UPCOMING_DUE = "upcoming_due"
    FALLING_BEHIND = "falling_behind"
    FINAL_STRETCH = "final_stretch"
    CODE_RED = "code_red"
    MISSED_LATE = "missed_late"
    STREAK_AT_RISK = "streak_at_risk"
    STREAK_LOST = "streak_lost"
    WIN = "win"
    DIGEST = "digest"
    NEW_CONTENT = "new_content"


WIN_TIER = 0


class NotificationTemplate(TimeStamped):
    trigger = models.CharField(max_length=30, choices=Trigger.choices)
    tier = models.PositiveSmallIntegerField()
    sass_level = models.PositiveSmallIntegerField(help_text="0 = supportive mode copy")
    text = models.CharField(max_length=300)
    variables = models.JSONField(default=list)
    active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["trigger", "sass_level", "active"])]


class Notification(TimeStamped):
    class Action(models.TextChoices):
        OPEN = "open"
        SNOOZE = "snooze"
        TONE_DOWN = "tone_down"

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    trigger = models.CharField(max_length=30, choices=Trigger.choices)
    tier = models.PositiveSmallIntegerField()
    sass_level = models.PositiveSmallIntegerField(default=3)
    template = models.ForeignKey(
        NotificationTemplate, null=True, blank=True, on_delete=models.SET_NULL
    )
    source_type = models.CharField(max_length=20, blank=True)
    source_id = models.IntegerField(null=True, blank=True)
    course_id = models.IntegerField(null=True, blank=True)
    text = models.CharField(max_length=400)
    link = models.CharField(max_length=200, blank=True)
    channels = models.JSONField(default=list)
    scheduled_for = models.DateTimeField(db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    snoozed_until = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=80, blank=True)
    dedupe_key = models.CharField(max_length=160, unique=True)
    action_taken = models.CharField(max_length=20, choices=Action.choices, blank=True)

    class Meta:
        ordering = ["-scheduled_for", "-id"]
        indexes = [models.Index(fields=["student", "scheduled_for"])]


class PushSubscription(TimeStamped):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(max_length=600, unique=True)
    keys = models.JSONField()
