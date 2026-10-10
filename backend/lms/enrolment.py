from django.db.models import Q
from django.utils import timezone

from .models import Assessment, Course, Enrollment, Submission, Term


def enroll_in_current_term(student) -> int:
    """Self sign-ups join every course of the latest term, so Pulse has work to plan. Work whose
    deadline passed before they joined is excused: it was never theirs to miss."""
    term = Term.objects.order_by("-start_date").first()
    if term is None:
        return 0
    courses = list(Course.objects.filter(term=term))
    already = set(
        Enrollment.objects.filter(user=student, course__in=courses).values_list(
            "course_id", flat=True
        )
    )
    joining = [c for c in courses if c.id not in already]
    Enrollment.objects.bulk_create(
        [Enrollment(user=student, course=c, role=Enrollment.Role.STUDENT) for c in joining],
        ignore_conflicts=True,
    )
    now = timezone.now()
    closed = Assessment.objects.filter(course__in=joining).filter(
        Q(cutoff_at__lt=now) | Q(cutoff_at__isnull=True, due_at__lt=now)
    )
    Submission.objects.bulk_create(
        [
            Submission(assessment=a, student=student, status=Submission.Status.EXCUSED)
            for a in closed
        ]
    )
    return len(joining)
