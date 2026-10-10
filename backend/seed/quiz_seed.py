"""Card banks for every chapter and some streak history for the demo students."""

import random
from datetime import datetime, time, timedelta

from django.utils import timezone

from lms.models import Chapter, ChapterProgress
from lms.selectors import enrolled_courses
from quizzes.models import CheckAttempt, Streak, StreakEvent, StudyCheck
from quizzes.services.bank import choices, rebuild_bank
from quizzes.services.checks import XP_FOR_FINISHING, XP_PER_CORRECT

STREAKS = {
    "on_track": (6, 9, 1),
    "extension": (4, 4, 0),
    "slightly_behind": (2, 5, 0),
    "badly_behind": (0, 3, 0),
}


def seed_banks() -> int:
    """Key-term cards, so seeding is fast and works offline. With AI configured, banks are
    upgraded to model-written cards in the background when checks open."""
    return sum(rebuild_bank(chapter, allow_ai=False) for chapter in Chapter.objects.all())


def seed_streaks(students: dict) -> None:
    now = timezone.now()
    for profile, (current, longest, freezes) in STREAKS.items():
        student = students[profile]
        Streak.objects.update_or_create(
            student=student,
            defaults={
                "current": current,
                "longest": longest,
                "freezes": freezes,
                "on_time_toward_freeze": current % 5,
            },  # fmt: skip
        )
        for i in range(current):
            when = now - timedelta(days=2 * i + 1)
            event = StreakEvent.objects.create(
                student=student,
                day=when.date(),
                result=StreakEvent.Result.ON_TIME,
                streak_after=current - i,
            )
            StreakEvent.objects.filter(pk=event.pk).update(created_at=when)
        if current == 0:
            when = now - timedelta(days=3)
            event = StreakEvent.objects.create(
                student=student, day=when.date(), result=StreakEvent.Result.MISSED
            )
            StreakEvent.objects.filter(pk=event.pk).update(created_at=when)


# (cards right out of four, chance of doing a check on a given day) for this week's leaderboard.
HABITS = {
    "on_track": (3.3, 0.95), "extension": (3.0, 0.7), "slightly_behind": (2.7, 0.55),
    "badly_behind": (2.2, 0.25),
}  # fmt: skip
CLASSMATE_HABIT = (3.0, 0.75)


def _finished_check(student, chapter: Chapter, finished: datetime, skill: float, rng) -> None:
    right = max(0, min(4, round(rng.gauss(skill, 0.6))))
    passed = right >= 3
    check = StudyCheck.objects.create(
        student=student, scheduled_date=finished.astimezone(student.tz).date(),
        opens_at=finished - timedelta(hours=6),
        closes_at=min(finished + timedelta(hours=4), timezone.now() - timedelta(minutes=1)),
        timezone=student.timezone, passed=passed, counted_for_streak=passed, resolved=True,
    )  # fmt: skip
    check.chapters.set([chapter])
    cards = [
        {"kind": "choice", "question_id": q.id, "order": list(range(len(q.options)))}
        for q in choices(chapter).order_by("?")[:4]
    ]
    CheckAttempt.objects.create(
        study_check=check, number=1, cards=cards, started_at=finished - timedelta(minutes=2),
        expires_at=finished + timedelta(minutes=1), finished_at=finished, correct=right,
        xp=right * XP_PER_CORRECT + XP_FOR_FINISHING,
    )  # fmt: skip


def seed_xp(students: dict, classmates: list) -> None:
    """Finished study checks from Monday to now, so the weekly leaderboard has something to show.
    Demo students only get checks on chapters they finished before today, so nothing about their
    upcoming checks changes; classmates (who have no schedule) use any released chapter."""
    now = timezone.now()
    people = [(u, *HABITS[p], True) for p, u in students.items() if p in HABITS]
    for u in classmates:
        skill, often = CLASSMATE_HABIT
        jitter = random.Random(u.email)
        people.append(
            (u, skill + jitter.uniform(-0.6, 0.4), often + jitter.uniform(-0.2, 0.1), False)
        )
        Streak.objects.update_or_create(student=u, defaults={"current": jitter.randint(1, 5)})
    for user, skill, often, own_chapters in people:
        rng = random.Random(f"xp:{user.email}")
        today = now.astimezone(user.tz).date()
        monday = today - timedelta(days=today.weekday())
        if own_chapters:
            start_of_today = datetime.combine(today, time(0), tzinfo=user.tz)
            ids = ChapterProgress.objects.filter(
                student=user, completed_at__lt=start_of_today
            ).values_list("chapter_id", flat=True)
            chapters = list(Chapter.objects.filter(id__in=ids).order_by("id"))
        else:
            chapters = list(
                Chapter.objects.filter(
                    course__in=enrolled_courses(user), available_from__lte=now
                ).order_by("id")
            )
        if not chapters:
            continue
        day = monday
        while day <= today:
            finished = datetime.combine(day, time(19, 30), tzinfo=user.tz)
            if day == today:
                finished = max(
                    now - timedelta(hours=2), datetime.combine(day, time(0, 5), tzinfo=user.tz)
                )
            if finished <= now and rng.random() < often:
                _finished_check(user, rng.choice(chapters), finished, skill, rng)
            day += timedelta(days=1)
