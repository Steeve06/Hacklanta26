"""Student and instructor actions in Learning Hub."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from accounts.clock import now as clock_now

from .models import (
    Assessment,
    Chapter,
    ChapterProgress,
    DiscussionPost,
    DueDateOverride,
    QuizAttempt,
    Submission,
)
from .signals import emit_change
from .status import deadline_for, load_state, status_for

S = Submission.Status
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOADS = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    ".zip": {"application/zip", "application/x-zip-compressed", "application/octet-stream"},
}
FILE_SIGNATURES = {".pdf": b"%PDF", ".docx": b"PK\x03\x04", ".zip": b"PK\x03\x04"}


def open_chapter(student, chapter: Chapter) -> ChapterProgress:
    progress, _ = ChapterProgress.objects.get_or_create(student=student, chapter=chapter)
    if progress.first_opened_at is None:
        progress.first_opened_at = clock_now(student)
        progress.save(update_fields=["first_opened_at", "updated_at"])
        emit_change([student.id], "chapter_opened", chapter_id=chapter.id)
    return progress


def complete_chapter(student, chapter: Chapter) -> ChapterProgress:
    current = clock_now(student)
    if chapter.available_from > current:
        raise ValidationError("This chapter is still locked.")
    progress, _ = ChapterProgress.objects.get_or_create(student=student, chapter=chapter)
    if progress.completed_at is None:
        progress.first_opened_at = progress.first_opened_at or current
        progress.completed_at = current
        progress.save()
        emit_change([student.id], "chapter_completed", chapter_id=chapter.id)
    return progress


def _check_open(assessment: Assessment, current) -> None:
    if current < assessment.open_at:
        raise ValidationError("This assignment isn't open yet.")


def validate_upload(upload) -> None:
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError({"file": "Files must be 10 MB or smaller."})
    ext = Path(upload.name).suffix.lower()
    if ext not in ALLOWED_UPLOADS:
        raise ValidationError({"file": "Upload a PDF, DOCX or ZIP file."})
    content_type = (upload.content_type or "").split(";")[0].strip()
    if content_type and content_type not in ALLOWED_UPLOADS[ext]:
        raise ValidationError({"file": "The file type doesn't match its extension."})
    head = upload.read(4)
    upload.seek(0)
    if not head.startswith(FILE_SIGNATURES[ext]):
        raise ValidationError({"file": "The file looks damaged or isn't really a " + ext + "."})


def submit_homework(student, assessment: Assessment, *, text: str = "", upload=None) -> Submission:
    if assessment.type != Assessment.Type.HOMEWORK:
        raise ValidationError("Only homework takes file or text submissions.")
    if not text.strip() and upload is None:
        raise ValidationError({"text": "Add a text answer or attach a file."})
    if upload is not None:
        validate_upload(upload)
    current = clock_now(student)
    _check_open(assessment, current)
    state = load_state(student, [assessment.id])
    deadline = deadline_for(assessment, state)
    status = status_for(assessment, state, current)
    if status == S.EXCUSED:
        raise ValidationError("You've been excused from this assignment.")
    if current > deadline.closes_at:
        raise ValidationError(
            "The late window for this assignment has closed, so it can't be submitted."
        )
    previous = state.latest.get(assessment.id)
    late = current > deadline.due_at
    if previous and previous.status in (S.SUBMITTED, S.LATE, S.GRADED) and late:
        raise ValidationError("Resubmissions are only allowed until the due date.")
    with transaction.atomic():
        submission = Submission.objects.create(
            assessment=assessment,
            student=student,
            status=S.LATE if late else S.SUBMITTED,
            text=text,
            file=upload or "",
            submitted_at=current,
            attempt_no=(previous.attempt_no + 1) if previous else 1,
        )
    emit_change([student.id], "submission", assessment_id=assessment.id)
    return submission


def add_discussion_post(student, assessment: Assessment, body: str, parent_id=None):
    if assessment.type != Assessment.Type.DISCUSSION:
        raise ValidationError("Posts are only for discussions.")
    if not body.strip():
        raise ValidationError({"body": "Write something before posting."})
    current = clock_now(student)
    _check_open(assessment, current)
    state = load_state(student, [assessment.id])
    if current > deadline_for(assessment, state).closes_at:
        raise ValidationError("This discussion is closed.")
    parent = None
    if parent_id is not None:
        parent = DiscussionPost.objects.filter(pk=parent_id, assessment=assessment).first()
        if parent is None:
            raise ValidationError({"parent": "That post no longer exists."})
    post = DiscussionPost.objects.create(
        assessment=assessment, author=student, parent=parent, body=body.strip()
    )
    _complete_discussion_if_met(student, assessment, current)
    emit_change([student.id], "discussion_post", assessment_id=assessment.id)
    return post


def discussion_progress(student, assessment: Assessment) -> dict:
    state = load_state(student, [assessment.id])
    return {
        "original_posted": state.originals.get(assessment.id, 0) > 0,
        "replies_made": state.replies.get(assessment.id, 0),
        "replies_required": assessment.discussion_replies_required,
    }


def _complete_discussion_if_met(student, assessment: Assessment, current) -> None:
    state = load_state(student, [assessment.id])
    met = (
        state.originals.get(assessment.id, 0) >= 1
        and state.replies.get(assessment.id, 0) >= assessment.discussion_replies_required
    )
    if not met or assessment.id in state.latest:
        return
    late = current > deadline_for(assessment, state).due_at
    Submission.objects.create(
        assessment=assessment,
        student=student,
        status=S.LATE if late else S.SUBMITTED,
        submitted_at=current,
    )


def start_quiz(student, assessment: Assessment) -> QuizAttempt:
    if assessment.type != Assessment.Type.QUIZ:
        raise ValidationError("This assignment isn't a quiz.")
    current = clock_now(student)
    _check_open(assessment, current)
    finalize_expired_attempts(student, assessment)
    state = load_state(student, [assessment.id])
    deadline = deadline_for(assessment, state)
    if state.latest.get(assessment.id) and state.latest[assessment.id].status == S.EXCUSED:
        raise ValidationError("You've been excused from this quiz.")
    if current > deadline.closes_at:
        raise ValidationError("This quiz has closed.")
    existing = QuizAttempt.objects.filter(
        student=student, assessment=assessment, submitted_at__isnull=True
    ).first()
    if existing:
        return existing
    used = state.attempts_used.get(assessment.id, 0)
    if used >= assessment.max_attempts:
        raise ValidationError("You've used all your attempts for this quiz.")
    limit_end = current + timedelta(minutes=assessment.time_limit_minutes)
    try:
        attempt = QuizAttempt.objects.create(
            assessment=assessment,
            student=student,
            attempt_no=used + 1,
            started_at=current,
            deadline_at=min(limit_end, deadline.closes_at),
        )
    except IntegrityError:
        attempt = QuizAttempt.objects.get(
            assessment=assessment, student=student, attempt_no=used + 1
        )
    emit_change([student.id], "quiz_started", assessment_id=assessment.id)
    return attempt


def save_quiz_answers(attempt: QuizAttempt, answers: dict) -> QuizAttempt:
    if attempt.submitted_at is not None:
        return attempt
    if clock_now(attempt.student) > attempt.deadline_at:
        return finalize_attempt(attempt, auto=True)
    attempt.answers = {**attempt.answers, **_clean_answers(attempt, answers)}
    attempt.save(update_fields=["answers", "updated_at"])
    return attempt


def _clean_answers(attempt: QuizAttempt, answers: dict) -> dict:
    valid = {str(q.id): len(q.options) for q in attempt.assessment.questions.all()}
    cleaned = {}
    for key, value in answers.items():
        key = str(key)
        if key in valid and isinstance(value, int) and 0 <= value < valid[key]:
            cleaned[key] = value
    return cleaned


def submit_quiz(attempt: QuizAttempt, answers: dict) -> QuizAttempt:
    if attempt.submitted_at is not None:
        return attempt
    current = clock_now(attempt.student)
    if current > attempt.deadline_at:
        return finalize_attempt(attempt, auto=True)
    attempt.answers = {**attempt.answers, **_clean_answers(attempt, answers)}
    attempt.save(update_fields=["answers", "updated_at"])
    return finalize_attempt(attempt, auto=False)


@transaction.atomic
def finalize_attempt(attempt: QuizAttempt, *, auto: bool) -> QuizAttempt:
    attempt = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
    if attempt.submitted_at is not None:
        return attempt
    questions = list(attempt.assessment.questions.all())
    total = sum(q.points for q in questions) or 1
    earned = sum(q.points for q in questions if attempt.answers.get(str(q.id)) == q.correct_index)
    score = (Decimal(earned) / Decimal(total) * attempt.assessment.points).quantize(Decimal("0.01"))
    attempt.submitted_at = (
        min(clock_now(attempt.student), attempt.deadline_at)
        if auto
        else (clock_now(attempt.student))
    )
    attempt.score = score
    attempt.auto_submitted = auto
    attempt.save()
    state = load_state(attempt.student, [attempt.assessment_id])
    late = attempt.submitted_at > deadline_for(attempt.assessment, state).due_at
    best = Submission.objects.filter(student=attempt.student, assessment=attempt.assessment).first()
    if best is None or (best.score or 0) <= score:
        Submission.objects.create(
            assessment=attempt.assessment,
            student=attempt.student,
            status=S.LATE if late else S.SUBMITTED,
            submitted_at=attempt.submitted_at,
            score=score,
            attempt_no=attempt.attempt_no,
        )
    emit_change([attempt.student_id], "submission", assessment_id=attempt.assessment_id)
    return attempt


def finalize_expired_attempts(student=None, assessment=None) -> int:
    qs = QuizAttempt.objects.filter(submitted_at__isnull=True).select_related(
        "assessment", "student"
    )
    if student is not None:
        qs = qs.filter(student=student)
    if assessment is not None:
        qs = qs.filter(assessment=assessment)
    count = 0
    for attempt in qs:
        if clock_now(attempt.student) > attempt.deadline_at:
            finalize_attempt(attempt, auto=True)
            count += 1
    return count


def set_override(assessment: Assessment, student, due_at, cutoff_at=None, reason=""):
    if cutoff_at and cutoff_at < due_at:
        raise ValidationError({"cutoff_at": "The late cut-off must be after the new due date."})
    override, _ = DueDateOverride.objects.update_or_create(
        assessment=assessment,
        student=student,
        defaults={"due_at": due_at, "cutoff_at": cutoff_at, "reason": reason},
    )
    emit_change([student.id], "override", assessment_id=assessment.id)
    return override


def set_excused(assessment: Assessment, student, excused: bool) -> None:
    latest = Submission.objects.filter(assessment=assessment, student=student).first()
    if excused and (latest is None or latest.status != S.EXCUSED):
        Submission.objects.create(
            assessment=assessment,
            student=student,
            status=S.EXCUSED,
            attempt_no=(latest.attempt_no + 1) if latest else 1,
        )
    elif not excused and latest is not None and latest.status == S.EXCUSED:
        latest.delete()
    emit_change([student.id], "excused", assessment_id=assessment.id)


def grade(submission: Submission, score) -> Submission:
    if score is not None and (score < 0 or score > submission.assessment.points):
        raise ValidationError(
            {"score": f"Score must be between 0 and {submission.assessment.points}."}
        )
    submission.score = score
    submission.save(update_fields=["score", "updated_at"])
    return submission
