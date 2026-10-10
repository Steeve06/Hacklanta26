import logging

from celery import shared_task

from accounts.models import User
from lms.models import Chapter

from .models import StreakEvent, StudyCheck

logger = logging.getLogger(__name__)


@shared_task
def sync_student_checks(student_id: int) -> int:
    from .services.windows import sync_checks

    student = User.objects.filter(pk=student_id, role=User.Role.STUDENT).first()
    return len(sync_checks(student)) if student else 0


@shared_task
def rebuild_chapter_bank(chapter_id: int) -> int:
    from .services.bank import rebuild_bank

    chapter = Chapter.objects.filter(pk=chapter_id).first()
    return rebuild_bank(chapter) if chapter else 0


@shared_task
def sweep_checks() -> int:
    """Every 10 minutes: settle checks whose window closed and deadlines that passed without a
    submission (freeze or reset the streak)."""
    from django.utils import timezone

    from lms.models import Assessment, Enrollment
    from notifications.engine import notify_streak_lost

    from .services.missed import RECENT
    from .services.streaks import sweep_student

    now = timezone.now()
    recent_courses = Assessment.objects.filter(due_at__gte=now - RECENT, due_at__lt=now).values(
        "course_id"
    )
    student_ids = set(
        StudyCheck.objects.filter(resolved=False).values_list("student_id", flat=True)
    ) | set(
        Enrollment.objects.filter(course_id__in=recent_courses, role="student").values_list(
            "user_id", flat=True
        )
    )
    settled = 0
    for student in User.objects.filter(pk__in=student_ids, role="student").select_related(
        "profile"
    ):
        for event in sweep_student(student):
            settled += 1
            if event.result == StreakEvent.Result.MISSED and event.study_check:
                notify_streak_lost(student, event.study_check)
    return settled
