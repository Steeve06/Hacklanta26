"""Channels: in-app (the row itself), Web Push and email."""

import json
import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import Notification, PushSubscription

logger = logging.getLogger(__name__)

TITLES = {
    "session_starting": "Session starting",
    "session_ignored": "How did it go?",
    "upcoming_due": "Coming up",
    "falling_behind": "Falling behind",
    "final_stretch": "Due tomorrow",
    "code_red": "Due very soon",
    "missed_late": "Past due",
    "streak_at_risk": "Streak at risk",
    "streak_lost": "Streak reset",
    "win": "Nice work",
    "digest": "While you were away",
}


def push_configured() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def push_payload(n: Notification) -> str:
    """What the lock screen sees: the reminder text and a link, never grades or scores."""
    return json.dumps(
        {
            "id": n.id,
            "title": f"Pulse · {TITLES.get(n.trigger, 'Reminder')}",
            "body": n.text,
            "url": n.link or "/pulse/inbox",
            "actions": [
                {"action": "open", "title": "Open"},
                {"action": "snooze", "title": "Snooze 1 h"},
                {"action": "tone_down", "title": "Tone it down"},
            ],
        }
    )


def _send_push(n: Notification) -> bool:
    from pywebpush import WebPushException, webpush

    delivered = False
    for sub in PushSubscription.objects.filter(user=n.student):
        try:
            webpush(
                subscription_info={"endpoint": sub.endpoint, "keys": sub.keys},
                data=push_payload(n),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_SUBJECT},
                timeout=10,
            )
            delivered = True
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                sub.delete()
            else:
                logger.warning("Push failed for notification %s (status %s)", n.id, status)
    return delivered


def _send_email(n: Notification) -> None:
    footer = ""
    if n.student.profile.supportive_mode:
        footer = (
            f"\n\nIf things are hard right now, support is available: {settings.CAMPUS_SUPPORT_URL}"
        )
    send_mail(
        subject=f"Pulse: {TITLES.get(n.trigger, 'Reminder')}",
        message=f"{n.text}\n\nOpen Pulse: {settings.FRONTEND_URL}{n.link or '/pulse'}{footer}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[n.student.email],
        fail_silently=True,
    )


def deliver(n: Notification) -> None:
    channels = list(n.channels)
    if "push" in channels and not _send_push(n):
        channels.remove("push")
        if "email" not in channels:
            channels.append("email")
    if "email" in channels:
        _send_email(n)
    n.channels = channels
