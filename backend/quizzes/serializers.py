from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import DailyDeck, Flashcard, Streak


class DeckCardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    topic = serializers.ChoiceField(choices=Flashcard.Topic.choices)
    source = serializers.CharField(
        help_text="where the card comes from, e.g. CS 201 · Ch 5: Hashing"
    )
    chapter_id = serializers.IntegerField(allow_null=True)
    course_id = serializers.IntegerField(allow_null=True)
    front = serializers.CharField()
    back = serializers.CharField()
    knew = serializers.BooleanField(allow_null=True, help_text="null until the card is rated")


class DeckFocusSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=DailyDeck.Kind.choices)
    course_id = serializers.IntegerField(allow_null=True)
    course_code = serializers.CharField(allow_null=True)
    assessment_id = serializers.IntegerField(allow_null=True)
    assessment_title = serializers.CharField(allow_null=True)
    due_at = serializers.DateTimeField(allow_null=True)


class DailyDeckSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()
    card_count = serializers.SerializerMethodField()
    focus = serializers.SerializerMethodField()

    class Meta:
        model = DailyDeck
        fields = [
            "id", "day", "state", "card_count", "focus", "started_at", "completed_at", "knew",
            "counted_for_streak",
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

    def get_card_count(self, obj) -> int:
        return len(obj.cards)


class DailyDeckDetailSerializer(DailyDeckSerializer):
    cards = serializers.SerializerMethodField()
    milestone = serializers.SerializerMethodField()
    streak = serializers.SerializerMethodField()

    class Meta(DailyDeckSerializer.Meta):
        fields = [*DailyDeckSerializer.Meta.fields, "cards", "milestone", "streak"]
        read_only_fields = fields

    @extend_schema_field(DeckCardSerializer(many=True))
    def get_cards(self, obj):
        cards = {
            c.id: c
            for c in Flashcard.objects.filter(id__in=obj.cards).select_related("chapter__course")
        }
        rated = dict(obj.reviews.values_list("card_id", "knew"))
        return [
            {
                "id": c.id,
                "topic": c.topic,
                "source": _source(c),
                "front": c.front,
                "back": c.back,
                "knew": rated.get(c.id),
                "chapter_id": c.chapter_id,
                "course_id": c.chapter.course_id if c.chapter else None,
            }
            for card_id in obj.cards
            if (c := cards.get(card_id))
        ]

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


class ReviewSerializer(serializers.Serializer):
    card_id = serializers.IntegerField()
    knew = serializers.BooleanField()


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
