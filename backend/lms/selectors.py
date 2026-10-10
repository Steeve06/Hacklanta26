"""Read-only views of Learning Hub data for other apps. Pulse never queries LMS tables directly."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Prefetch

from .models import Assessment, Chapter, ChapterProgress, Course, Enrollment, SyllabusWeek
from .status import deadline_for, is_done, load_state, status_for


@dataclass(frozen=True)
class CourseInfo:
    id: int
    code: str
    title: str
    color: str


@dataclass(frozen=True)
class ChapterInfo:
    id: int
    course_id: int
    course_code: str
    order: int
    title: str
    reading_minutes: int
    objectives: tuple[str, ...]
    available_from: datetime
    content_hash: str
    syllabus_week: int | None
    week_end: datetime | None
    completed_at: datetime | None
    opened_at: datetime | None


@dataclass(frozen=True)
class AssessmentInfo:
    id: int
    course_id: int
    course_code: str
    type: str
    title: str
    instructions: str
    open_at: datetime
    due_at: datetime
    cutoff_at: datetime | None
    weight_pct: Decimal
    points: int
    est_minutes: int | None
    chapter_ids: tuple[int, ...]
    status: str
    extended: bool
    submitted_at: datetime | None
    replies_required: int
    time_limit_minutes: int
    original_posted: bool
    replies_made: int

    @property
    def done(self) -> bool:
        return is_done(self.status)

    @property
    def closes_at(self) -> datetime:
        return self.cutoff_at or self.due_at


@dataclass(frozen=True)
class StudentSnapshot:
    now: datetime
    term_start: date | None
    term_end: date | None
    courses: tuple[CourseInfo, ...]
    chapters: tuple[ChapterInfo, ...]
    assessments: tuple[AssessmentInfo, ...]

    def course(self, course_id: int) -> CourseInfo:
        return next(c for c in self.courses if c.id == course_id)

    def chapter(self, chapter_id: int) -> ChapterInfo | None:
        return next((c for c in self.chapters if c.id == chapter_id), None)

    def term_end_at(self, tz) -> datetime | None:
        if self.term_end is None:
            return None
        return datetime.combine(self.term_end + timedelta(days=1), time(0), tzinfo=tz)


def enrolled_courses(student):
    return Course.objects.filter(
        enrollments__user=student, enrollments__role=Enrollment.Role.STUDENT
    ).select_related("term")


def student_snapshot(student, now: datetime) -> StudentSnapshot:
    courses = list(enrolled_courses(student))
    course_by_id = {c.id: c for c in courses}
    chapters = list(
        Chapter.objects.filter(course__in=courses)
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
    progress = {
        p.chapter_id: p
        for p in ChapterProgress.objects.filter(student=student, chapter__in=chapters)
    }
    assessments = list(
        Assessment.objects.filter(course__in=courses, published=True).prefetch_related(
            Prefetch("chapters", queryset=Chapter.objects.only("id"))
        )
    )
    state = load_state(student, [a.id for a in assessments])

    chapter_infos = []
    for ch in chapters:
        week = min(ch.syllabus_weeks.all(), key=lambda w: w.week_number, default=None)
        week_end = (
            datetime.combine(week.start_date + timedelta(days=7), time(0), tzinfo=student.tz)
            if week
            else None
        )
        p = progress.get(ch.id)
        chapter_infos.append(
            ChapterInfo(
                id=ch.id,
                course_id=ch.course_id,
                course_code=course_by_id[ch.course_id].code,
                order=ch.order,
                title=ch.title,
                reading_minutes=ch.reading_minutes,
                objectives=tuple(ch.objectives),
                available_from=ch.available_from,
                content_hash=ch.content_hash,
                syllabus_week=week.week_number if week else None,
                week_end=week_end,
                completed_at=p.completed_at if p else None,
                opened_at=p.first_opened_at if p else None,
            )
        )

    assessment_infos = []
    for a in assessments:
        deadline = deadline_for(a, state)
        latest = state.latest.get(a.id)
        assessment_infos.append(
            AssessmentInfo(
                id=a.id,
                course_id=a.course_id,
                course_code=course_by_id[a.course_id].code,
                type=a.type,
                title=a.title,
                instructions=a.instructions,
                open_at=a.open_at,
                due_at=deadline.due_at,
                cutoff_at=deadline.cutoff_at,
                weight_pct=a.weight_pct,
                points=a.points,
                est_minutes=a.est_minutes,
                chapter_ids=tuple(c.id for c in a.chapters.all()),
                status=status_for(a, state, now),
                extended=deadline.extended,
                submitted_at=latest.submitted_at if latest else None,
                replies_required=a.discussion_replies_required,
                time_limit_minutes=a.time_limit_minutes,
                original_posted=state.originals.get(a.id, 0) > 0,
                replies_made=state.replies.get(a.id, 0),
            )
        )

    terms = [c.term for c in courses]
    return StudentSnapshot(
        now=now,
        term_start=min((t.start_date for t in terms), default=None),
        term_end=max((t.end_date for t in terms), default=None),
        courses=tuple(CourseInfo(c.id, c.code, c.title, c.color) for c in courses),
        chapters=tuple(sorted(chapter_infos, key=lambda c: (c.course_id, c.order))),
        assessments=tuple(sorted(assessment_infos, key=lambda a: a.due_at)),
    )
