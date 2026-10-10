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
    correct = serializers.BooleanField()
    explanation = serializers.CharField()
    source_excerpt = serializers.CharField()
    chosen = serializers.IntegerField(allow_null=True, help_text="choice: option tapped, as shown")
    answer = serializers.IntegerField(allow_null=True, help_text="choice: right option, as shown")
    given_text = serializers.CharField(allow_null=True, help_text="short: what was typed")
    expected_text = serializers.CharField(allow_null=True, help_text="short: the key term")
    pairs = serializers.ListField(
        child=serializers.IntegerField(),
        allow_null=True,
        help_text="match: sentence picked per term",
    )
    right_pairs = serializers.ListField(
        child=serializers.IntegerField(),
        allow_null=True,
        help_text="match: right sentence per term",
    )


class CheckCardSerializer(serializers.Serializer):
    position = serializers.IntegerField()
    kind = serializers.ChoiceField(choices=["choice", "short", "match"])
    type = serializers.CharField(help_text="multiple_choice, true_false, short_answer or matching")
    front = serializers.CharField()
    options = serializers.ListField(child=serializers.CharField())
    terms = serializers.ListField(child=serializers.CharField(), help_text="match: the key terms")
    clues = serializers.ListField(child=serializers.CharField(), help_text="match: the sentences")
    source = serializers.CharField(help_text="e.g. CS 201 · Ch 4: Stacks and Queues")
    chapter_id = serializers.IntegerField()
    course_id = serializers.IntegerField()
    result = CardResultSerializer(allow_null=True, help_text="null until the card is answered")


class AttemptSerializer(serializers.Serializer):
    number = serializers.IntegerField()
    correct = serializers.IntegerField()
    finished = serializers.BooleanField()
    timed_out = serializers.BooleanField()
    expires_at = serializers.DateTimeField(allow_null=True)
    xp = serializers.IntegerField()
    cards = CheckCardSerializer(many=True)


def _source(q: CheckQuestion) -> str:
    return f"{q.chapter.course.code} · Ch {q.chapter.order}: {q.chapter.title}"


def _empty_result(given, q: CheckQuestion) -> dict:
    return {
        "correct": given.correct, "explanation": q.explanation, "source_excerpt": q.source_excerpt,
        "chosen": None, "answer": None, "given_text": None, "expected_text": None,
        "pairs": None, "right_pairs": None,
    }  # fmt: skip


def _card(position: int, item: dict, questions: dict, given) -> dict:
    kind = item.get("kind", "choice")
    if kind == "match":
        qs = [questions[i] for i in item["question_ids"]]
        clue_qs = [questions[i] for i in item["clues"]]
        first = qs[0]
        result = None
        if given:
            result = _empty_result(given, first)
            result["explanation"] = "Each key term goes with the sentence that introduces it."
            result["source_excerpt"] = " ".join(q.explanation for q in qs)[:600]
            result["pairs"] = given.response.get("pairs")
            result["right_pairs"] = [item["clues"].index(i) for i in item["question_ids"]]
        sources = list(dict.fromkeys(_source(q) for q in qs))
        return {
            "position": position, "kind": kind, "type": "matching",
            "front": "Match each key term to the sentence it completes.",
            "options": [], "terms": [q.answer for q in qs], "clues": [q.prompt for q in clue_qs],
            "source": "; ".join(sources), "chapter_id": first.chapter_id,
            "course_id": first.chapter.course_id, "result": result,
        }  # fmt: skip
    q = questions[item["question_id"]]
    result = _empty_result(given, q) if given else None
    options: list[str] = []
    if kind == "choice":
        order = item["order"]
        options = [q.options[i] for i in order]
        if given:
            result["chosen"] = order.index(given.chosen_index)
            result["answer"] = order.index(q.correct_index)
    elif given:
        result["given_text"] = given.response.get("text", "")
        result["expected_text"] = q.answer
    return {
        "position": position, "kind": kind, "type": q.type, "front": q.prompt, "options": options,
        "terms": [], "clues": [], "source": _source(q), "chapter_id": q.chapter_id,
        "course_id": q.chapter.course_id, "result": result,
    }  # fmt: skip


def attempt_data(attempt: CheckAttempt) -> dict:
    """Cards as the student sees them. Answers are only included once a card has been answered."""
    from .services.checks import _question_ids

    ids = [qid for c in attempt.cards for qid in _question_ids(c)]
    questions = {
        q.id: q for q in CheckQuestion.objects.filter(id__in=ids).select_related("chapter__course")
    }
    answers = {a.position: a for a in attempt.answers.all()}
    cards = [_card(i, item, questions, answers.get(i)) for i, item in enumerate(attempt.cards)]
    timed_out = bool(
        attempt.finished_at and attempt.expires_at and attempt.finished_at == attempt.expires_at
    )
    return {
        "number": attempt.number,
        "correct": attempt.correct,
        "finished": attempt.finished_at is not None,
        "timed_out": timed_out,
        "expires_at": attempt.expires_at,
        "xp": attempt.xp,
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
    """Send the field for the card's kind: choice, text or pairs."""

    position = serializers.IntegerField(min_value=0, max_value=9)
    choice = serializers.IntegerField(min_value=0, max_value=3, required=False)
    text = serializers.CharField(max_length=120, required=False, trim_whitespace=True)
    pairs = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=5), max_length=6, required=False
    )


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


class MissedDeadlineSerializer(serializers.Serializer):
    assessment_id = serializers.IntegerField()
    course_id = serializers.IntegerField()
    course_code = serializers.CharField()
    title = serializers.CharField()
    due_at = serializers.DateTimeField()
    late_until = serializers.DateTimeField(allow_null=True)
    streak_result = serializers.ChoiceField(
        choices=["frozen", "missed"], allow_null=True, help_text="what it did to the streak"
    )


class StreakSerializer(serializers.Serializer):
    current = serializers.IntegerField()
    longest = serializers.IntegerField()
    freezes = serializers.IntegerField()
    toward_next_freeze = serializers.IntegerField()
    next_milestone = serializers.IntegerField(allow_null=True)
    week = StreakDaySerializer(many=True)
    recent = StreakEventSerializer(many=True)
    missed_deadlines = MissedDeadlineSerializer(
        many=True,
        help_text="past-due work from the last 7 days; each one counts against the streak",
    )
