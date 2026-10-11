"""Builds the Learning Hub part of the demo: term, courses, chapters, assessments and history."""

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from accounts.models import StudentProfile, User
from lms.models import (
    Assessment,
    Chapter,
    ChapterProgress,
    Course,
    CourseMeeting,
    DiscussionPost,
    DueDateOverride,
    Enrollment,
    QuizAttempt,
    QuizQuestion,
    Submission,
    Syllabus,
    SyllabusWeek,
    Term,
)
from lms.registration import Meeting, Registration, register_course

from . import catalog

CONTENT_DIR = Path(__file__).parent / "content"
CAMPUS_TZ = ZoneInfo(settings.CAMPUS_TIMEZONE)
PASSWORD = "pulse-demo"
TERM_WEEKS = 15
STUDY_WORDS_PER_MINUTE = 70
S = Submission.Status


@dataclass
class DemoTerm:
    term: Term
    start: date
    courses: list[Course]
    students: dict[str, User]
    classmates: list[User]


def term_start() -> date:
    if settings.TERM_START_DATE:
        return date.fromisoformat(settings.TERM_START_DATE)
    today = timezone.localdate()
    four_weeks_back = today - timedelta(weeks=4)
    return four_weeks_back - timedelta(days=four_weeks_back.weekday())


def local_dt(day: date, at: time) -> datetime:
    return datetime.combine(day, at, tzinfo=CAMPUS_TZ)


def week_day(start: date, week: int, day: int) -> date:
    return start + timedelta(weeks=week - 1, days=day)


def term_name(start: date) -> str:
    season = "Spring" if start.month <= 4 else "Summer" if start.month <= 7 else "Fall"
    return f"{season} {start.year}"


