"""Turn true triggers into notifications: copy, caps, quiet hours, dedupe, digest, delivery."""

import logging
import random
from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q

from accounts.clock import now as clock_now
from accounts.models import StudentProfile
from lms.selectors import student_snapshot

from . import delivery
from .candidates import Candidate
from .copy import DIGEST
from .guardrails import is_safe, placeholders
from .models import WIN_TIER, Notification, NotificationTemplate, PushSubscription, Trigger
from .templates_loader import SUPPORTIVE_LEVEL, TIERS
from .triggers import evaluate, still_true

logger = logging.getLogger(__name__)

DAILY_CAP = 5
PER_SOURCE_CAP = 2
URGENT_EXTRA = 1
REPEAT_WINDOW = timedelta(days=14)
DIGEST_THRESHOLD = 4
SUPPORTIVE_MISSED = 3
SUPPORTIVE_TONE_DOWNS = 5
SUPPORTIVE_COOLDOWN = timedelta(days=14)


def effective_sass(profile: StudentProfile, candidate: Candidate | None = None) -> int:
    if profile.supportive_mode:
        return SUPPORTIVE_LEVEL
    if candidate and candidate.gentle:
        return 1
    return max(1, min(4, profile.sass_level))


def _local_date(student, moment: datetime):
    return moment.astimezone(student.tz).date()


def dedupe_key(student, c: Candidate, now: datetime) -> str:
    day = _local_date(student, now)
    return f"{student.id}:{c.trigger}:{c.source_type}:{c.source_id}:{c.tier}:{day}"


def choose_template(
    student, trigger: str, sass: int, variables: dict, rng=random
) -> tuple[NotificationTemplate, str] | None:
    """Round-robin with randomness. Never sends the same text twice within 14 days: templates whose
    rendered text was already used are skipped, and the least-used of the rest wins."""
    candidates = NotificationTemplate.objects.filter(trigger=trigger, sass_level=sass, active=True)
    templates = [t for t in candidates if placeholders(t.text) <= variables.keys()]
    if not templates:
        return None
    since = clock_now(student) - REPEAT_WINDOW
    recent = Notification.objects.filter(student=student, created_at__gte=since)
    used_texts = set(recent.values_list("text", flat=True))
    uses: dict[int, int] = {}
    for template_id in recent.filter(template__in=templates).values_list("template_id", flat=True):
        uses[template_id] = uses.get(template_id, 0) + 1
    rendered = [(t, t.text.format(**variables)) for t in templates]
    unused = [(t, text) for t, text in rendered if text not in used_texts]
    if not unused:
        return None
    least = min(uses.get(t.id, 0) for t, _ in unused)
    return rng.choice([(t, text) for t, text in unused if uses.get(t.id, 0) == least])


def _ai_variation(text: str, sass: int) -> str:
    if not settings.NOTIFICATION_AI_VARIATION:
        return text
    from ai.client import AIError, complete_json, note_fallback
    from ai.schemas import Rewrite

    try:
        rewritten = complete_json(
            purpose="notification", tier="light", prompt="notification_v1",
            payload={"text": text, "sass_level": sass}, schema=Rewrite, max_tokens=200,
        ).text  # fmt: skip
    except AIError as exc:
        note_fallback("notification", str(exc))
        return text
    return rewritten if is_safe(rewritten) else text


def _in_quiet_hours(t: time, start: time, end: time) -> bool:
    if start == end:
        return False
    return start <= t or t < end if start > end else start <= t < end


def quiet_until(
    student, profile: StudentProfile, now: datetime, due_at: datetime | None
) -> datetime | None:
    local = now.astimezone(student.tz)
    if not _in_quiet_hours(local.time(), profile.quiet_start, profile.quiet_end):
        return None
    end_day = local.date() if local.time() < profile.quiet_end else local.date() + timedelta(days=1)
    end = datetime.combine(end_day, profile.quiet_end, tzinfo=student.tz)
    if profile.quiet_hours_override_for_deadlines and due_at and now < due_at <= end:
        return None
    return end


def _channels(student, tier: int) -> list[str]:
    has_push = delivery.push_configured() and PushSubscription.objects.filter(user=student).exists()
    channels = ["inapp"]
    if has_push:
        channels.append("push")
    if tier >= 3 or not has_push:
        channels.append("email")
    return channels


def _within_caps(student, c: Candidate, now: datetime, pending: list[Candidate] = ()) -> bool:
    if c.tier == WIN_TIER:
        return True
    day_start = datetime.combine(_local_date(student, now), time(0), tzinfo=student.tz)
    today = (
        Notification.objects.filter(
            student=student, created_at__gte=day_start, cancelled_at__isnull=True
        )
        .exclude(tier=WIN_TIER)
        .exclude(trigger=Trigger.DIGEST)
    )
    if today.count() + len(pending) >= DAILY_CAP:
        return False
    same = today.filter(source_type=c.source_type, source_id=c.source_id).count() + sum(
        1 for p in pending if (p.source_type, p.source_id) == (c.source_type, c.source_id)
    )
    limit = PER_SOURCE_CAP + (URGENT_EXTRA if c.tier >= 4 else 0)
    return same < limit


def maybe_enter_supportive_mode(student, profile: StudentProfile, snapshot, now) -> None:
    if profile.supportive_mode:
        return
    if (
        profile.supportive_dismissed_at
        and now - profile.supportive_dismissed_at < SUPPORTIVE_COOLDOWN
    ):
        return
    missed = sum(
        1 for a in snapshot.assessments
        if a.status == "missed" and now - a.closes_at <= timedelta(days=14)
    )  # fmt: skip
    if missed >= SUPPORTIVE_MISSED:
        profile.supportive_mode = True
        profile.save(update_fields=["supportive_mode", "updated_at"])


