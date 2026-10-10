from datetime import time
from zoneinfo import ZoneInfo, available_timezones

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models

from config.models import TimeStamped


def validate_timezone(value: str) -> None:
    if value not in available_timezones():
        raise ValidationError(f"Unknown timezone: {value}")


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("role", User.Role.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin, TimeStamped):
    class Role(models.TextChoices):
        STUDENT = "student"
        INSTRUCTOR = "instructor"
        ADMIN = "admin"

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    timezone = models.CharField(
        max_length=64, default="America/New_York", validators=[validate_timezone]
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name"]

    def __str__(self) -> str:
        return self.email

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT

    @property
    def is_instructor(self) -> bool:
        return self.role == self.Role.INSTRUCTOR


class StudentProfile(TimeStamped):
    class SessionLength(models.IntegerChoices):
        SHORT = 25
        MEDIUM = 50
        LONG = 90

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    sass_level = models.PositiveSmallIntegerField(default=3)
    max_hours_per_day = models.DecimalField(max_digits=4, decimal_places=1, default=3)
    session_minutes = models.PositiveSmallIntegerField(
        choices=SessionLength.choices, default=SessionLength.MEDIUM
    )
    earliest_time = models.TimeField(default=time(8, 0))
    latest_time = models.TimeField(default=time(22, 0))
    quiet_start = models.TimeField(default=time(22, 0))
    quiet_end = models.TimeField(default=time(8, 0))
    quiet_hours_override_for_deadlines = models.BooleanField(default=False)
    supportive_mode = models.BooleanField(default=False)
    tone_down_streak = models.PositiveSmallIntegerField(default=0)
    onboarding_done = models.BooleanField(default=False)
    push_prompt_seen = models.BooleanField(default=False)
    plan_feedback = models.CharField(max_length=300, blank=True)
    clock_offset_minutes = models.IntegerField(default=0)

    def effective_sass(self) -> int:
        return 1 if self.supportive_mode else self.sass_level

    def __str__(self) -> str:
        return f"Profile<{self.user_id}>"
