from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import CheckAttempt, CheckQuestion, StudyCheck

CHECK_STATES = ["upcoming", "open", "passed", "not_passed", "missed"]


class CheckChapterSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    course_id = serializers.IntegerField()
    course_code = serializers.CharField(source="course.code")
    order = serializers.IntegerField()
    title = serializers.CharField()


class StudyCheckSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    chapters = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    tries_left = serializers.SerializerMethodField()
    best_correct = serializers.SerializerMethodField()
    card_count = serializers.SerializerMethodField()
    pass_mark = serializers.SerializerMethodField()

    class Meta:
        model = StudyCheck
        fields = [
            "id", "title", "chapters", "kind", "scheduled_date", "opens_at", "closes_at", "state",
            "passed", "counted_for_streak", "tries_left", "best_correct", "card_count", "pass_mark",
        ]  # fmt: skip
        read_only_fields = fields

    def _chapters(self, obj):
        return sorted(obj.chapters.all(), key=lambda c: (c.course.code, c.order))

    def get_title(self, obj) -> str:
        return ", ".join(f"{c.course.code} Ch {c.order}" for c in self._chapters(obj))

    @extend_schema_field(CheckChapterSerializer(many=True))
    def get_chapters(self, obj):
        return CheckChapterSerializer(self._chapters(obj), many=True).data

    @extend_schema_field(serializers.ChoiceField(choices=CHECK_STATES))
    def get_state(self, obj) -> str:
        from .services.checks import state_of

        return state_of(obj, self.context["now"])

    def get_tries_left(self, obj) -> int:
        from .services.checks import MAX_ATTEMPTS

        finished = sum(1 for a in obj.attempts.all() if a.finished_at)
        return 0 if obj.passed else max(0, MAX_ATTEMPTS - finished)

    def get_best_correct(self, obj) -> int | None:
        finished = [a.correct for a in obj.attempts.all() if a.finished_at]
        return max(finished) if finished else None

    def get_card_count(self, obj) -> int:
        from django.conf import settings

        latest = _latest_attempt(obj)
        return len(latest.cards) if latest else settings.STUDY_CHECK_CARDS

    def get_pass_mark(self, obj) -> int:
        from .services.checks import pass_mark

        return pass_mark(self.get_card_count(obj))


def _latest_attempt(check: StudyCheck) -> CheckAttempt | None:
    attempts = sorted(check.attempts.all(), key=lambda a: a.number)
    return attempts[-1] if attempts else None


class CardResultSerializer(serializers.Serializer):
    chosen = serializers.IntegerField(help_text="position of the tapped option, as shown")
    answer = serializers.IntegerField(help_text="position of the right option, as shown")
    correct = serializers.BooleanField()
    explanation = serializers.CharField()
    source_excerpt = serializers.CharField()


class CheckCardSerializer(serializers.Serializer):
    position = serializers.IntegerField()
    type = serializers.ChoiceField(choices=CheckQuestion.Type.choices)
    front = serializers.CharField()
    options = serializers.ListField(child=serializers.CharField())
    source = serializers.CharField(help_text="e.g. CS 201 · Ch 4: Stacks and Queues")
    chapter_id = serializers.IntegerField()
    course_id = serializers.IntegerField()
    result = CardResultSerializer(allow_null=True, help_text="null until the card is answered")


class AttemptSerializer(serializers.Serializer):
    number = serializers.IntegerField()
    correct = serializers.IntegerField()
    finished = serializers.BooleanField()
    cards = CheckCardSerializer(many=True)


def attempt_data(attempt: CheckAttempt) -> dict:
    """Cards as the student sees them. The right answer is only included once a card has been
    answered."""
    ids = [c["question_id"] for c in attempt.cards]
    questions = {
        q.id: q for q in CheckQuestion.objects.filter(id__in=ids).select_related("chapter__course")
    }
    answers = {a.position: a for a in attempt.answers.all()}
    cards = []
    for position, item in enumerate(attempt.cards):
        q = questions[item["question_id"]]
        order = item["order"]
        given = answers.get(position)
        result = None
        if given:
            result = {
                "chosen": order.index(given.chosen_index),
                "answer": order.index(q.correct_index),
                "correct": given.correct,
                "explanation": q.explanation,
                "source_excerpt": q.source_excerpt,
            }
        chapter = q.chapter
        cards.append(
            {
                "position": position,
                "type": q.type,
                "front": q.prompt,
                "options": [q.options[i] for i in order],
                "source": f"{chapter.course.code} · Ch {chapter.order}: {chapter.title}",
                "chapter_id": chapter.id,
                "course_id": chapter.course_id,
                "result": result,
            }
        )
    return {
        "number": attempt.number,
        "correct": attempt.correct,
        "finished": attempt.finished_at is not None,
        "cards": cards,
    }


class StudyCheckDetailSerializer(StudyCheckSerializer):
    attempt = serializers.SerializerMethodField()
    milestone = serializers.SerializerMethodField()
    streak = serializers.SerializerMethodField()

    class Meta(StudyCheckSerializer.Meta):
        fields = [*StudyCheckSerializer.Meta.fields, "attempt", "milestone", "streak"]
        read_only_fields = fields

    @extend_schema_field(AttemptSerializer(allow_null=True))
    def get_attempt(self, obj):
        latest = _latest_attempt(obj)
        return attempt_data(latest) if latest else None

    def get_milestone(self, obj) -> int | None:
        return self.context.get("milestone")

    def get_streak(self, obj) -> int:
        from .services.streaks import get_streak

        return get_streak(obj.student).current


class AnswerSerializer(serializers.Serializer):
    position = serializers.IntegerField(min_value=0, max_value=9)
    choice = serializers.IntegerField(min_value=0, max_value=3)


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
    week = StreakDaySerializer(many=True)
    recent = StreakEventSerializer(many=True)
