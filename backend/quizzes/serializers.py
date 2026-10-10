from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import DailyDeck, Flashcard, Streak


class DeckItemSerializer(serializers.Serializer):
    position = serializers.IntegerField()
    type = serializers.ChoiceField(choices=["flashcard", "mcq", "short", "match"])
    source = serializers.CharField(help_text="e.g. CS 201 · Ch 5: Hashing, or a general topic")
    chapter_id = serializers.IntegerField(allow_null=True)
    course_id = serializers.IntegerField(allow_null=True)
    prompt = serializers.CharField(help_text="question text (the card front for flashcards)")
    back = serializers.CharField(allow_null=True, help_text="flashcards only: the other side")
    options = serializers.ListField(child=serializers.CharField(), allow_null=True)
    terms = serializers.ListField(child=serializers.CharField(), allow_null=True)
    clues = serializers.ListField(child=serializers.CharField(), allow_null=True)
    answered = serializers.BooleanField()
    correct = serializers.BooleanField(allow_null=True)
    response = serializers.JSONField(allow_null=True)
    solution = serializers.JSONField(
        allow_null=True, help_text="after answering: {answer, explanation, choice?} or {pairs}"
    )


class DeckFocusSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=DailyDeck.Kind.choices)
    course_id = serializers.IntegerField(allow_null=True)
    course_code = serializers.CharField(allow_null=True)
    assessment_id = serializers.IntegerField(allow_null=True)
    assessment_title = serializers.CharField(allow_null=True)
    due_at = serializers.DateTimeField(allow_null=True)


class DailyDeckSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    focus = serializers.SerializerMethodField()
    deadline = serializers.SerializerMethodField()

    class Meta:
        model = DailyDeck
        fields = [
            "id", "day", "state", "question_count", "time_limit_seconds", "focus", "started_at",
            "deadline", "completed_at", "knew", "xp", "counted_for_streak",
        ]  # fmt: skip
        read_only_fields = fields

    @extend_schema_field(DeckFocusSerializer)
    def get_focus(self, obj):
        """What the deck is about. due_at is the student's own deadline (extensions included)."""
        assessment = obj.assessment
        due_at = None
        if assessment is not None:
            from lms.models import DueDateOverride

            override = DueDateOverride.objects.filter(
                assessment=assessment, student_id=obj.student_id
            ).first()
            due_at = override.due_at if override else assessment.due_at
        return {
            "kind": obj.kind,
            "course_id": obj.course_id,
            "course_code": obj.course.code if obj.course else None,
            "assessment_id": obj.assessment_id,
            "assessment_title": assessment.title if assessment else None,
            "due_at": due_at,
        }

    def get_state(self, obj) -> str:
        from .services.decks import state_of

        return state_of(obj, self.context["now"])

    def get_question_count(self, obj) -> int:
        return len(obj.items)

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_deadline(self, obj):
        from .services.decks import deadline

        when = deadline(obj)
        return serializers.DateTimeField().to_representation(when) if when else None


class DailyDeckDetailSerializer(DailyDeckSerializer):
    items = serializers.SerializerMethodField()
    milestone = serializers.SerializerMethodField()
    streak = serializers.SerializerMethodField()

    class Meta(DailyDeckSerializer.Meta):
        fields = [*DailyDeckSerializer.Meta.fields, "items", "milestone", "streak"]
        read_only_fields = fields

    @extend_schema_field(DeckItemSerializer(many=True))
    def get_items(self, obj):
        from .services.items import item_cards, solution

        ids = {c for item in obj.items for c in item_cards(item)}
        cards = {
            c.id: c for c in Flashcard.objects.filter(id__in=ids).select_related("chapter__course")
        }
        answers = {a.position: a for a in obj.answers.all()}
        reveal = obj.completed_at is not None
        rows = []
        for position, item in enumerate(obj.items):
            used = [cards[c] for c in item_cards(item) if c in cards]
            if not used:
                continue
            first = used[0]
            done = answers.get(position)
            row = {
                "position": position, "type": item["type"], "source": _source(first),
                "chapter_id": first.chapter_id,
                "course_id": first.chapter.course_id if first.chapter else None,
                "prompt": first.front, "back": None, "options": None, "terms": None,
                "clues": None, "answered": done is not None,
                "correct": done.correct if done else None,
                "response": done.response if done else None,
                "solution": solution(item, cards) if (done or reveal) else None,
            }  # fmt: skip
            if item["type"] == "flashcard":
                row["back"] = first.back
            elif item["type"] == "mcq":
                row["options"] = item["options"]
            elif item["type"] == "match":
                row["prompt"] = "Match each term to the sentence it completes."
                row["terms"] = [cards[c].answer for c in item["cards"]]
                row["clues"] = [cards[c].clue for c in item["clues"]]
            rows.append(row)
        return rows

    def get_milestone(self, obj) -> int | None:
        return self.context.get("milestone")

    def get_streak(self, obj) -> int:
        streak = Streak.objects.filter(student=obj.student).first()
        return streak.current if streak else 0


def _source(card: Flashcard) -> str:
    if card.chapter is None:
        return card.get_topic_display()
    chapter = card.chapter
    return f"{chapter.course.code} · Ch {chapter.order}: {chapter.title}"


class AnswerSerializer(serializers.Serializer):
    position = serializers.IntegerField(min_value=0)
    response = serializers.JSONField(
        help_text='{"knew": bool} | {"choice": int} | {"text": str} | {"pairs": [int, ...]}'
    )

    def validate_response(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Send the answer as an object.")
        return value


class LeaderboardRowSerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    student_id = serializers.IntegerField()
    name = serializers.CharField()
    xp = serializers.IntegerField()
    streak = serializers.IntegerField()
    is_me = serializers.BooleanField()


class LeaderboardCourseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()


class LeaderboardSerializer(serializers.Serializer):
    week_start = serializers.DateField()
    course_id = serializers.IntegerField(allow_null=True)
    courses = LeaderboardCourseSerializer(many=True)
    rows = LeaderboardRowSerializer(many=True)


class StreakEventSerializer(serializers.Serializer):
    day = serializers.DateField(allow_null=True)
    result = serializers.CharField()
    streak_after = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class StreakDaySerializer(serializers.Serializer):
    day = serializers.DateField()
    result = serializers.ChoiceField(choices=["done", "frozen", "missed", "open", "none"])


class StreakSerializer(serializers.Serializer):
    current = serializers.IntegerField()
    longest = serializers.IntegerField()
    freezes = serializers.IntegerField()
    toward_next_freeze = serializers.IntegerField()
    next_milestone = serializers.IntegerField(allow_null=True)
    done_today = serializers.BooleanField()
    week = StreakDaySerializer(many=True)
    recent = StreakEventSerializer(many=True)
