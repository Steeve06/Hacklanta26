import logging

from celery import shared_task
from django.conf import settings

from accounts.models import User

from .engine import dispatch_due, scan_student

logger = logging.getLogger(__name__)
BATCH = 200


@shared_task
def scan_all() -> int:
    """Every 10 minutes: evaluate triggers for every onboarded student in batches of 200.

    With a worker the batches run as parallel tasks; without one they run inline.
    """
    ids = list(
        User.objects.filter(role=User.Role.STUDENT, profile__onboarding_done=True, is_active=True)
        .order_by("id")
        .values_list("id", flat=True)
    )
    batches = [ids[start : start + BATCH] for start in range(0, len(ids), BATCH)]
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return sum(scan_batch(batch) for batch in batches)
    for batch in batches:
        scan_batch.delay(batch)
    return 0


@shared_task
def scan_batch(student_ids: list[int]) -> int:
    created = 0
    for student in User.objects.filter(id__in=student_ids).select_related("profile"):
        try:
            created += len(scan_student(student))
            dispatch_due(student=student)
        except Exception:
            logger.exception("Notification scan failed for student %s", student.id)
    return created
