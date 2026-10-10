"""Who can see what in Learning Hub."""

from django.db.models import QuerySet
from rest_framework.exceptions import NotFound, PermissionDenied

from .models import Assessment, Chapter, Course, Enrollment


def visible_courses(user) -> QuerySet[Course]:
    if user.role == "admin" or user.is_superuser:
        return Course.objects.all()
    if user.role == "instructor":
        return Course.objects.filter(instructor=user)
    return Course.objects.filter(enrollments__user=user, enrollments__role=Enrollment.Role.STUDENT)


def get_course(user, course_id: int) -> Course:
    course = visible_courses(user).filter(pk=course_id).first()
    if course is None:
        raise NotFound("Course not found.")
    return course


def get_chapter(user, chapter_id: int) -> Chapter:
    chapter = (
        Chapter.objects.select_related("course")
        .filter(pk=chapter_id, course__in=visible_courses(user))
        .first()
    )
    if chapter is None:
        raise NotFound("Chapter not found.")
    return chapter


def get_assessment(user, assessment_id: int) -> Assessment:
    qs = Assessment.objects.select_related("course").filter(
        pk=assessment_id, course__in=visible_courses(user)
    )
    if user.role == "student":
        qs = qs.filter(published=True)
    assessment = qs.first()
    if assessment is None:
        raise NotFound("Assignment not found.")
    return assessment


def require_teacher(user, course: Course) -> None:
    if not (user.is_superuser or user.role == "admin" or course.instructor_id == user.id):
        raise PermissionDenied("Only the course instructor can do that.")


def require_student(user) -> None:
    if user.role != "student":
        raise PermissionDenied("Only students can do that.")


def enrolled_student_ids(course: Course) -> list[int]:
    return list(
        Enrollment.objects.filter(course=course, role=Enrollment.Role.STUDENT).values_list(
            "user_id", flat=True
        )
    )
