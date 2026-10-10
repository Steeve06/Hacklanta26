"""First-run wizard: five steps, each saved when the student presses Next.

Answers are stored where the rest of the app reads them (profile, user timezone, availability);
the Onboarding row only tracks the current step, which steps are done, and when the inputs to
the schedule last changed, so step 5 knows whether its schedule is still current.
"""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.clock import now as clock_now
from accounts.models import StudentProfile
from lms.selectors import enrolled_courses

from .models import AvailabilityBlock, Onboarding, Schedule
from .serializers import merge_blocks

SCHEDULE_INPUT_STEPS = {2, 3}
TOTAL_STEPS = Onboarding.STEPS


def replace_availability(student, blocks: list[dict]) -> int:
    """Swap a student's weekly blocks in one transaction. Returns how many were merged."""
    merged, absorbed = merge_blocks(blocks)
    with transaction.atomic():
        AvailabilityBlock.objects.filter(student=student).delete()
        AvailabilityBlock.objects.bulk_create(
            AvailabilityBlock(student=student, **block) for block in merged
        )
    return absorbed


def state_for(student) -> Onboarding:
    state, _ = Onboarding.objects.get_or_create(student=student)
    profile = getattr(student, "profile", None)
    if profile and profile.onboarding_done and state.completed_at is None:
        state.completed_steps = list(range(1, TOTAL_STEPS + 1))
        state.current_step = TOTAL_STEPS
        state.completed_at = state.updated_at
        state.save(update_fields=["completed_steps", "current_step", "completed_at"])
    return state


def schedule_ready(student, state: Onboarding) -> bool:
    schedule = Schedule.objects.filter(student=student, is_active=True).only("generated_at")
    schedule = schedule.first()
    if schedule is None:
        return False
    return state.inputs_changed_at is None or schedule.generated_at >= state.inputs_changed_at


def first_open_step(state: Onboarding) -> int:
    done = set(state.completed_steps)
    return next((s for s in range(1, TOTAL_STEPS + 1) if s not in done), TOTAL_STEPS)


def snapshot(student, state: Onboarding, note: str = "", stale: bool = False) -> dict:
    profile = student.profile
    blocks = AvailabilityBlock.objects.filter(student=student)
    return {
        "step": state.current_step,
        "completed_steps": sorted(state.completed_steps),
        "version": state.version,
        "done": profile.onboarding_done,
        "schedule_ready": schedule_ready(student, state),
        "stale": stale,
        "note": note,
        "availability": {"blocks": blocks},
        "preferences": {
            "max_hours_per_day": profile.max_hours_per_day,
            "max_hours_per_week": profile.max_hours_per_week,
            "session_minutes": profile.session_minutes,
            "earliest_time": profile.earliest_time,
            "latest_time": profile.latest_time,
            "timezone": student.timezone,
        },
        "notifications": {
            "sass_level": profile.sass_level,
            "quiet_start": profile.quiet_start,
            "quiet_end": profile.quiet_end,
        },
    }


def save_step(
    student, step: int, data: dict | None, version: int | None
) -> tuple[Onboarding, str, bool]:
    """Apply one step. Last save wins; `stale` tells a second tab to reload what it shows."""
    from .onboarding_serializers import STEP_SERIALIZERS

    with transaction.atomic():
        state = Onboarding.objects.select_for_update().get(pk=state_for(student).pk)
        stale = version is not None and version != state.version
        if data is None:
            if step > first_open_step(state):
                raise ValidationError({"step": f"Finish step {first_open_step(state)} first."})
            state.current_step = step
            state.version += 1
            state.save(update_fields=["current_step", "version", "updated_at"])
            return state, "", stale
        if step not in STEP_SERIALIZERS:
            raise ValidationError({"step": "This step is finished from the schedule screen."})
        if step > first_open_step(state):
            raise ValidationError({"step": f"Finish step {first_open_step(state)} first."})
        serializer = STEP_SERIALIZERS[step](data=data, context={"student": student})
        serializer.is_valid(raise_exception=True)
        changed, note = serializer.apply()
        if changed and step in SCHEDULE_INPUT_STEPS:
            state.inputs_changed_at = clock_now(student)
        if step not in state.completed_steps:
            state.completed_steps = sorted({*state.completed_steps, step})
        state.current_step = min(step + 1, TOTAL_STEPS)
        state.version += 1
        state.save()
        return state, note, stale


def complete(student) -> Onboarding:
    with transaction.atomic():
        state = Onboarding.objects.select_for_update().get(pk=state_for(student).pk)
        missing = [s for s in range(1, TOTAL_STEPS) if s not in state.completed_steps]
        if missing:
            raise ValidationError({"step": f"Finish step {missing[0]} first."})
        if not enrolled_courses(student).exists():
            raise ValidationError({"step": "You aren't enrolled in any courses yet."})
        if not schedule_ready(student, state):
            raise ValidationError({"schedule": "Generate your schedule before finishing."})
        state.completed_steps = list(range(1, TOTAL_STEPS + 1))
        state.completed_at = clock_now(student)
        state.version += 1
        state.save()
        StudentProfile.objects.filter(user=student).update(onboarding_done=True)
    student.profile.refresh_from_db()
    return state
