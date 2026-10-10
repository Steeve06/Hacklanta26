"""Learning Hub emits `lms_changed` after any change that can affect a student's plan.

Pulse listens; Learning Hub never imports Pulse.
"""

from django.db import transaction
from django.dispatch import Signal

lms_changed = Signal()


def emit_change(student_ids, reason: str, **details) -> None:
    ids = sorted({int(i) for i in student_ids})
    if not ids:
        return
    transaction.on_commit(
        lambda: lms_changed.send(sender="lms", student_ids=ids, reason=reason, details=details)
    )
