import logging

from celery import shared_task

from accounts.models import User

from .models import Streak, StreakEvent

logger = logging.getLogger(__name__)


@shared_task
def sweep_streaks() -> int:
    """Every 10 minutes: settle days that ended without a finished deck (freeze or reset)."""
    from notifications.engine import notify_streak_lost

    from .services.streaks import settle

    student_ids = Streak.objects.filter(current__gt=0).values_list("student_id", flat=True)
    settled = 0
    for student in User.objects.filter(pk__in=list(student_ids)).select_related("profile"):
        for event in settle(student):
            settled += 1
            if event.result == StreakEvent.Result.MISSED:
                notify_streak_lost(student, event)
    return settled
