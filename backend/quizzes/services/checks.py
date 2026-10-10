"""Taking a study check: four cards, one tap each, graded on the server as the student goes.
Three right out of four passes. A failed first try leaves one more try with new cards."""

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.clock import now as clock_now

from ..models import CheckAnswer, CheckAttempt, CheckQuestion, StudyCheck
from .bank import rebuild_bank, usable
from .streaks import GRACE, record_missed, record_pass

MAX_ATTEMPTS = 2
REPEAT_WINDOW = timedelta(days=21)


@dataclass
class AnswerOutcome:
    answer: CheckAnswer
    milestone: int | None


def pass_mark(cards: int) -> int:
    """Right answers needed; scales the 3-of-4 rule down for chapters with tiny banks."""
    share = settings.STUDY_CHECK_PASS_MARK / settings.STUDY_CHECK_CARDS
    return max(1, math.ceil(share * cards - 1e-9))


def in_window(check: StudyCheck, attempt: CheckAttempt | None, now: datetime) -> bool:
    """Server time decides. An attempt started before the close may finish within the grace."""
    if now <= check.closes_at:
        return True
    started_in_time = attempt is not None and attempt.started_at <= check.closes_at
    return started_in_time and now <= check.closes_at + GRACE


def state_of(check: StudyCheck, now: datetime) -> str:
    """upcoming, open, passed, not_passed (tried and didn't pass) or missed (never finished)."""
    if check.passed:
        return "passed"
    if now < check.opens_at:
        return "upcoming"
    attempts = list(check.attempts.all())
    active = next((a for a in attempts if a.finished_at is None), None)
    finished = sum(1 for a in attempts if a.finished_at)
    can_go = active is not None or finished < MAX_ATTEMPTS
    if not check.resolved and can_go and in_window(check, active, now):
        return "open"
    return "not_passed" if finished else "missed"


def _pick(check: StudyCheck, number: int, now: datetime) -> list[dict]:
    rng = random.Random(f"{check.student_id}:{check.id}:{number}")
    seen_here = {
        item["question_id"] for a in check.attempts.all() for item in a.cards
    }  # fmt: skip
    recent = set(
        CheckAnswer.objects.filter(
            attempt__study_check__student_id=check.student_id, created_at__gte=now - REPEAT_WINDOW
        ).values_list("question_id", flat=True)
    )
    pools = []
    for chapter in check.chapters.order_by("course__code", "order"):
        if usable(chapter).count() < settings.STUDY_CHECK_CARDS:
            rebuild_bank(chapter, allow_ai=False)
        pool = list(usable(chapter).order_by("id"))
        rng.shuffle(pool)
        pool.sort(key=lambda q: (q.id in seen_here, q.id in recent))
        pools.append(pool)
    picked: list[CheckQuestion] = []
    while len(picked) < settings.STUDY_CHECK_CARDS and any(pools):
        for pool in pools:
            if pool and len(picked) < settings.STUDY_CHECK_CARDS:
                picked.append(pool.pop(0))
    cards = []
    for q in picked:
        order = list(range(len(q.options)))
        if q.type == CheckQuestion.Type.MULTIPLE_CHOICE:
            rng.shuffle(order)
        cards.append({"question_id": q.id, "order": order})
    return cards


def start_attempt(check: StudyCheck) -> CheckAttempt:
    """Return the try in progress, or start the next one."""
    with transaction.atomic():
        check = StudyCheck.objects.select_for_update().get(pk=check.pk)
        now = clock_now(check.student)
        active = check.attempts.filter(finished_at__isnull=True).first()
        if active:
            return active
        if check.passed:
            raise ValidationError("You already passed this check.")
        if now < check.opens_at:
            raise ValidationError("This check isn't open yet.")
        if check.resolved or now > check.closes_at:
            raise ValidationError("This check has closed.")
        number = check.attempts.count() + 1
        if number > MAX_ATTEMPTS:
            raise ValidationError("You've used both tries on this check.")
        cards = _pick(check, number, now)
        if not cards:
            raise ValidationError("This chapter doesn't have cards yet. Try again in a minute.")
        return CheckAttempt.objects.create(
            study_check=check, number=number, cards=cards, started_at=now
        )


def answer(check: StudyCheck, position: int, choice: int) -> AnswerOutcome:
    """Record the option the student tapped (`choice` is its position as shown). Sending the same
    card again returns the first answer unchanged."""
    with transaction.atomic():
        attempt = (
            CheckAttempt.objects.select_for_update()
            .filter(study_check=check)
            .order_by("-number")
            .first()
        )
        if attempt is None:
            raise ValidationError("Start the check first.")
        existing = attempt.answers.filter(position=position).first()
        if existing:
            return AnswerOutcome(existing, None)
        if attempt.finished_at:
            raise ValidationError("This try is finished.")
        if position != attempt.answers.count() or not 0 <= position < len(attempt.cards):
            raise ValidationError("Answer the cards in order.")
        now = clock_now(check.student)
        if not in_window(check, attempt, now):
            raise ValidationError("This check has closed.")
        since = attempt.last_answer_at or attempt.started_at
        if (now - since).total_seconds() < settings.STUDY_CHECK_SECONDS_PER_CARD:
            raise ValidationError("Take a moment to read the card first.")
        item = attempt.cards[position]
        question = CheckQuestion.objects.get(pk=item["question_id"])
        if not 0 <= choice < len(item["order"]):
            raise ValidationError("Pick one of the options.")
        original = item["order"][choice]
        given = CheckAnswer.objects.create(
            attempt=attempt,
            position=position,
            question=question,
            chosen_index=original,
            correct=original == question.correct_index,
        )
        attempt.last_answer_at = now
        attempt.correct += given.correct
        if position + 1 == len(attempt.cards):
            attempt.finished_at = now
        attempt.save()
        milestone = _finish(check, attempt, now) if attempt.finished_at else None
    return AnswerOutcome(given, milestone)


def _finish(check: StudyCheck, attempt: CheckAttempt, now: datetime) -> int | None:
    check = StudyCheck.objects.select_for_update().get(pk=check.pk)
    if attempt.correct >= pass_mark(len(attempt.cards)):
        counted = in_window(check, attempt, now)
        check.passed = True
        check.counted_for_streak = counted
        check.resolved = True
        check.save(update_fields=["passed", "counted_for_streak", "resolved", "updated_at"])
        if counted:
            return record_pass(check)[1]
        record_missed(check)
    elif attempt.number >= MAX_ATTEMPTS:
        record_missed(check)
    return None
