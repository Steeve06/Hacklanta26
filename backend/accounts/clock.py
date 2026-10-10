"""Server-authoritative time, with a per-student offset used only by demo time-travel."""

from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone


def now(user=None) -> datetime:
    current = timezone.now()
    if not settings.DEMO_MODE or user is None:
        return current
    profile = getattr(user, "profile", None)
    if profile is None or not profile.clock_offset_minutes:
        return current
    return current + timedelta(minutes=profile.clock_offset_minutes)


def local_now(user) -> datetime:
    return now(user).astimezone(user.tz)
