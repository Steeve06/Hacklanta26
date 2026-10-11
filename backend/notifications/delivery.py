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
    "new_content": "New in your course",
}


def push_configured() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


# How long a push service keeps a reminder for a phone that's asleep or offline.
PUSH_TTL_SECONDS = 12 * 60 * 60
URGENT_TIER = 4


def push_payload(n: Notification) -> str:
    """What the lock screen sees: the reminder text and a link, never grades or scores."""
    return json.dumps(
        {
            "id": n.id,
            "title": f"Leon · {TITLES.get(n.trigger, 'Reminder')}",
            "body": n.text,
            "url": n.link or "/pulse/inbox",
            "urgent": n.tier >= URGENT_TIER,
            "actions": [{"action": "open", "title": "Open"}]
            if n.trigger == "new_content"
            else [
                {"action": "open", "title": "Open"},
                {"action": "snooze", "title": "Snooze 1 h"},
                {"action": "tone_down", "title": "Tone it down"},
            ],
        }
    )


def send_to_devices(user, payload: str, *, urgent: bool = False) -> int:
    """Send one push to each of the user's subscribed devices. Returns how many accepted it.
    Expired subscriptions (404/410) are removed."""
    from pywebpush import WebPushException, webpush

    delivered = 0
    for sub in PushSubscription.objects.filter(user=user):
        try:
            webpush(
                subscription_info={"endpoint": sub.endpoint, "keys": sub.keys},
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_SUBJECT},
                ttl=PUSH_TTL_SECONDS,
                headers={"Urgency": "high" if urgent else "normal"},
                timeout=10,
            )
            delivered += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                sub.delete()
            else:
                logger.warning("Push to user %s failed (status %s)", user.id, status)
    return delivered


def _send_push(n: Notification) -> bool:
    return send_to_devices(n.student, push_payload(n), urgent=n.tier >= URGENT_TIER) > 0


def _send_email(n: Notification) -> None:
    footer = ""
    if n.student.profile.supportive_mode:
        footer = (
            f"\n\nIf things are hard right now, support is available: {settings.CAMPUS_SUPPORT_URL}"
        )
    send_mail(
        subject=f"Leon: {TITLES.get(n.trigger, 'Reminder')}",
        message=f"{n.text}\n\nOpen Leon: {settings.FRONTEND_URL}{n.link or '/pulse'}{footer}",
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
