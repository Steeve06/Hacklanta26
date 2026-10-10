from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import StudentProfile, User, validate_timezone


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(email=attrs["email"].lower(), password=attrs["password"])
        if user is None or not user.is_active:
            raise serializers.ValidationError("Email or password is incorrect.")
        attrs["user"] = user
        return attrs


class AccessTokenSerializer(serializers.Serializer):
    access = serializers.CharField()


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = [
            "sass_level",
            "max_hours_per_day",
            "session_minutes",
            "earliest_time",
            "latest_time",
            "quiet_start",
            "quiet_end",
            "quiet_hours_override_for_deadlines",
            "supportive_mode",
            "onboarding_done",
            "push_prompt_seen",
        ]

    def validate_sass_level(self, value):
        if not 1 <= value <= 4:
            raise serializers.ValidationError("Sass level must be between 1 and 4.")
        return value

    def validate_max_hours_per_day(self, value):
        if not 0.5 <= float(value) <= 12:
            raise serializers.ValidationError("Choose between 0.5 and 12 hours.")
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

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "timezone", "profile"]
        read_only_fields = ["id", "email", "role"]


class MeUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=80, required=False)
    timezone = serializers.CharField(max_length=64, required=False, validators=[validate_timezone])
    profile = ProfileSerializer(required=False)
