from datetime import time

from rest_framework import serializers

from .models import AvailabilityBlock, Blackout, PlanJob, Schedule, Session

STAGE_LABELS = {
    "queued": "Waiting to start",
    "collecting": "Collecting courses",
    "estimating": "Estimating work",
    "building": "Building schedule",
    "polishing": "Building schedule",
    "done": "Done",
}


class AvailabilityBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilityBlock
        fields = ["weekday", "start_time", "end_time"]

    def validate_weekday(self, value):
        if not 0 <= value <= 6:
            raise serializers.ValidationError("Weekday must be 0 (Monday) to 6 (Sunday).")
        return value

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"] and attrs["end_time"] != time(0):
            raise serializers.ValidationError({"end_time": "End time must be after start time."})
        return attrs


class AvailabilitySerializer(serializers.Serializer):
    blocks = AvailabilityBlockSerializer(many=True)

    def validate_blocks(self, blocks):
        by_day: dict[int, list] = {}
        for b in blocks:
            by_day.setdefault(b["weekday"], []).append(b)
        for day_blocks in by_day.values():
            day_blocks.sort(key=lambda b: b["start_time"])
            for a, b in zip(day_blocks, day_blocks[1:], strict=False):
                if b["start_time"] < a["end_time"]:
                    raise serializers.ValidationError("Blocks on the same day can't overlap.")
        if len(blocks) > 50:
            raise serializers.ValidationError("That's more blocks than Pulse can use.")
        return blocks


class BlackoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blackout
        fields = ["id", "start", "end", "label"]

    def validate(self, attrs):
        if attrs["end"] <= attrs["start"]:
            raise serializers.ValidationError({"end": "End must be after start."})
        return attrs


class SessionSerializer(serializers.ModelSerializer):
    course = serializers.IntegerField(source="task.course_id", read_only=True)
    task_title = serializers.CharField(source="title", read_only=True)
    source_type = serializers.CharField(source="task.source_type", read_only=True)
    source_id = serializers.IntegerField(source="task.source_id", read_only=True)
    minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Session
        fields = [
            "id", "start", "end", "course", "task_title", "source_type", "source_id", "kind",
            "status", "completed_minutes", "minutes", "at_risk",
        ]  # fmt: skip
        read_only_fields = fields


class OverloadItemSerializer(serializers.Serializer):
    source_type = serializers.CharField()
    source_id = serializers.IntegerField()
    course_code = serializers.CharField()
    title = serializers.CharField()
    due_at = serializers.DateTimeField()
    minutes_short = serializers.IntegerField()
    needs_longer_block = serializers.BooleanField()


class SuggestionSerializer(serializers.Serializer):
    type = serializers.CharField()
    text = serializers.CharField()
    weekday = serializers.IntegerField(required=False)
    assessment_id = serializers.IntegerField(required=False)


class ExcludedSerializer(serializers.Serializer):
    course_code = serializers.CharField()
    title = serializers.CharField()
    reason = serializers.CharField()


class OverloadReportSerializer(serializers.Serializer):
    items = OverloadItemSerializer(many=True)
    extra_hours_needed = serializers.FloatField()
    at_risk = serializers.ListField(child=serializers.CharField())
    suggestions = SuggestionSerializer(many=True)
    unresolvable = serializers.BooleanField()
    excluded = ExcludedSerializer(many=True)


class DeadlineSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    course = serializers.IntegerField()
    course_code = serializers.CharField()
    title = serializers.CharField()
    type = serializers.CharField()
    due_at = serializers.DateTimeField()
    status = serializers.CharField()
    weight_pct = serializers.FloatField()
    extended = serializers.BooleanField()


class CourseRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    title = serializers.CharField()
    color = serializers.CharField()


class ScheduleSerializer(serializers.ModelSerializer):
    overload_report = OverloadReportSerializer(allow_null=True)
    sessions = SessionSerializer(many=True)
    deadlines = DeadlineSerializer(many=True)
    upcoming = DeadlineSerializer(many=True)
    courses = CourseRefSerializer(many=True)
    term_start = serializers.DateField(allow_null=True)
    term_end = serializers.DateField(allow_null=True)

    class Meta:
        model = Schedule
        fields = [
            "id", "version", "generated_at", "horizon_end", "summary", "overload_report",
            "sessions", "deadlines", "upcoming", "courses", "term_start", "term_end",
        ]  # fmt: skip
        read_only_fields = fields


class SessionUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["done", "partial", "skipped", "planned"])
    completed_minutes = serializers.IntegerField(required=False, min_value=0)


class GenerateSerializer(serializers.Serializer):
    feedback = serializers.CharField(required=False, allow_blank=True, max_length=300)


class PlanJobSerializer(serializers.ModelSerializer):
    stage_label = serializers.SerializerMethodField()

    class Meta:
        model = PlanJob
        fields = ["id", "kind", "state", "progress", "stage", "stage_label", "error", "created_at"]
        read_only_fields = fields

    def get_stage_label(self, obj) -> str:
        return STAGE_LABELS.get(obj.stage, obj.stage)
