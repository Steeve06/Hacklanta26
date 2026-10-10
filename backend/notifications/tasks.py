import logging

from celery import shared_task

from accounts.models import User

from .engine import dispatch_due, scan_student

logger = logging.getLogger(__name__)
BATCH = 200


@shared_task
def scan_all() -> int:
    """Every 10 minutes: evaluate triggers for every onboarded student, then send what's due."""
    created = 0
    ids = list(
        User.objects.filter(role=User.Role.STUDENT, profile__onboarding_done=True, is_active=True)
        .order_by("id")
        .values_list("id", flat=True)
    )
    for start in range(0, len(ids), BATCH):
        for student in User.objects.filter(id__in=ids[start : start + BATCH]).select_related(
            "profile"
        ):
            try:
                created += len(scan_student(student))
            except Exception:
                logger.exception("Notification scan failed for student %s", student.id)
    dispatch_due()
    return created


@shared_task
def dispatch() -> int:
    return dispatch_due()
