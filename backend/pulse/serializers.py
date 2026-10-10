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


def block_minutes(start: time, end: time) -> int:
    """Length of a block; an end of 00:00 means midnight at the end of the day."""
    end_minutes = 24 * 60 if end == time(0) else end.hour * 60 + end.minute
    return end_minutes - (start.hour * 60 + start.minute)


def merge_blocks(blocks: list[dict]) -> tuple[list[dict], int]:
    """Join overlapping or touching blocks on the same day. Returns the blocks and how many
    were absorbed."""
    merged: list[dict] = []
    for block in sorted(blocks, key=lambda b: (b["weekday"], b["start_time"])):
        last = merged[-1] if merged else None
        end_of_last = None
        if last and last["weekday"] == block["weekday"]:
            end_of_last = time(23, 59, 59) if last["end_time"] == time(0) else last["end_time"]
        if end_of_last is not None and block["start_time"] <= end_of_last:
            if last["end_time"] != time(0) and (
                block["end_time"] == time(0) or block["end_time"] > last["end_time"]
            ):
                last["end_time"] = block["end_time"]
            continue
        merged.append(dict(block))
    return merged, len(blocks) - len(merged)


class AvailabilityBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilityBlock
        fields = ["weekday", "start_time", "end_time"]

    def validate_weekday(self, value):
        if not 0 <= value <= 6:
            raise serializers.ValidationError("Weekday must be 0 (Monday) to 6 (Sunday).")
        return value

    def validate(self, attrs):
        length = block_minutes(attrs["start_time"], attrs["end_time"])
        if length <= 0:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})
        if length < 30:
            raise serializers.ValidationError(
                {"end_time": "A study block needs at least 30 minutes."}
            )
        return attrs


class AvailabilitySerializer(serializers.Serializer):
    blocks = AvailabilityBlockSerializer(many=True)
    merged = serializers.IntegerField(read_only=True, default=0)

    def validate_blocks(self, blocks):
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
    closes_at = serializers.DateTimeField()
    status = serializers.CharField()
    weight_pct = serializers.FloatField()
    extended = serializers.BooleanField()


class CourseRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    title = serializers.CharField()
    color = serializers.CharField()


class ChapterReleaseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    course = serializers.IntegerField()
    course_code = serializers.CharField()
    order = serializers.IntegerField()
    title = serializers.CharField()
    available_from = serializers.DateTimeField()
    completed = serializers.BooleanField()


class CourseCalendarSerializer(serializers.Serializer):
    """The course schedule from Learning Hub for one week: due dates (with extensions applied)
    and chapter releases. Separate from the study plan Pulse builds."""

    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    deadlines = DeadlineSerializer(many=True)
    chapters = ChapterReleaseSerializer(many=True)
    courses = CourseRefSerializer(many=True)


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


class StatusEntrySerializer(serializers.Serializer):
    course_id = serializers.IntegerField(allow_null=True)
    code = serializers.CharField()
    score = serializers.IntegerField()
    state = serializers.ChoiceField(choices=["good", "medium", "bad"])
    reasons = serializers.ListField(child=serializers.CharField())
    components = serializers.DictField(child=serializers.FloatField())


class MomentSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["celebrate", "gasp", "fresh_start"])
    key = serializers.CharField()
    text = serializers.CharField()


class StatusSerializer(serializers.Serializer):
    computed_at = serializers.DateTimeField()
    overall = StatusEntrySerializer()
    courses = StatusEntrySerializer(many=True)
    fresh_start = serializers.BooleanField()
    all_done = serializers.BooleanField()
    moment = MomentSerializer(allow_null=True)
