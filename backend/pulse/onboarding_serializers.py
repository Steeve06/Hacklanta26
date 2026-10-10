from datetime import time

from rest_framework import serializers

from accounts.models import StudentProfile, validate_timezone
from lms.selectors import enrolled_courses

from .models import AvailabilityBlock
from .serializers import AvailabilityBlockSerializer, AvailabilitySerializer


class StepSerializer(serializers.Serializer):
    """Each step's `apply()` saves it and returns (schedule inputs changed?, note for the
    student)."""

    @property
    def student(self):
        return self.context["student"]


class CoursesStep(StepSerializer):
    def validate(self, attrs):
        if not enrolled_courses(self.student).exists():
            raise serializers.ValidationError("You aren't enrolled in any courses yet.")
        return attrs

    def apply(self):
        return False, ""


class AvailabilityStep(StepSerializer):
    blocks = AvailabilityBlockSerializer(many=True)

    def validate_blocks(self, blocks):
        if not blocks:
            raise serializers.ValidationError("Add at least one study block.")
        return AvailabilitySerializer().validate_blocks(blocks)

    def apply(self):
        from .onboarding import replace_availability

        before = list(
            AvailabilityBlock.objects.filter(student=self.student).values_list(
                "weekday", "start_time", "end_time"
            )
        )
        merged = replace_availability(self.student, self.validated_data["blocks"])
        after = list(
            AvailabilityBlock.objects.filter(student=self.student).values_list(
                "weekday", "start_time", "end_time"
            )
        )
        note = f"Merged {merged} overlapping block{'s' if merged != 1 else ''}." if merged else ""
        return sorted(before) != sorted(after), note


class PreferencesStep(StepSerializer):
    max_hours_per_day = serializers.DecimalField(
        max_digits=4, decimal_places=1, min_value=1, max_value=12
    )
    session_minutes = serializers.ChoiceField(choices=[25, 50, 90])
    earliest_time = serializers.TimeField()
    latest_time = serializers.TimeField()
    timezone = serializers.CharField(max_length=64, validators=[validate_timezone])

    def validate(self, attrs):
        if attrs["latest_time"] <= attrs["earliest_time"]:
            raise serializers.ValidationError(
                {"latest_time": "Latest time must be after earliest time."}
            )
        return attrs

    def apply(self):
        data = self.validated_data
        profile = self.student.profile
        user = self.student
        fields = ["max_hours_per_day", "session_minutes", "earliest_time", "latest_time"]
        changed = user.timezone != data["timezone"] or any(
            getattr(profile, f) != data[f] for f in fields
        )
        StudentProfile.objects.filter(pk=profile.pk).update(**{f: data[f] for f in fields})
        if user.timezone != data["timezone"]:
            user.timezone = data["timezone"]
            user.save(update_fields=["timezone", "updated_at"])
        profile.refresh_from_db()
        return changed, ""


class NotificationsStep(StepSerializer):
    sass_level = serializers.IntegerField(min_value=1, max_value=4)
    quiet_start = serializers.TimeField(default=time(22))
    quiet_end = serializers.TimeField(default=time(8))

    def validate(self, attrs):
        if attrs["quiet_start"] == attrs["quiet_end"]:
            raise serializers.ValidationError(
                {"quiet_end": "Quiet hours need a different start and end."}
            )
        return attrs

    def apply(self):
        StudentProfile.objects.filter(user=self.student).update(**self.validated_data)
        self.student.profile.refresh_from_db()
        return False, ""


STEP_SERIALIZERS = {
    1: CoursesStep,
    2: AvailabilityStep,
    3: PreferencesStep,
    4: NotificationsStep,
}


class OnboardingPatchSerializer(serializers.Serializer):
    step = serializers.IntegerField(min_value=1, max_value=5)
    version = serializers.IntegerField(required=False)
    data = serializers.DictField(required=False, allow_null=True)


class PreferencesAnswer(serializers.Serializer):
    max_hours_per_day = serializers.DecimalField(max_digits=4, decimal_places=1)
    session_minutes = serializers.IntegerField()
    earliest_time = serializers.TimeField()
    latest_time = serializers.TimeField()
    timezone = serializers.CharField()


class NotificationsAnswer(serializers.Serializer):
    sass_level = serializers.IntegerField()
    quiet_start = serializers.TimeField()
    quiet_end = serializers.TimeField()


class OnboardingStateSerializer(serializers.Serializer):
    step = serializers.IntegerField()
    completed_steps = serializers.ListField(child=serializers.IntegerField())
    version = serializers.IntegerField()
    done = serializers.BooleanField()
    schedule_ready = serializers.BooleanField()
    stale = serializers.BooleanField()
    note = serializers.CharField(allow_blank=True)
    availability = AvailabilitySerializer()
    preferences = PreferencesAnswer()
    notifications = NotificationsAnswer()
