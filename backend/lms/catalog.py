"""Course-level data every student in a course shares, cached and invalidated on any change."""

from dataclasses import dataclass
from datetime import date, datetime

from django.core.cache import cache
from django.db.models import Prefetch
from django.db.models.signals import m2m_changed, post_delete, post_save

from .models import Assessment, Chapter, Course, SyllabusWeek

CACHE_SECONDS = 60 * 30
KEY = "lms:catalog:v1:{}"


@dataclass(frozen=True)
class ChapterRow:
    id: int
    course_id: int
    order: int
    title: str
    reading_minutes: int
    objectives: tuple[str, ...]
    available_from: datetime
    content_hash: str
    week_number: int | None
    week_start: date | None


@dataclass(frozen=True)
class CourseCatalog:
    chapters: tuple[ChapterRow, ...]
    assessments: tuple[Assessment, ...]
    chapter_ids: dict[int, tuple[int, ...]]


def catalogs(course_ids) -> dict[int, CourseCatalog]:
    ids = list(course_ids)
    found = cache.get_many([KEY.format(i) for i in ids])
    result = {i: found[KEY.format(i)] for i in ids if KEY.format(i) in found}
    missing = [i for i in ids if i not in result]
    if missing:
        built = _build(missing)
        cache.set_many({KEY.format(i): c for i, c in built.items()}, CACHE_SECONDS)
        result.update(built)
    return result


def invalidate(course_id: int) -> None:
    cache.delete(KEY.format(course_id))


def invalidate_all() -> None:
    cache.delete_many([KEY.format(i) for i in Course.objects.values_list("id", flat=True)])


def _build(course_ids: list[int]) -> dict[int, CourseCatalog]:
    chapters = (
        Chapter.objects.filter(course_id__in=course_ids)
        .only(
            "id",
            "course_id",
            "order",
            "title",
            "reading_minutes",
            "objectives",
            "available_from",
            "content_hash",
        )  # fmt: skip
        .prefetch_related(
            Prefetch(
                "syllabus_weeks",
                queryset=SyllabusWeek.objects.only("id", "week_number", "start_date"),
            )
        )
    )
    assessments = Assessment.objects.filter(course_id__in=course_ids, published=True)
    links = Assessment.chapters.through.objects.filter(
        assessment__course_id__in=course_ids
    ).values_list("assessment_id", "chapter_id")

    rows: dict[int, list[ChapterRow]] = {i: [] for i in course_ids}
    for ch in chapters:
        week = min(ch.syllabus_weeks.all(), key=lambda w: w.week_number, default=None)
        rows[ch.course_id].append(
            ChapterRow(
                id=ch.id,
                course_id=ch.course_id,
                order=ch.order,
                title=ch.title,
                reading_minutes=ch.reading_minutes,
                objectives=tuple(ch.objectives),
                available_from=ch.available_from,
                content_hash=ch.content_hash,
                week_number=week.week_number if week else None,
                week_start=week.start_date if week else None,
            )
        )
    linked: dict[int, list[int]] = {}
    for assessment_id, chapter_id in links:
        linked.setdefault(assessment_id, []).append(chapter_id)
    by_course: dict[int, list[Assessment]] = {i: [] for i in course_ids}
    for a in assessments:
        by_course[a.course_id].append(a)
    return {
        i: CourseCatalog(
            chapters=tuple(rows[i]),
            assessments=tuple(by_course[i]),
            chapter_ids={a.id: tuple(sorted(linked.get(a.id, ()))) for a in by_course[i]},
        )
        for i in course_ids
    }


def _on_change(sender, instance, **kwargs):
    if isinstance(instance, Course):
        invalidate(instance.id)
    elif isinstance(instance, SyllabusWeek):
        invalidate(instance.syllabus.course_id)
    else:
        invalidate(instance.course_id)


def connect() -> None:
    for model in (Course, Chapter, Assessment, SyllabusWeek):
        post_save.connect(_on_change, sender=model, dispatch_uid=f"catalog-save-{model.__name__}")
        post_delete.connect(
            _on_change, sender=model, dispatch_uid=f"catalog-delete-{model.__name__}"
        )
    for through in (Assessment.chapters.through, SyllabusWeek.chapters.through):
        m2m_changed.connect(_on_change, sender=through, dispatch_uid=f"catalog-m2m-{through}")
