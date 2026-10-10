from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import BankQuestion, ChapterQuiz, Streak


class QuizChapterSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order = serializers.IntegerField()
    title = serializers.CharField()
    course_id = serializers.IntegerField()
    course_code = serializers.CharField()


class QuizQuestionSerializer(serializers.Serializer):
    position = serializers.IntegerField()
    type = serializers.CharField()
    prompt = serializers.CharField()
    options = serializers.ListField(child=serializers.CharField())


class QuizResultSerializer(serializers.Serializer):
    position = serializers.IntegerField()
    chosen = serializers.IntegerField()
    correct = serializers.IntegerField()
    is_correct = serializers.BooleanField()
    explanation = serializers.CharField()
    chapter_id = serializers.IntegerField()
    course_id = serializers.IntegerField()


class ChapterQuizSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()
    chapters = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = ChapterQuiz
        fields = [
            "id", "kind", "scheduled_date", "opens_at", "closes_at", "state", "chapters",
            "question_count", "started_at", "submitted_at", "score", "sharp", "counted_for_streak",
        ]  # fmt: skip
        read_only_fields = fields

    def get_state(self, obj) -> str:
        from .services.attempts import state_of

        return state_of(obj, self.context["now"])

    @extend_schema_field(QuizChapterSerializer(many=True))
    def get_chapters(self, obj):
        return [
            {
                "id": c.id,
                "order": c.order,
                "title": c.title,
                "course_id": c.course_id,
                "course_code": c.course.code,
            }  # fmt: skip
            for c in obj.chapters.all()
        ]

    def get_question_count(self, obj) -> int:
        return len(obj.questions)


class ChapterQuizDetailSerializer(ChapterQuizSerializer):
    questions = serializers.SerializerMethodField()
    results = serializers.SerializerMethodField()
    milestone = serializers.SerializerMethodField()
    streak = serializers.SerializerMethodField()

    class Meta(ChapterQuizSerializer.Meta):
        fields = [*ChapterQuizSerializer.Meta.fields, "questions", "results", "milestone", "streak"]
        read_only_fields = fields

    def _bank(self, obj) -> dict[int, BankQuestion]:
        if "bank" not in self.context:
            ids = [q["bank_id"] for q in obj.questions]
            self.context["bank"] = {
                q.id: q for q in BankQuestion.objects.filter(id__in=ids).select_related("chapter")
            }
        return self.context["bank"]

    @extend_schema_field(QuizQuestionSerializer(many=True))
    def get_questions(self, obj):
        if obj.started_at is None and obj.submitted_at is None:
            return []
        bank = self._bank(obj)
        rows = []
        for position, item in enumerate(obj.questions):
            q = bank.get(item["bank_id"])
            if q is None:
                continue
            rows.append(
                {
                    "position": position,
                    "type": q.type,
                    "prompt": q.prompt,
                    "options": [q.options[i] for i in item["order"]],
                }  # fmt: skip
            )
        return rows

    @extend_schema_field(QuizResultSerializer(many=True, allow_null=True))
    def get_results(self, obj):
        if obj.submitted_at is None:
            return None
        bank = self._bank(obj)
        chosen = {a.question_id: a.chosen_index for a in obj.answers.all()}
        rows = []
        for position, item in enumerate(obj.questions):
            q = bank.get(item["bank_id"])
            if q is None:
                continue
            order = item["order"]
            picked = chosen.get(q.id)
            rows.append(
                {
                    "position": position,
                    "chosen": order.index(picked) if picked in order else -1,
                    "correct": order.index(q.correct_index),
                    "is_correct": picked == q.correct_index,
                    "explanation": q.explanation,
                    "chapter_id": q.chapter_id,
                    "course_id": q.chapter.course_id,
                }
            )
        return rows

    def get_milestone(self, obj) -> int | None:
        return self.context.get("milestone")

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_streak(self, obj):
        streak = Streak.objects.filter(student=obj.student).first()
        return streak.current if streak else 0


class QuizAnswersSerializer(serializers.Serializer):
    answers = serializers.DictField(child=serializers.IntegerField(min_value=0))


class StreakEventSerializer(serializers.Serializer):
    result = serializers.CharField()
    streak_after = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class StreakSerializer(serializers.Serializer):
    current = serializers.IntegerField()
    longest = serializers.IntegerField()
    freezes = serializers.IntegerField()
    toward_next_freeze = serializers.IntegerField()
    next_milestone = serializers.IntegerField(allow_null=True)
    recent = StreakEventSerializer(many=True)
