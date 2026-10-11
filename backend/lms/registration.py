"""Pre-registered courses. The department registers a course with its teacher's email; the
teacher's account waits, without a password, until they sign up with that email and claim it.
Students only ever see what the teacher adds afterwards."""

from dataclasses import dataclass, field
from datetime import time

from django.db import transaction

from accounts.models import User

from .models import Course, CourseMeeting, Enrollment, Syllabus, Term

DEFAULT_POLICIES = {
    "late_work": "Late work loses 10% per day until the cut-off, unless you have an extension.",
    "academic_integrity": "Submit your own work and cite any sources or tools you used.",
}


@dataclass
class Meeting:
    weekday: int
    start: time
    end: time
    location: str = ""


@dataclass
class Registration:
    code: str
    title: str
    teacher_email: str
    teacher_first_name: str = ""
    teacher_last_name: str = ""
    color: str = "#1f6f5c"
    description: str = ""
    office_hours: str = ""
    meetings: list[Meeting] = field(default_factory=list)


def is_pending_teacher(user: User) -> bool:
    return user.role == User.Role.INSTRUCTOR and not user.has_usable_password()


def pending_teacher(email: str) -> User | None:
    user = User.objects.filter(email__iexact=email.strip(), role=User.Role.INSTRUCTOR).first()
    return user if user is not None and is_pending_teacher(user) else None


def current_term() -> Term | None:
    return Term.objects.order_by("-start_date").first()


@transaction.atomic
def register_course(reg: Registration, term: Term | None = None) -> Course:
    """Create the course shell (class times, an empty syllabus) and the teacher's waiting
    account. Students who already signed up join the course if it's in the current term."""
    term = term or current_term()
    if term is None:
        raise ValueError("Create a term before registering courses.")
    email = reg.teacher_email.strip().lower()
    teacher = User.objects.filter(email__iexact=email).first()
    if teacher is None:
        teacher = User.objects.create_user(
            email,
            None,
            first_name=reg.teacher_first_name.strip() or "Instructor",
            last_name=reg.teacher_last_name.strip(),
            role=User.Role.INSTRUCTOR,
        )
    elif teacher.role != User.Role.INSTRUCTOR:
        raise ValueError(f"{email} already belongs to a {teacher.role} account.")
    course = Course.objects.create(
        term=term, code=reg.code.strip(), title=reg.title.strip(), instructor=teacher,
        color=reg.color,
    )  # fmt: skip
    Enrollment.objects.create(user=teacher, course=course, role=Enrollment.Role.INSTRUCTOR)
    CourseMeeting.objects.bulk_create(
        CourseMeeting(
            course=course,
            weekday=m.weekday,
            start_time=m.start,
            end_time=m.end,
            location=m.location,
        )  # fmt: skip
        for m in reg.meetings
    )
    Syllabus.objects.create(
        course=course,
        description=reg.description,
        office_hours=reg.office_hours,
        grading=[],
        policies=DEFAULT_POLICIES,
    )
    if term == current_term():
        students = User.objects.filter(role=User.Role.STUDENT, is_active=True)
        Enrollment.objects.bulk_create(
            [Enrollment(user=s, course=course) for s in students], ignore_conflicts=True
        )
    return course


@transaction.atomic
def claim_teacher_account(
    teacher: User, *, password: str, first_name: str, last_name: str, timezone: str | None
) -> User:
    teacher.set_password(password)
    teacher.first_name = first_name.strip()
    teacher.last_name = last_name.strip()
    if timezone:
        teacher.timezone = timezone
    teacher.save()
    return teacher
