from datetime import timedelta

import factory
from django.utils import timezone

from accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.edu")
    first_name = factory.Sequence(lambda n: f"Sam{n}")
    timezone = "America/New_York"
    password = factory.PostGenerationMethodCall("set_password", "correct-horse")

    @factory.post_generation
    def _save(obj, create, extracted, **kwargs):
        if create:
            obj.save()


class StudentFactory(UserFactory):
    role = User.Role.STUDENT


class InstructorFactory(UserFactory):
    role = User.Role.INSTRUCTOR


class TermFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "lms.Term"

    name = "Fall 2026"
    start_date = factory.LazyFunction(lambda: (timezone.now() - timedelta(weeks=4)).date())
    end_date = factory.LazyAttribute(lambda o: o.start_date + timedelta(weeks=15))


class CourseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "lms.Course"

    term = factory.SubFactory(TermFactory)
    code = factory.Sequence(lambda n: f"TST {100 + n}")
    title = "Testing Things"
    instructor = factory.SubFactory(InstructorFactory)


class ChapterFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "lms.Chapter"

    course = factory.SubFactory(CourseFactory)
    order = factory.Sequence(lambda n: n + 1)
    title = factory.Sequence(lambda n: f"Chapter {n}")
    body_md = (
        "Spaced practice beats cramming for long-term retention. "
        "Retrieval practice strengthens memory more than rereading does. "
        "Interleaving topics helps learners tell problem types apart."
    )
    objectives = factory.LazyFunction(lambda: ["Explain spaced practice"])
    reading_minutes = 20
    available_from = factory.LazyFunction(lambda: timezone.now() - timedelta(days=7))


class AssessmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "lms.Assessment"

    course = factory.SubFactory(CourseFactory)
    type = "homework"
    title = factory.Sequence(lambda n: f"Assignment {n}")
    instructions = "Do the thing."
    open_at = factory.LazyFunction(lambda: timezone.now() - timedelta(days=5))
    due_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=3))
    cutoff_at = factory.LazyAttribute(lambda o: o.due_at + timedelta(days=2))
    weight_pct = 10
    est_minutes = None
    max_attempts = 2


def enroll(user, course, role="student"):
    from lms.models import Enrollment

    return Enrollment.objects.get_or_create(user=user, course=course, defaults={"role": role})[0]
