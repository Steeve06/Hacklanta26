"""Taking a chapter quiz: start, submit (idempotent), grade on the server."""

from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.clock import now as clock_now

from ..models import BankQuestion, ChapterQuiz, ChapterQuizAnswer
from .streaks import GRACE, record_on_time

MIN_SECONDS = 20


@dataclass
class SubmitOutcome:
    quiz: ChapterQuiz
    milestone: int | None


def state_of(quiz: ChapterQuiz, now) -> str:
    if quiz.submitted_at:
        return "done"
    if now < quiz.opens_at:
        return "upcoming"
    if now <= quiz.closes_at:
        return "open"
    return "closed"


def start(quiz: ChapterQuiz) -> ChapterQuiz:
    now = clock_now(quiz.student)
    if now < quiz.opens_at:
        raise ValidationError("This quiz isn't open yet.")
    if quiz.started_at is None:
        ChapterQuiz.objects.filter(pk=quiz.pk, started_at__isnull=True).update(started_at=now)
        quiz.refresh_from_db()
    return quiz


def counts_for_streak(quiz: ChapterQuiz, submitted_at) -> bool:
    if submitted_at <= quiz.closes_at:
        return True
    started_in_window = quiz.started_at is not None and quiz.started_at <= quiz.closes_at
    return started_in_window and submitted_at <= quiz.closes_at + GRACE


def submit(quiz: ChapterQuiz, displayed_answers: dict[str, int]) -> SubmitOutcome:
    """`displayed_answers` maps question position (as a string) to the option index the student
    saw. Resubmitting returns the first result unchanged."""
    with transaction.atomic():
        quiz = ChapterQuiz.objects.select_for_update().get(pk=quiz.pk)
        if quiz.submitted_at is not None:
            return SubmitOutcome(quiz, None)
        now = clock_now(quiz.student)
        if quiz.started_at is None:
            raise ValidationError("Start the quiz before submitting it.")
        if (now - quiz.started_at).total_seconds() < MIN_SECONDS:
            raise ValidationError("That was quick. Take a little longer to read the questions.")
        bank = {
            q.id: q
            for q in BankQuestion.objects.filter(id__in=[i["bank_id"] for i in quiz.questions])
        }
        answered = 0
        correct = 0
        rows = []
        for position, item in enumerate(quiz.questions):
            question = bank.get(item["bank_id"])
            shown = displayed_answers.get(str(position))
            if question is None or shown is None or not 0 <= shown < len(item["order"]):
                continue
            original = item["order"][shown]
            answered += 1
            is_correct = original == question.correct_index
            correct += is_correct
            rows.append(
                ChapterQuizAnswer(
                    quiz=quiz, question=question, chosen_index=original, correct=is_correct
                )
            )
        if answered < len(quiz.questions):
            raise ValidationError("Answer every question before submitting.")
        ChapterQuizAnswer.objects.bulk_create(rows)
        quiz.submitted_at = now
        quiz.score = correct / max(1, len(quiz.questions))
        quiz.sharp = quiz.score >= settings.QUIZ_SHARP_THRESHOLD
        quiz.counted_for_streak = counts_for_streak(quiz, now)
        quiz.resolved = quiz.counted_for_streak
        quiz.save()
    milestone = None
    if quiz.counted_for_streak:
        _, milestone = record_on_time(quiz)
    return SubmitOutcome(quiz, milestone)
