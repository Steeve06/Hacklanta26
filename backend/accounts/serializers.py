from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.clock import now as clock_now

from .models import StudentProfile, User, validate_timezone


def normalize_email(value: str) -> str:
    return value.strip().lower()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    remember = serializers.BooleanField(required=False, default=False)

    def validate_email(self, value):
        return normalize_email(value)


def _check_password(password: str, user: User, field: str = "password") -> None:
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({field: list(exc.messages)}) from exc


class SignupSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=["student", "teacher"], required=False, default="student"
    )
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)
    timezone = serializers.CharField(max_length=64, required=False, validators=[validate_timezone])

    def validate_email(self, value):
        return normalize_email(value)

    def validate(self, attrs):
        from lms.registration import pending_teacher

        teacher = pending_teacher(attrs["email"])
        if attrs.get("role") == "teacher":
            if teacher is None:
                taken = User.objects.filter(email__iexact=attrs["email"]).exists()
                raise serializers.ValidationError(
                    {
                        "email": "An account with this email already exists."
                        if taken
                        else "No course is registered to this email yet. Use the email your "
                        "department registered, or ask them to add your course."
                    }
                )
            attrs["teacher"] = teacher
        elif teacher is not None:
            raise serializers.ValidationError(
                {"email": "This email is registered to teach a course. Sign up as a teacher."}
            )
        elif User.objects.filter(email__iexact=attrs["email"]).exists():
            raise serializers.ValidationError(
                {"email": "An account with this email already exists."}
            )
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords don't match."})
        candidate = User(
            email=attrs["email"], first_name=attrs["first_name"], last_name=attrs["last_name"]
        )
        _check_password(attrs["password"], candidate)
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return normalize_email(value)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords don't match."})
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = self.context["user"]
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError(
                {"current_password": "That isn't your current password."}
            )
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Passwords don't match."})
        _check_password(attrs["new_password"], user, field="new_password")
        return attrs


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class AccessTokenSerializer(serializers.Serializer):
    access = serializers.CharField()


PROFILE_FIELDS = [
    "sass_level",
    "max_hours_per_day",
    "max_hours_per_week",
    "session_minutes",
    "earliest_time",
    "latest_time",
    "quiet_start",
    "quiet_end",
    "quiet_hours_override_for_deadlines",
    "supportive_mode",
    "onboarding_done",
    "push_prompt_seen",
    "plan_feedback",
]


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = PROFILE_FIELDS
        read_only_fields = PROFILE_FIELDS


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = PROFILE_FIELDS

    def validate_sass_level(self, value):
        if not 1 <= value <= 4:
            raise serializers.ValidationError("Sass level must be between 1 and 4.")
        return value

    def validate_max_hours_per_week(self, value):
        if not 2 <= float(value) <= 40:
            raise serializers.ValidationError("Choose between 2 and 40 hours.")
        return value

    def validate_max_hours_per_day(self, value):
        if not 1 <= float(value) <= 12:
            raise serializers.ValidationError("Choose between 1 and 12 hours.")
        return value

    def validate(self, attrs):
        earliest = attrs.get("earliest_time", getattr(self.instance, "earliest_time", None))
        latest = attrs.get("latest_time", getattr(self.instance, "latest_time", None))
        if earliest and latest and earliest >= latest:
            raise serializers.ValidationError(
                {"latest_time": "Latest time must be after earliest time."}
            )
        if attrs.get("supportive_mode") is False:
            attrs["tone_down_streak"] = 0
        return attrs


class MeSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    server_now = serializers.SerializerMethodField()
    demo_mode = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "role", "timezone", "profile", "server_now",
            "demo_mode",
        ]  # fmt: skip
        read_only_fields = fields

    def get_server_now(self, obj) -> str:
        return clock_now(obj).isoformat()

    def get_demo_mode(self, obj) -> bool:
        return settings.DEMO_MODE


class MeUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=80, required=False)
    timezone = serializers.CharField(max_length=64, required=False, validators=[validate_timezone])
    profile = ProfileUpdateSerializer(required=False)
