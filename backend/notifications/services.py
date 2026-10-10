"""Student actions on notifications."""

from datetime import timedelta

from django.db.models import Q

from accounts.clock import now as clock_now
from accounts.models import StudentProfile

from .engine import SUPPORTIVE_TONE_DOWNS
from .models import Notification

SNOOZE = timedelta(hours=1)


def inbox(student):
    now = clock_now(student)
    return Notification.objects.filter(
        Q(snoozed_until__isnull=True) | Q(snoozed_until__lte=now),
        student=student,
        sent_at__isnull=False,
        cancelled_at__isnull=True,
    ).order_by("-sent_at", "-id")


def take_action(student, notification: Notification, action: str) -> StudentProfile:
    profile, _ = StudentProfile.objects.get_or_create(user=student)
    now = clock_now(student)
    notification.action_taken = action
    notification.read_at = notification.read_at or now
    if action == Notification.Action.SNOOZE:
        notification.snoozed_until = now + SNOOZE
        notification.scheduled_for = now + SNOOZE
        notification.sent_at = None
    notification.save()
    if action == Notification.Action.TONE_DOWN:
        profile.sass_level = max(1, profile.sass_level - 1)
        profile.tone_down_streak += 1
        if profile.tone_down_streak >= SUPPORTIVE_TONE_DOWNS:
            profile.supportive_mode = True
    else:
        profile.tone_down_streak = 0
    profile.save(update_fields=["sass_level", "tone_down_streak", "supportive_mode", "updated_at"])
    return profile
