from django.dispatch import receiver

from accounts.clock import now as clock_now
from accounts.models import User
from lms.selectors import student_snapshot
from lms.signals import lms_changed

from .engine import cancel_for_source, notify_win

RESOLVING = {"submission", "excused", "override", "assessment_deleted", "discussion_post"}


@receiver(lms_changed)
def on_lms_change(sender, student_ids, reason, details, **kwargs):
    assessment_id = details.get("assessment_id")
    if not assessment_id or reason not in RESOLVING:
        return
    for student in User.objects.filter(pk__in=student_ids).select_related("profile"):
        cancel_for_source(student.id, "assessment", assessment_id, reason)
        if reason not in ("submission", "discussion_post"):
            continue
        snapshot = student_snapshot(student, clock_now(student))
        item = next((a for a in snapshot.assessments if a.id == assessment_id), None)
        if item and item.done and item.submitted_at and item.submitted_at <= item.due_at:
            notify_win(student, title=item.title, source_type="assessment", source_id=item.id,
                       course_id=item.course_id)  # fmt: skip
