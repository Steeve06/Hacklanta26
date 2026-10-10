from .models import Course, Enrollment, Term


def enroll_in_current_term(student) -> int:
    """Self sign-ups join every course of the latest term, so Pulse has work to plan."""
    term = Term.objects.order_by("-start_date").first()
    if term is None:
        return 0
    created = Enrollment.objects.bulk_create(
        [
            Enrollment(user=student, course=course, role=Enrollment.Role.STUDENT)
            for course in Course.objects.filter(term=term)
        ],
        ignore_conflicts=True,
    )
    return len(created)
