import factory

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
