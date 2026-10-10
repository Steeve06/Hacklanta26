import logging

from celery import shared_task
from django.db import transaction

from accounts.clock import local_now
from accounts.models import User

from .models import PlanJob
from .services import replan
from .services.planner import plan

logger = logging.getLogger(__name__)

STAGES = {
    "collecting": "Collecting courses",
    "estimating": "Estimating work",
    "building": "Building schedule",
    "polishing": "Building schedule",
    "done": "Done",
}


class JobCancelled(Exception):
    pass


@shared_task(bind=True, max_retries=10)
def run_plan_job(self, job_id: int) -> None:
    job = PlanJob.objects.select_related("student").get(pk=job_id)
    if job.state != PlanJob.State.QUEUED:
        return
    if not replan.acquire(job.student_id):
        raise self.retry(countdown=3)
    try:
        PlanJob.objects.filter(pk=job.pk).update(
            state=PlanJob.State.RUNNING, stage="collecting", progress=5
        )

        def on_progress(stage: str, progress: int) -> None:
            state = PlanJob.objects.filter(pk=job.pk).values_list("state", flat=True).first()
            if state == PlanJob.State.CANCELLED:
                raise JobCancelled
            PlanJob.objects.filter(pk=job.pk).update(stage=stage, progress=progress)

        schedule = plan(job.student, reason=job.kind, on_progress=on_progress)
        PlanJob.objects.filter(pk=job.pk).exclude(state=PlanJob.State.CANCELLED).update(
            state=PlanJob.State.DONE, stage="done", progress=100, schedule=schedule
        )
    except JobCancelled:
        logger.info("Plan job %s cancelled", job.pk)
    except Exception as exc:
        logger.exception("Plan job %s failed", job.pk)
        PlanJob.objects.filter(pk=job.pk).update(state=PlanJob.State.FAILED, error=str(exc)[:500])
    finally:
        replan.release(job.student_id)


@shared_task(bind=True, max_retries=20)
def replan_student(self, student_id: int, reason: str) -> None:
    student = User.objects.filter(pk=student_id).select_related("profile").first()
    if student is None or not replan.can_plan(student):
        replan.clear_pending(student_id)
        return
    if not replan.acquire(student_id):
        raise self.retry(countdown=5)
    replan.clear_pending(student_id)
    try:
        with transaction.atomic():
            plan(student, reason=reason)
    except Exception:
        logger.exception("Re-plan failed for student %s (%s)", student_id, reason)
    finally:
        replan.release(student_id)


@shared_task
def roll_forward_due_students() -> int:
    """Hourly: re-plan every student for whom it is now 03:00 local time."""
    count = 0
    for student in User.objects.filter(
        role=User.Role.STUDENT, profile__onboarding_done=True
    ).select_related("profile"):
        if local_now(student).hour == 3:
            replan.request_replan(student, "nightly")
            count += 1
    return count
