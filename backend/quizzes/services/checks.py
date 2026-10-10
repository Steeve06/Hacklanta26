"""Taking a study check: four cards in a timed try, graded on the server as the student goes.
Cards mix multiple choice, true/false, short answer and one matching card. Three right out of four
passes. A failed first try leaves one more try with new cards. Each try earns XP for the weekly
leaderboard."""

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.clock import now as clock_now

from ..models import CheckAnswer, CheckAttempt, CheckQuestion, StudyCheck
from .bank import choices, rebuild_bank, usable
from .grading import close_enough
from .streaks import GRACE, record_missed, record_pass

MAX_ATTEMPTS = 2
REPEAT_WINDOW = timedelta(days=21)
LATENCY = timedelta(seconds=10)
MATCH_PAIRS = 3
MATCH_AT = 2
XP_PER_CORRECT = 10
XP_FOR_FINISHING = 20


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


def _question_ids(card: dict) -> list[int]:
    return card["question_ids"] if card.get("kind") == "match" else [card["question_id"]]


def _recently_seen(check: StudyCheck, now: datetime) -> set[int]:
    attempts = CheckAttempt.objects.filter(
        study_check__student_id=check.student_id, started_at__gte=now - REPEAT_WINDOW
    ).values_list("cards", flat=True)
    return {qid for cards in attempts for card in cards for qid in _question_ids(card)}


def _round_robin(pools: list[list[CheckQuestion]], count: int) -> list[CheckQuestion]:
    picked: list[CheckQuestion] = []
    while len(picked) < count and any(pools):
        for pool in pools:
            if pool and len(picked) < count:
                picked.append(pool.pop(0))
    return picked


def _pick(check: StudyCheck, number: int, now: datetime) -> list[dict]:
    """Four cards spread over the check's chapters: one matching card (three key terms) when the
    chapters have enough, one short answer, and option questions for the rest. Questions this
    student saw recently go last."""
    rng = random.Random(f"{check.student_id}:{check.id}:{number}")
    seen_here = {qid for a in check.attempts.all() for c in a.cards for qid in _question_ids(c)}
    recent = _recently_seen(check, now)
    option_pools, term_pools = [], []
    for chapter in check.chapters.order_by("course__code", "order"):
        if choices(chapter).count() < settings.STUDY_CHECK_CARDS:
            rebuild_bank(chapter, allow_ai=False)
        for pools, qs in (
            (option_pools, choices(chapter)),
            (term_pools, usable(chapter).filter(type=CheckQuestion.Type.SHORT_ANSWER)),
        ):
            pool = list(qs.order_by("id"))
            rng.shuffle(pool)
            pool.sort(key=lambda q: (q.id in seen_here, q.id in recent))
            pools.append(pool)
    # A retry gets new cards: leave out this check's earlier cards while enough others remain.
    fresh = sum(1 for p in option_pools + term_pools for q in p if q.id not in seen_here)
    if seen_here and fresh >= settings.STUDY_CHECK_CARDS:
        option_pools = [[q for q in p if q.id not in seen_here] for p in option_pools]
        term_pools = [[q for q in p if q.id not in seen_here] for p in term_pools]

    size = settings.STUDY_CHECK_CARDS
    cards: list[dict] = []
    match = None
    if sum(len(p) for p in term_pools) >= MATCH_PAIRS + 1 and size >= 3:
        group = _round_robin(term_pools, MATCH_PAIRS)
        clues = [q.id for q in group]
        rng.shuffle(clues)
        match = {"kind": "match", "question_ids": [q.id for q in group], "clues": clues}
    short = _round_robin(term_pools, 1)
    for q in short:
        cards.append({"kind": "short", "question_id": q.id})
    room = size - len(cards) - (1 if match else 0)
    for q in _round_robin(option_pools, room):
        order = list(range(len(q.options)))
        if q.type == CheckQuestion.Type.MULTIPLE_CHOICE:
            rng.shuffle(order)
        cards.append({"kind": "choice", "question_id": q.id, "order": order})
    room = size - len(cards) - (1 if match else 0)
    cards += [{"kind": "short", "question_id": q.id} for q in _round_robin(term_pools, room)]
    rng.shuffle(cards)
    if match:
        cards.insert(min(MATCH_AT, len(cards)), match)
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
            study_check=check, number=number, cards=cards, started_at=now,
            expires_at=now + timedelta(seconds=settings.STUDY_CHECK_TIME_LIMIT),
        )  # fmt: skip


