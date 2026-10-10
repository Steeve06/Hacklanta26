"""Quiz windows follow the schedule: a chapter's quiz opens on the day of its last study session
(or the moment the student completes it early) and closes at the end of the next day."""

import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction

from accounts.clock import now as clock_now
from lms.models import Chapter, ChapterProgress
from lms.selectors import enrolled_courses
from pulse.models import Schedule, Session

from ..models import BankQuestion, ChapterQuiz, ChapterQuizAnswer
from .bank import rebuild_bank, usable

PER_CHAPTER = 5
MAX_QUESTIONS = 10
REPEAT_WINDOW = timedelta(days=21)


def window_for(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    opens = datetime.combine(day, time(0), tzinfo=tz)
    closes = datetime.combine(day + timedelta(days=2), time(0), tzinfo=tz) - timedelta(seconds=1)
    return opens, closes


def _quizzed_chapter_ids(student) -> set[int]:
    """Chapters that already have a quiz that is open, finished, or resolved."""
    return set(
        ChapterQuiz.objects.filter(student=student)
        .exclude(opens_at__gt=clock_now(student), submitted_at__isnull=True, resolved=False)
        .values_list("chapters__id", flat=True)
    )


def _study_days(schedule: Schedule | None, tz) -> dict[int, date]:
    if schedule is None:
        return {}
    days: dict[int, date] = {}
    sessions = (
        schedule.sessions.filter(task__source_type="chapter", kind=Session.Kind.STUDY)
        .exclude(status__in=[Session.Status.SKIPPED, Session.Status.RESCHEDULED])
        .select_related("task")
    )
    for s in sessions:
        local = s.start.astimezone(tz).date()
        days[s.task.source_id] = max(days.get(s.task.source_id, local), local)
    return days


@transaction.atomic
def sync_windows(student) -> list[ChapterQuiz]:
    """Create, move or regroup this student's upcoming quiz windows. Open windows never move."""
    now = clock_now(student)
    tz = student.tz
    today = now.astimezone(tz).date()
    chapters = Chapter.objects.filter(course__in=enrolled_courses(student))
    completed = {
        p.chapter_id: p.completed_at
        for p in ChapterProgress.objects.filter(
            student=student, chapter__in=chapters, completed_at__isnull=False
        )
    }
    schedule = Schedule.objects.filter(student=student, is_active=True).first()
    study_days = _study_days(schedule, tz)

    pending = ChapterQuiz.objects.filter(
        student=student, opens_at__gt=now, submitted_at__isnull=True, resolved=False
    )
    pending.delete()
    taken = _quizzed_chapter_ids(student)

    groups: dict[tuple[str, date], list[int]] = defaultdict(list)
    for chapter_id, completed_at in completed.items():
        if chapter_id in taken:
            continue
        done_day = completed_at.astimezone(tz).date()
        if done_day >= today:
            groups[(ChapterQuiz.Kind.EARLY, done_day)].append(chapter_id)
    for chapter_id, day in study_days.items():
        if chapter_id in taken or chapter_id in completed or day < today:
            continue
        groups[(ChapterQuiz.Kind.SCHEDULED, day)].append(chapter_id)

    created = []
    for (kind, day), chapter_ids in sorted(groups.items(), key=lambda kv: kv[0][1]):
        if kind == ChapterQuiz.Kind.EARLY:
            first_completion = min(completed[c] for c in chapter_ids)
            opens = max(first_completion, now)
            closes = window_for(day, tz)[1]
        else:
            opens, closes = window_for(day, tz)
        quiz = ChapterQuiz.objects.create(
            student=student, kind=kind, scheduled_date=day, opens_at=opens, closes_at=closes,
            timezone=student.timezone,
        )  # fmt: skip
        quiz.chapters.set(chapter_ids)
        assemble(quiz)
        created.append(quiz)
    return created


def assemble(quiz: ChapterQuiz, rng: random.Random | None = None) -> None:
    """Pick questions from each chapter's bank now, so opening the quiz needs no model call."""
    rng = rng or random.Random(f"{quiz.student_id}:{quiz.id}")
    chapters = list(quiz.chapters.all())
    per_chapter = max(1, min(PER_CHAPTER, MAX_QUESTIONS // max(1, len(chapters))))
    recent = set(
        ChapterQuizAnswer.objects.filter(
            quiz__student=quiz.student, created_at__gte=clock_now(quiz.student) - REPEAT_WINDOW
        ).values_list("question_id", flat=True)
    )
    picked: list[dict] = []
    for chapter in chapters:
        pool = list(usable(chapter))
        if len(pool) < per_chapter:
            rebuild_bank(chapter)
            pool = list(usable(chapter))
        fresh = [q for q in pool if q.id not in recent] or pool
        rng.shuffle(fresh)
        for q in fresh[:per_chapter]:
            order = list(range(len(q.options)))
            if q.type == BankQuestion.Type.MULTIPLE_CHOICE:
                rng.shuffle(order)
            picked.append({"bank_id": q.id, "order": order})
    quiz.questions = picked[:MAX_QUESTIONS]
    quiz.save(update_fields=["questions", "updated_at"])
