from django.db import transaction
from django.dispatch import receiver

from accounts.models import User
from lms.signals import lms_changed
from pulse.models import Schedule
from pulse.services.planner import schedule_committed

from .tasks import rebuild_chapter_bank, sync_student_windows


@receiver(schedule_committed, sender=Schedule)
def windows_follow_schedule(sender, schedule, **kwargs):
    sync_student_windows.delay(schedule.student_id)


@receiver(lms_changed)
def on_lms_change(sender, student_ids, reason, details, **kwargs):
    chapter_id = details.get("chapter_id")
    if reason in ("chapter_created", "chapter_updated") and chapter_id:
        transaction.on_commit(lambda: rebuild_chapter_bank.delay(chapter_id))
    if reason == "chapter_completed":
        for student_id in User.objects.filter(pk__in=student_ids).values_list("id", flat=True):
            sync_student_windows.delay(student_id)
