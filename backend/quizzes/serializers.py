from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import DailyDeck, Flashcard, Streak


class DeckCardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    topic = serializers.ChoiceField(choices=Flashcard.Topic.choices)
    front = serializers.CharField()
    back = serializers.CharField()
    knew = serializers.BooleanField(allow_null=True, help_text="null until the card is rated")


class DailyDeckSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()
    card_count = serializers.SerializerMethodField()

    class Meta:
        model = DailyDeck
        fields = [
            "id", "day", "state", "card_count", "started_at", "completed_at", "knew",
            "counted_for_streak",
        ]  # fmt: skip
        read_only_fields = fields

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
        cards = {c.id: c for c in Flashcard.objects.filter(id__in=obj.cards)}
        rated = dict(obj.reviews.values_list("card_id", "knew"))
        return [
            {
                "id": c.id,
                "topic": c.topic,
                "front": c.front,
                "back": c.back,
                "knew": rated.get(c.id),
            }  # fmt: skip
            for card_id in obj.cards
            if (c := cards.get(card_id))
        ]

    def get_milestone(self, obj) -> int | None:
        return self.context.get("milestone")

    def get_streak(self, obj) -> int:
        streak = Streak.objects.filter(student=obj.student).first()
        return streak.current if streak else 0


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
