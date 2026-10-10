from django.dispatch import receiver

from accounts.models import User
from lms.signals import lms_changed

from .models import Schedule
from .services import status
from .services.planner import schedule_committed
from .services.replan import request_replan


@receiver(lms_changed)
def replan_on_lms_change(sender, student_ids, reason, details, **kwargs):
    for student in User.objects.filter(pk__in=student_ids).select_related("profile"):
        status.invalidate(student.id)
        request_replan(student, f"lms:{reason}")


@receiver(schedule_committed, sender=Schedule)
def refresh_status(sender, schedule, **kwargs):
    status.invalidate(schedule.student_id)
