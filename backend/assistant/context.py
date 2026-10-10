"""What the assistant knows about the student for one reply: only the fields it needs, with
times in the student's own zone. No names, emails or grades."""

from datetime import timedelta

from accounts.clock import now as clock_now
from lms.selectors import student_snapshot
from pulse.models import AvailabilityBlock, Blackout, Session
from quizzes.services.streaks import get_streak, open_checks

from .models import ChatMessage

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SESSION_DAYS = 10
DUE_DAYS = 21
HISTORY = 10


def local(moment, tz) -> str:
    return moment.astimezone(tz).strftime("%Y-%m-%dT%H:%M")


def build(student, conversation, before_id: int) -> dict:
    tz = student.tz
    now = clock_now(student)
    profile = student.profile
    sessions = (
        Session.objects.filter(
            schedule__student=student,
            schedule__is_active=True,
            start__lt=now + timedelta(days=SESSION_DAYS),
            end__gt=now - timedelta(hours=12),
        )
        .select_related("schedule")
        .order_by("start")[:60]
    )
    snapshot = student_snapshot(student, now)
    due = sorted(
        (
            a
            for a in snapshot.assessments
            if not a.done and a.due_at <= now + timedelta(days=DUE_DAYS)
        ),
        key=lambda a: a.due_at,
    )[:20]
    streak = get_streak(student)
    return {
        "now": local(now, tz),
        "today": WEEKDAY_NAMES[now.astimezone(tz).weekday()],
        "timezone": str(tz),
        "settings": {
            "max_hours_per_week": float(profile.max_hours_per_week),
            "max_hours_per_day": float(profile.max_hours_per_day),
            "session_minutes": profile.session_minutes,
            "earliest_time": profile.earliest_time.strftime("%H:%M"),
            "latest_time": profile.latest_time.strftime("%H:%M"),
            "schedule_note": profile.plan_feedback,
        },
        "free_time": [
            {
                "weekday": b.weekday,
                "day": WEEKDAY_NAMES[b.weekday],
                "start": b.start_time.strftime("%H:%M"),
                "end": b.end_time.strftime("%H:%M"),
            }
            for b in AvailabilityBlock.objects.filter(student=student).order_by(
                "weekday", "start_time"
            )
        ],
        "busy_times": [
            {"start": local(b.start, tz), "end": local(b.end, tz), "label": b.label}
            for b in Blackout.objects.filter(student=student, end__gt=now).order_by("start")[:10]
        ],
        "sessions": [
            {
                "id": s.id,
                "start": local(s.start, tz),
                "end": local(s.end, tz),
                "title": s.title,
                "kind": s.kind,
                "status": s.status,
                "moved_by_student": s.locked,
            }
            for s in sessions
        ],
        "due_soon": [
            {
                "course": a.course_code,
                "title": a.title,
                "type": a.type,
                "due": local(a.due_at, tz),
                "status": a.status,
                "weight_pct": float(a.weight_pct),
            }
            for a in due
        ],
        "study_checks_open": [
            {"closes": local(c.closes_at, tz)} for c in open_checks(student, now)
        ],
        "streak": streak.current,
        "conversation": [
            {"from": m.role, "text": m.text[:600]}
            for m in reversed(
                conversation.messages.filter(state=ChatMessage.State.DONE, id__lt=before_id)
                .exclude(text="")
                .order_by("-created_at", "-id")[:HISTORY]
            )
        ],
    }
