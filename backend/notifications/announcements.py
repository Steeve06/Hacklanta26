"""Tell students when their teacher posts something new: in the inbox and, on devices that
turned push on, as a push notification. Content that opens later is announced when it opens."""

from django.db import IntegrityError

from accounts.clock import now as clock_now
from accounts.models import StudentProfile, User

from .engine import _channels, dispatch_due, quiet_until
from .models import Notification, Trigger

LABELS = {"chapter": "chapter", "homework": "assignment", "discussion": "discussion",
          "quiz": "quiz"}  # fmt: skip
TIER = 1


def announce(student_ids, *, kind: str, title: str, course, source_type: str, source_id: int,
             link: str, opens_at=None) -> int:  # fmt: skip
    created = 0
    text = f"New {LABELS.get(kind, 'item')} in {course.code}: {title}"[:400]
    students = User.objects.filter(pk__in=student_ids, role=User.Role.STUDENT, is_active=True)
    for student in students:
        profile, _ = StudentProfile.objects.get_or_create(user=student)
        now = clock_now(student)
        start = max(now, opens_at) if opens_at else now
        try:
            Notification.objects.create(
                student=student, trigger=Trigger.NEW_CONTENT, tier=TIER,
                sass_level=profile.effective_sass(), source_type=source_type,
                source_id=source_id, course_id=course.id, text=text, link=link,
                channels=[c for c in _channels(student, TIER) if c != "email"],
                scheduled_for=quiet_until(student, profile, start, None) or start,
                dedupe_key=f"{student.id}:new_content:{source_type}:{source_id}",
            )  # fmt: skip
        except IntegrityError:
            continue
        created += 1
        dispatch_due(student=student)
    return created
