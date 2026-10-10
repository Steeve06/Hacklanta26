import logging

from celery import shared_task

from accounts.models import User
from lms.models import Chapter

from .models import ChapterQuiz, StreakEvent

logger = logging.getLogger(__name__)


@shared_task
def sync_student_windows(student_id: int) -> int:
    from .services.windows import sync_windows

    student = User.objects.filter(pk=student_id, role=User.Role.STUDENT).first()
    return len(sync_windows(student)) if student else 0


@shared_task
def rebuild_chapter_bank(chapter_id: int) -> int:
    from .services.bank import rebuild_bank

    chapter = Chapter.objects.filter(pk=chapter_id).first()
    return rebuild_bank(chapter) if chapter else 0


@shared_task
def sweep_windows() -> int:
    """Every 10 minutes: settle quiz windows that closed (freeze or reset the streak)."""
    from notifications.engine import notify_streak_lost

    from .services.streaks import sweep_student

    student_ids = (
        ChapterQuiz.objects.filter(resolved=False).values_list("student_id", flat=True).distinct()
    )
    settled = 0
    for student in User.objects.filter(pk__in=list(student_ids)).select_related("profile"):
        for event in sweep_student(student):
            settled += 1
            if event.result == StreakEvent.Result.MISSED and event.quiz:
                notify_streak_lost(student, event.quiz)
    return settled