def parse_chapter(path: Path) -> dict:
    raw = path.read_text()
    match = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    if not match:
        raise ValueError(f"{path} has no front matter")
    meta, body = match.groups()
    title = re.search(r"^title: (.+)$", meta, re.M).group(1).strip()
    objectives = [line[2:].strip() for line in meta.splitlines() if line.startswith("- ")]
    words = len(body.split())
    return {
        "title": title,
        "objectives": objectives,
        "body_md": body.strip(),
        "reading_minutes": max(10, -(-words // STUDY_WORDS_PER_MINUTE)),
    }


def reset() -> None:
    Course.objects.filter(code__in=[c["code"] for c in catalog.COURSES]).delete()
    Term.objects.filter(courses__isnull=True).delete()
    User.objects.filter(email__endswith="@pulse.test").delete()


def reenroll_signups() -> int:
    """Students who signed up themselves keep their accounts across reseeds; put them back in
    the freshly created courses."""
    from lms.enrolment import enroll_in_current_term

    students = User.objects.filter(role=User.Role.STUDENT).exclude(email__endswith="@pulse.test")
    for student in students:
        enroll_in_current_term(student)
    return students.count()


def make_user(email, first, last, role, **extra) -> User:
    user = User.objects.create_user(
        email=email, password=PASSWORD, first_name=first, last_name=last, role=role, **extra
    )
    return user


def build_term(with_content: bool = True) -> DemoTerm:
    start = term_start()
    term = Term.objects.create(
        name=term_name(start),
        start_date=start,
        end_date=start + timedelta(weeks=TERM_WEEKS, days=-1),
    )
    make_user(
        "admin@pulse.test", "Demo", "Admin", User.Role.ADMIN, is_staff=True, is_superuser=True
    )
    students = {
        spec["profile"]: make_user(spec["email"], spec["first"], spec["last"], User.Role.STUDENT)
        for spec in catalog.STUDENTS
    }
    classmates = [
        make_user(
            f"{first.lower()}.{last.lower()}@pulse.test".replace("á", "a"), first, last, "student"
        )
        for first, last in catalog.CLASSMATES
    ]
    if not with_content:
        courses = [register_shell(term, spec) for spec in catalog.COURSES]
        return DemoTerm(term, start, courses, students, classmates)
    courses = [
        build_course(term, start, spec, [*students.values(), *classmates])
        for spec in catalog.COURSES
    ]
    return DemoTerm(term, start, courses, students, classmates)


def register_shell(term: Term, spec: dict) -> Course:
    """The course as the department pre-registers it: class times and a syllabus intro, no
    chapters or assignments. The teacher signs up with their email to claim it and add content."""
    email, first, last = spec["instructor"]
    return register_course(
        Registration(
            code=spec["code"], title=spec["title"], teacher_email=email,
            teacher_first_name=first, teacher_last_name=last, color=spec["color"],
            description=spec["description"], office_hours=spec["office_hours"],
            meetings=[
                Meeting(day, time.fromisoformat(begins), time.fromisoformat(ends), room)
                for day, begins, ends, room in spec["meetings"]
            ],
        ),
        term=term,
    )  # fmt: skip


def build_course(term: Term, start: date, spec: dict, students: list[User]) -> Course:
    email, first, last = spec["instructor"]
    instructor = make_user(email, first, last, User.Role.INSTRUCTOR)
    course = Course.objects.create(
        term=term,
        code=spec["code"],
        title=spec["title"],
        instructor=instructor,
        color=spec["color"],
    )
    Enrollment.objects.create(user=instructor, course=course, role=Enrollment.Role.INSTRUCTOR)
    CourseMeeting.objects.bulk_create(
        CourseMeeting(
            course=course,
            weekday=day,
            start_time=time.fromisoformat(begins),
            end_time=time.fromisoformat(ends),
            location=room,
        )  # fmt: skip
        for day, begins, ends, room in spec["meetings"]
    )
    Enrollment.objects.bulk_create(Enrollment(user=s, course=course) for s in students)

    chapters = []
    for order, week in enumerate(catalog.CHAPTER_WEEKS, start=1):
        data = parse_chapter(CONTENT_DIR / spec["slug"] / f"{order:02d}.md")
        unlock = local_dt(week_day(start, week, 0) - timedelta(days=3), time(8, 0))
        chapters.append(
            Chapter.objects.create(course=course, order=order, available_from=unlock, **data)
        )

    syllabus = Syllabus.objects.create(
        course=course,
        description=spec["description"],
        office_hours=spec["office_hours"],
        grading=[{"label": label, "weight_pct": weight} for label, weight in spec["grading"]],
        policies=catalog.POLICIES,
    )
    for week in range(1, TERM_WEEKS + 1):
        week_chapters = [
            c for c, w in zip(chapters, catalog.CHAPTER_WEEKS, strict=True) if w == week
        ]
        topic = catalog.WEEK_TOPICS.get(week) or (
            week_chapters[0].title if week_chapters else "Practice and catch-up"
        )
        sw = SyllabusWeek.objects.create(
            syllabus=syllabus, week_number=week, start_date=week_day(start, week, 0), topic=topic
        )
        sw.chapters.set(week_chapters)

    quiz_no = 0
    for kind, title, chapter_orders, week, day, weight, est in spec["assessments"]:
        due_day = week_day(start, week, day)
        assessment = Assessment.objects.create(
            course=course,
            type=kind,
            title=title,
            instructions=instructions_for(kind, title),
            open_at=local_dt(due_day - timedelta(days=10), time(8, 0)),
            due_at=local_dt(due_day, time(23, 59)),
            cutoff_at=local_dt(due_day + timedelta(days=3), time(23, 59))
            if kind != "quiz"
            else None,
            points=20 if kind == "homework" else 10,
            weight_pct=Decimal(weight),
            est_minutes=est,
            discussion_replies_required=2,
            time_limit_minutes=20,
            max_attempts=2,
        )
        assessment.chapters.set([chapters[o - 1] for o in chapter_orders])
        if kind == "quiz":
            quiz_no += 1
            for order, (prompt, options, correct) in enumerate(
                catalog.QUIZ_QUESTIONS[(spec["code"], quiz_no)], start=1
            ):
                QuizQuestion.objects.create(
                    assessment=assessment,
                    order=order,
                    type="true_false" if options == ["True", "False"] else "multiple_choice",
                    prompt=prompt,
                    options=options,
                    correct_index=correct,
                )
    return course


def instructions_for(kind: str, title: str) -> str:
    if kind == "homework":
        return (
            f"Complete **{title}** using the linked chapters.\n\n"
            "- Show your reasoning, not just final answers.\n"
            "- Submit a single PDF, DOCX or ZIP, or paste your answer as text.\n"
            "- You can resubmit until the due date; the latest submission is graded."
        )
    if kind == "discussion":
        return (
            f"**{title}**\n\nWrite an original post of 150–250 words that draws on the linked "
            "chapter, then reply to two classmates. Good replies add an example, ask a real "
            "question or respectfully disagree with a reason."
        )
    return (
        "Multiple choice and true/false. You have 20 minutes once you start and two attempts; "
        "your best score counts."
    )


def seed_history(demo: DemoTerm) -> None:
    now = timezone.now()
    for c_index, course in enumerate(demo.courses):
        chapters = list(course.chapters.all())
        assessments = list(course.assessments.prefetch_related("questions"))
        seed_classmate_posts(demo.classmates, assessments, now)
        for profile, student in demo.students.items():
            seed_chapters(student, profile, chapters, now)
            for a_index, assessment in enumerate(assessments):
                seed_assessment(student, profile, assessment, a_index, now)
        if c_index == 0:
            extend_next_homework(demo.students["extension"], assessments, now)


def seed_classmate_posts(classmates, assessments, now) -> None:
    for assessment in assessments:
        if assessment.type != "discussion" or assessment.open_at > now:
            continue
        for i, mate in enumerate(classmates[:3]):
            post = DiscussionPost.objects.create(
                assessment=assessment, author=mate, body=catalog.CLASSMATE_POSTS[i]
            )
            stamp = min(now, assessment.open_at + timedelta(days=1 + i))
            DiscussionPost.objects.filter(pk=post.pk).update(created_at=stamp)


def seed_chapters(student, profile, chapters, now) -> None:
    available = [c for c in chapters if c.available_from <= now]
    done_count = {
        "on_track": len(available),
        "extension": len(available),
        "slightly_behind": max(0, len(available) - 1),
        "badly_behind": min(1, len(available)),
        "new": 0,
        "halfway": 0,
    }[profile]
    for chapter in available[:done_count]:
        finished = min(now - timedelta(hours=6), chapter.available_from + timedelta(days=4))
        if profile == "on_track" and chapter == available[-1]:
            # Finished this week's chapter earlier today, so the demo always has an open check.
            finished = now - timedelta(minutes=30)
        ChapterProgress.objects.create(
            student=student,
            chapter=chapter,
            first_opened_at=finished - timedelta(hours=2),
            completed_at=finished,
        )
    if profile == "badly_behind" and len(available) > 1:
        ChapterProgress.objects.create(
            student=student, chapter=available[1], first_opened_at=now - timedelta(days=5)
        )


def outcome(profile: str, assessment: Assessment, index: int, now: datetime) -> str | None:
    """What the student did with an assessment whose due date has passed."""
    if profile in ("new", "halfway"):
        return "excused"
    if profile in ("on_track", "extension"):
        return "on_time"
    if profile == "slightly_behind":
        recent = now - assessment.due_at < timedelta(days=21)
        if recent and assessment.type == "quiz" and assessment.course.code == "CS 201":
            return None
        return "late" if recent and assessment.type == "homework" else "on_time"
    if assessment.type == "quiz":
        return "on_time"
    days_ago = (now - assessment.due_at).days
    if days_ago > 14:
        return "on_time" if index % 3 != 2 else "missed"
    return None


def seed_assessment(student, profile, assessment: Assessment, index: int, now) -> None:
    if assessment.due_at > now:
        return
    result = outcome(profile, assessment, index, now)
    if result is None or result == "missed":
        return
    if result == "excused":
        Submission.objects.create(assessment=assessment, student=student, status=S.EXCUSED)
        return
    late = result == "late"
    submitted = assessment.due_at + (timedelta(days=1) if late else -timedelta(hours=20))
    if assessment.type == "discussion":
        seed_discussion(student, assessment, submitted)
    if assessment.type == "quiz":
        seed_quiz(student, assessment, submitted, strong=profile != "badly_behind")
        return
    graded = now - assessment.due_at > timedelta(days=5)
    score = Decimal(assessment.points) * (Decimal("0.78") if late else Decimal("0.9"))
    Submission.objects.create(
        assessment=assessment,
        student=student,
        status=S.LATE if late else S.SUBMITTED,
        text="Submitted answers are attached." if assessment.type == "homework" else "",
        submitted_at=submitted,
        score=score.quantize(Decimal("0.01")) if graded else None,
    )


def seed_discussion(student, assessment, submitted) -> None:
    original = DiscussionPost.objects.create(
        assessment=assessment,
        author=student,
        body="My take: the reading's main trade-off showed up in a project I worked on, and the "
        "fix was to decide what mattered most to the people using it before choosing anything.",
    )
    DiscussionPost.objects.filter(pk=original.pk).update(created_at=submitted - timedelta(days=1))
    others = DiscussionPost.objects.filter(assessment=assessment, parent__isnull=True).exclude(
        author=student
    )[:2]
    for other in others:
        reply = DiscussionPost.objects.create(
            assessment=assessment,
            author=student,
            parent=other,
            body="Good point. I'd add that it depends on how often that case actually happens.",
        )
        DiscussionPost.objects.filter(pk=reply.pk).update(created_at=submitted)


def seed_quiz(student, assessment, submitted, strong: bool) -> None:
    questions = list(assessment.questions.all())
    answers = {
        str(q.id): (
            q.correct_index if strong or i % 2 == 0 else (q.correct_index + 1) % len(q.options)
        )
        for i, q in enumerate(questions)
    }
    earned = sum(1 for q in questions if answers[str(q.id)] == q.correct_index)
    score = (Decimal(earned) / Decimal(len(questions)) * assessment.points).quantize(
        Decimal("0.01")
    )
    started = submitted - timedelta(minutes=14)
    QuizAttempt.objects.create(
        assessment=assessment,
        student=student,
        attempt_no=1,
        started_at=started,
        deadline_at=started + timedelta(minutes=assessment.time_limit_minutes),
        submitted_at=submitted,
        answers=answers,
        score=score,
    )
    Submission.objects.create(
        assessment=assessment,
        student=student,
        status=S.SUBMITTED,
        submitted_at=submitted,
        score=score,
    )


def extend_next_homework(student, assessments, now) -> None:
    upcoming = next((a for a in assessments if a.type == "homework" and a.due_at > now), None)
    if upcoming is None:
        return
    DueDateOverride.objects.create(
        assessment=upcoming,
        student=student,
        due_at=upcoming.due_at + timedelta(days=5),
        cutoff_at=(upcoming.cutoff_at or upcoming.due_at) + timedelta(days=5),
        reason="Approved extension: family event",
    )


def mark_profiles(demo: DemoTerm) -> None:
    not_onboarded = [demo.students["new"], demo.students["halfway"]]
    StudentProfile.objects.filter(user__in=demo.students.values()).exclude(
        user__in=not_onboarded
    ).update(sass_level=3)
    StudentProfile.objects.filter(user__in=not_onboarded).update(onboarding_done=False)
