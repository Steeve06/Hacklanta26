"""Study checks follow the schedule: a chapter's check opens on the day of its last study session
(or the moment the student completes it early) and closes at the end of the next day. Chapters
studied on the same day share one check."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction

from accounts.clock import now as clock_now
from accounts.models import StudentProfile
from ai.client import available
from lms.models import Chapter, ChapterProgress
from lms.selectors import enrolled_courses
from pulse.models import Schedule, Session

from ..models import StudyCheck
from .bank import needs_cards


def window_for(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    opens = datetime.combine(day, time(0), tzinfo=tz)
    closes = datetime.combine(day + timedelta(days=2), time(0), tzinfo=tz) - timedelta(seconds=1)
    return opens, closes


def _checked_chapter_ids(student) -> set[int]:
    """Chapters that already have a check that is open, passed, or resolved."""
    return set(
        StudyCheck.objects.filter(student=student)
        .exclude(opens_at__gt=clock_now(student), attempts__isnull=True, resolved=False)
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
def sync_checks(student) -> list[StudyCheck]:
    """Create, move or regroup this student's upcoming checks. Open checks never move."""
    # Serialise concurrent syncs for one student (two workers would otherwise both create one).
    StudentProfile.objects.select_for_update().filter(user_id=student.id).first()
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

    pending = StudyCheck.objects.filter(
        student=student, opens_at__gt=now, attempts__isnull=True, resolved=False
    )
    StudyCheck.objects.filter(pk__in=list(pending.values_list("pk", flat=True))).delete()
    taken = _checked_chapter_ids(student)

    groups: dict[tuple[str, date], list[int]] = defaultdict(list)
    for chapter_id, completed_at in completed.items():
        if chapter_id in taken:
            continue
        done_day = completed_at.astimezone(tz).date()
        # The early window runs to the end of the day after completion, so yesterday's still counts.
        if done_day >= today - timedelta(days=1):
            groups[(StudyCheck.Kind.EARLY, done_day)].append(chapter_id)
    for chapter_id, day in study_days.items():
        if chapter_id in taken or chapter_id in completed or day < today:
            continue
        groups[(StudyCheck.Kind.SCHEDULED, day)].append(chapter_id)

    created = []
    for (kind, day), chapter_ids in sorted(groups.items(), key=lambda kv: kv[0][1]):
        if kind == StudyCheck.Kind.EARLY:
            first_completion = min(completed[c] for c in chapter_ids)
            opens = max(first_completion, now)
            closes = window_for(day, tz)[1]
        else:
            opens, closes = window_for(day, tz)
        check = StudyCheck.objects.create(
            student=student, kind=kind, scheduled_date=day, opens_at=opens, closes_at=closes,
            timezone=student.timezone,
        )  # fmt: skip
        check.chapters.set(chapter_ids)
        created.append(check)
    use_ai = available()
    short = [
        c.id
        for c in Chapter.objects.filter(study_checks__in=created).distinct()
        if needs_cards(c, use_ai=use_ai)
    ]
    if short:
        from ..tasks import rebuild_chapter_bank

        for chapter_id in short:
            transaction.on_commit(lambda cid=chapter_id: rebuild_chapter_bank.delay(cid))
    return created
