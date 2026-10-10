from django.dispatch import receiver

from accounts.models import User
from lms.signals import lms_changed

from .services.replan import request_replan


@receiver(lms_changed)
def replan_on_lms_change(sender, student_ids, reason, details, **kwargs):
    for student in User.objects.filter(pk__in=student_ids).select_related("profile"):
        request_replan(student, f"lms:{reason}")