def _grade(card: dict, response: dict) -> tuple[bool, CheckQuestion, int | None, dict]:
    """Whether the card is right, the question to file the answer under, the original option
    index (choice cards) and what to store."""
    kind = card.get("kind", "choice")
    if kind == "match":
        pairs = response.get("pairs")
        ids = card["question_ids"]
        if not isinstance(pairs, list) or sorted(pairs) != list(range(len(ids))):
            raise ValidationError("Match every term to one sentence.")
        right = all(card["clues"][pairs[i]] == qid for i, qid in enumerate(ids))
        return right, CheckQuestion.objects.get(pk=ids[0]), None, {"pairs": pairs}
    question = CheckQuestion.objects.get(pk=card["question_id"])
    if kind == "short":
        text = response.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("Type an answer.")
        return close_enough(text[:120], question.answer), question, None, {"text": text[:120]}
    choice = response.get("choice")
    if not isinstance(choice, int) or not 0 <= choice < len(card["order"]):
        raise ValidationError("Pick one of the options.")
    original = card["order"][choice]
    return original == question.correct_index, question, original, {}


def time_left(attempt: CheckAttempt, now: datetime) -> timedelta | None:
    return None if attempt.expires_at is None else attempt.expires_at - now


def settle_expired(check: StudyCheck, now: datetime) -> bool:
    """Finish a try whose clock ran out (plus a little for network delay). Cards left unanswered
    count as wrong."""
    with transaction.atomic():
        attempt = (
            CheckAttempt.objects.select_for_update()
            .filter(study_check=check, finished_at__isnull=True, expires_at__lt=now - LATENCY)
            .first()
        )
        if attempt is None:
            return False
        attempt.finished_at = attempt.expires_at
        attempt.xp = XP_PER_CORRECT * attempt.correct
        attempt.save(update_fields=["finished_at", "xp", "updated_at"])
        _finish(check, attempt, attempt.expires_at)
    return True


def answer(check: StudyCheck, position: int, response: dict) -> AnswerOutcome:
    """Record the answer to one card: {choice} for options (as shown), {text} for a short answer,
    {pairs} for matching (pairs[i] is the sentence picked for term i). Sending the same card again
    returns the first answer unchanged."""
    now = clock_now(check.student)
    settle_expired(check, now)
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
            raise ValidationError("Time's up for this try." if attempt.expires_at
                                  and attempt.finished_at == attempt.expires_at
                                  else "This try is finished.")  # fmt: skip
        if position != attempt.answers.count() or not 0 <= position < len(attempt.cards):
            raise ValidationError("Answer the cards in order.")
        if not in_window(check, attempt, now):
            raise ValidationError("This check has closed.")
        since = attempt.last_answer_at or attempt.started_at
        if (now - since).total_seconds() < settings.STUDY_CHECK_SECONDS_PER_CARD:
            raise ValidationError("Take a moment to read the card first.")
        right, question, original, stored = _grade(attempt.cards[position], response)
        given = CheckAnswer.objects.create(
            attempt=attempt, position=position, question=question,
            chosen_index=original, response=stored, correct=right,
        )  # fmt: skip
        attempt.last_answer_at = now
        attempt.correct += given.correct
        if position + 1 == len(attempt.cards):
            attempt.finished_at = now
            attempt.xp = XP_PER_CORRECT * attempt.correct + XP_FOR_FINISHING
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
