"""Streak reminders for the notification engine."""

from datetime import datetime

from notifications.candidates import Candidate
from notifications.models import Trigger
from notifications.templates_loader import TIERS

from ..models import ChapterQuiz
from .streaks import AT_RISK_WINDOW, get_streak, open_quizzes


def quiz_title(quiz: ChapterQuiz) -> str:
    chapters = list(quiz.chapters.select_related("course").order_by("course__code", "order"))
    return ", ".join(f"{c.course.code} Ch {c.order}" for c in chapters) or "Chapter quiz"


def streak_candidates(student, now: datetime) -> list[Candidate]:
    streak = get_streak(student)
    found = []
    for quiz in open_quizzes(student, now).filter(closes_at__lte=now + AT_RISK_WINDOW):
        first = quiz.chapters.select_related("course").first()
        found.append(
            Candidate(
                trigger=Trigger.STREAK_AT_RISK,
                tier=TIERS[Trigger.STREAK_AT_RISK],
                source_type="chapter_quiz",
                source_id=quiz.id,
                course_id=first.course_id if first else None,
                variables={
                    "title": quiz_title(quiz),
                    "course": first.course.code if first else "",
                    "streak_days": streak.current,
                },
                link=f"/pulse/quiz/{quiz.id}",
                due_at=quiz.closes_at,
            )
        )
    return found


def quiz_still_open(quiz_id: int, now: datetime) -> bool:
    quiz = ChapterQuiz.objects.filter(pk=quiz_id).first()
    return bool(quiz and quiz.submitted_at is None and quiz.closes_at > now)
