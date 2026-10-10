"""Per-student assessment state: effective deadlines and status."""

from dataclasses import dataclass, field
from datetime import datetime

from django.db.models import Count, Q

from .models import Assessment, DiscussionPost, DueDateOverride, QuizAttempt, Submission

S = Submission.Status


@dataclass
class StudentState:
    latest: dict[int, Submission] = field(default_factory=dict)
    overrides: dict[int, DueDateOverride] = field(default_factory=dict)
    originals: dict[int, int] = field(default_factory=dict)
    replies: dict[int, int] = field(default_factory=dict)
    open_attempts: set[int] = field(default_factory=set)
    attempts_used: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Deadline:
    due_at: datetime
    cutoff_at: datetime | None
    extended: bool

    @property
    def closes_at(self) -> datetime:
        return self.cutoff_at or self.due_at


def load_state(student, assessment_ids) -> StudentState:
    ids = list(assessment_ids)
    state = StudentState()
    for sub in Submission.objects.filter(student=student, assessment_id__in=ids).order_by(
        "assessment_id", "-attempt_no", "-id"
    ):
        state.latest.setdefault(sub.assessment_id, sub)
    for override in DueDateOverride.objects.filter(student=student, assessment_id__in=ids):
        state.overrides[override.assessment_id] = override
    post_counts = (
        DiscussionPost.objects.filter(author=student, assessment_id__in=ids)
        .values("assessment_id")
        .annotate(
            originals=Count("id", filter=Q(parent__isnull=True)),
            replies=Count("id", filter=Q(parent__isnull=False) & ~Q(parent__author=student)),
        )
    )
    for row in post_counts:
        state.originals[row["assessment_id"]] = row["originals"]
        state.replies[row["assessment_id"]] = row["replies"]
    for attempt in QuizAttempt.objects.filter(student=student, assessment_id__in=ids).only(
        "assessment_id", "submitted_at"
    ):
        state.attempts_used[attempt.assessment_id] = (
            state.attempts_used.get(attempt.assessment_id, 0) + 1
        )
        if attempt.submitted_at is None:
            state.open_attempts.add(attempt.assessment_id)
    return state


def deadline_for(assessment: Assessment, state: StudentState) -> Deadline:
    override = state.overrides.get(assessment.id)
    if override:
        return Deadline(override.due_at, override.cutoff_at, extended=True)
    return Deadline(assessment.due_at, assessment.cutoff_at, extended=False)


def status_for(assessment: Assessment, state: StudentState, now: datetime) -> str:
    latest = state.latest.get(assessment.id)
    if latest is not None:
        if latest.status == S.EXCUSED:
            return S.EXCUSED
        if latest.score is not None:
            return S.GRADED
        if latest.status in (S.SUBMITTED, S.LATE):
            return latest.status
    started = (
        state.originals.get(assessment.id, 0) > 0
        or state.replies.get(assessment.id, 0) > 0
        or assessment.id in state.open_attempts
    )
    if now > deadline_for(assessment, state).closes_at:
        return S.MISSED
    return S.IN_PROGRESS if started else S.NOT_STARTED


def is_done(status: str) -> bool:
    return status in (S.SUBMITTED, S.LATE, S.GRADED, S.EXCUSED)