def create(student, profile, c: Candidate, now: datetime, *, channels=None) -> Notification | None:
    sass = effective_sass(profile, c)
    variables = {**c.variables, "first_name": student.first_name}
    chosen = choose_template(student, c.trigger, sass, variables)
    if chosen is None:
        logger.info("No unused copy for %s at sass %s; skipped", c.trigger, sass)
        return None
    template, text = chosen
    text = _ai_variation(text, sass)
    if not is_safe(text):
        logger.error("Template %s failed guardrails; skipped", template.id)
        return None
    scheduled = quiet_until(student, profile, now, c.due_at) or now
    try:
        with transaction.atomic():
            return Notification.objects.create(
                student=student, trigger=c.trigger, tier=c.tier, sass_level=sass, template=template,
                source_type=c.source_type, source_id=c.source_id, course_id=c.course_id,
                text=text, link=c.link, channels=channels or _channels(student, c.tier),
                scheduled_for=scheduled, dedupe_key=dedupe_key(student, c, now),
            )  # fmt: skip
    except IntegrityError:
        return None


def scan_student(student, now: datetime | None = None) -> list[Notification]:
    now = now or clock_now(student)
    profile, _ = StudentProfile.objects.get_or_create(user=student)
    snapshot = student_snapshot(student, now)
    maybe_enter_supportive_mode(student, profile, snapshot, now)
    candidates = sorted(evaluate(student, snapshot, now), key=lambda c: -c.tier)
    fresh: list[Candidate] = []
    for c in candidates:
        if Notification.objects.filter(dedupe_key=dedupe_key(student, c, now)).exists():
            continue
        if _within_caps(student, c, now, pending=fresh):
            fresh.append(c)
    if len(fresh) >= DIGEST_THRESHOLD:
        return _digest(student, profile, fresh, now)
    created = [n for c in fresh if (n := create(student, profile, c, now))]
    return created


def _digest(student, profile, candidates: list[Candidate], now: datetime) -> list[Notification]:
    items = [n for c in candidates if (n := create(student, profile, c, now, channels=["inapp"]))]
    if not items:
        return []
    sass = effective_sass(profile) or 1
    titles = ", ".join(
        sorted({c.variables.get("title", "") for c in candidates if c.variables.get("title")})[:4]
    )
    text = DIGEST[max(1, sass)].format(count=len(items), items=titles)
    top = max(c.tier for c in candidates)
    try:
        digest = Notification.objects.create(
            student=student, trigger=Trigger.DIGEST, tier=top, sass_level=sass, text=text,
            link="/pulse/inbox", channels=_channels(student, top),
            scheduled_for=quiet_until(student, profile, now, None) or now,
            dedupe_key=f"{student.id}:digest:{now.isoformat()}",
        )  # fmt: skip
    except IntegrityError:
        return items
    return [*items, digest]


def notify_win(
    student, *, title: str, source_type: str, source_id: int, course_id=None, variables=None
) -> None:
    profile, _ = StudentProfile.objects.get_or_create(user=student)
    now = clock_now(student)
    candidate = Candidate(
        Trigger.WIN, WIN_TIER, source_type, source_id, course_id,
        {"title": title, **(variables or {})}, "/pulse",
    )  # fmt: skip
    create(student, profile, candidate, now)


def cancel_for_source(student_id: int, source_type: str, source_id: int, reason: str) -> int:
    queued = Notification.objects.filter(
        student_id=student_id, source_type=source_type, source_id=source_id,
        sent_at__isnull=True, cancelled_at__isnull=True,
    ).exclude(trigger=Trigger.WIN)  # fmt: skip
    return queued.update(cancelled_at=clock_now(), cancel_reason=reason)


def dispatch_due(now: datetime | None = None, student=None) -> int:
    """Send everything whose time has come, after re-checking it is still true."""
    qs = Notification.objects.filter(
        sent_at__isnull=True, cancelled_at__isnull=True
    ).select_related("student", "student__profile")
    if student is not None:
        qs = qs.filter(student=student)
    sent = 0
    snapshots: dict[int, object] = {}
    for n in qs.filter(Q(scheduled_for__lte=now) if now else Q()):
        moment = now or clock_now(n.student)
        if n.scheduled_for > moment:
            continue
        snapshot = snapshots.get(n.student_id) or student_snapshot(n.student, moment)
        snapshots[n.student_id] = snapshot
        if not still_true(n, snapshot, moment):
            n.cancelled_at, n.cancel_reason = moment, "condition resolved"
            n.save(update_fields=["cancelled_at", "cancel_reason", "updated_at"])
            continue
        delivery.deliver(n)
        n.sent_at = moment
        n.save(update_fields=["sent_at", "channels", "updated_at"])
        sent += 1
    return sent


def notify_streak_lost(student, check) -> None:
    from quizzes.services.reminders import check_title

    profile, _ = StudentProfile.objects.get_or_create(user=student)
    candidate = Candidate(
        Trigger.STREAK_LOST, TIERS[Trigger.STREAK_LOST], "study_check", check.id, None,
        {"title": check_title(check), "course": "", "streak_days": 0}, f"/pulse/checks/{check.id}",
    )  # fmt: skip
    create(student, profile, candidate, clock_now(student))


def notify_streak_milestone(student, check, streak_days: int) -> None:
    profile, _ = StudentProfile.objects.get_or_create(user=student)
    candidate = Candidate(
        Trigger.WIN,
        WIN_TIER,
        "study_check",
        check.id,
        None,
        {"streak_days": streak_days},
        "/pulse/checks",
    )
    create(student, profile, candidate, clock_now(student))
