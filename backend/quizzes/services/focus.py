"""What today's deck is about: the next quiz (or other deadline) coming up in the student's
courses, or a review of their course chapters when nothing is due soon."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from lms.models import Chapter
from lms.selectors import student_snapshot

from ..models import DailyDeck
from . import chapter_cards
from .cards import general_ids

UPCOMING_WINDOW = timedelta(days=7)


@dataclass
class Focus:
    kind: str
    course_id: int | None = None
    assessment_id: int | None = None
    assessment_type: str | None = None
    pools: list[list[int]] = field(default_factory=list)


def _cards_for(chapter_ids) -> list[int]:
    ids: list[int] = []
    for chapter in Chapter.objects.filter(id__in=chapter_ids).order_by("course_id", "order"):
        ids += chapter_cards.ensure(chapter)
    return ids


def choose(student, now: datetime) -> Focus:
    snapshot = student_snapshot(student, now)
    released = [c for c in snapshot.chapters if c.available_from <= now]
    upcoming = sorted(
        (
            a for a in snapshot.assessments
            if a.chapter_ids and not a.done and now < a.due_at <= now + UPCOMING_WINDOW
        ),
        key=lambda a: (a.type != "quiz", a.due_at),
    )  # fmt: skip
    for target in upcoming:
        prep = _cards_for(target.chapter_ids)
        if not prep:
            continue
        same_course = _cards_for([c.id for c in released if c.course_id == target.course_id])
        return Focus(
            DailyDeck.Kind.UPCOMING, target.course_id, target.id, target.type,
            [prep, same_course, general_ids()],
        )  # fmt: skip
    # Chapters the student has opened come first; anything released fills in.
    touched = [c.id for c in released if c.completed_at or c.opened_at]
    review = _cards_for(touched) + _cards_for([c.id for c in released if c.id not in touched])
    if review:
        return Focus(DailyDeck.Kind.REVIEW, pools=[review, general_ids()])
    return Focus(DailyDeck.Kind.GENERAL, pools=[general_ids()])
