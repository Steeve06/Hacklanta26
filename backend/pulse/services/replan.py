"""When and how plans are (re)built: jobs, locking and debouncing."""

import logging

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction

from ..models import AvailabilityBlock, PlanJob

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 60
WORKER_DELAY_SECONDS = 5
LOCK_SECONDS = 120


def _pending_key(student_id: int) -> str:
    return f"replan:pending:{student_id}"


def _lock_key(student_id: int) -> str:
    return f"plan:lock:{student_id}"


def can_plan(student) -> bool:
    profile = getattr(student, "profile", None)
    return bool(
        student.is_student
        and profile is not None
        and profile.onboarding_done
        and AvailabilityBlock.objects.filter(student=student).exists()
    )


def request_replan(student, reason: str) -> None:
    """Coalesce automatic triggers: one pending re-plan per student, picked up by the worker."""
    if not can_plan(student):
        return
    if not cache.add(_pending_key(student.id), reason, DEBOUNCE_SECONDS):
        return
    from ..tasks import replan_student

    countdown = 0 if settings.CELERY_TASK_ALWAYS_EAGER else WORKER_DELAY_SECONDS
    transaction.on_commit(
        lambda: replan_student.apply_async(args=[student.id, reason], countdown=countdown)
    )


def start_generate_job(student, feedback: str = "") -> PlanJob:
    """One open generate job per student; a second request returns the running one."""
    open_job = PlanJob.objects.filter(student=student, state__in=["queued", "running"]).first()
    if open_job:
        return open_job
    try:
        with transaction.atomic():
            job = PlanJob.objects.create(
                student=student, kind=PlanJob.Kind.GENERATE, reason="generate", feedback=feedback
            )
    except IntegrityError:
        return PlanJob.objects.get(student=student, state__in=["queued", "running"])
    from ..tasks import run_plan_job

    transaction.on_commit(lambda: run_plan_job.delay(job.id))
    return job


def acquire(student_id: int) -> bool:
    return cache.add(_lock_key(student_id), 1, LOCK_SECONDS)


def release(student_id: int) -> None:
    cache.delete(_lock_key(student_id))


def clear_pending(student_id: int) -> None:
    cache.delete(_pending_key(student_id))
