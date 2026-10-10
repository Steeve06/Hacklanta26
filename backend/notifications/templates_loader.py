"""Load the seeded copy into NotificationTemplate rows (idempotent)."""

from .copy import COPY, SUPPORTIVE
from .guardrails import placeholders

TIERS = {
    "session_starting": 1, "session_ignored": 2, "upcoming_due": 1, "falling_behind": 2,
    "final_stretch": 3, "code_red": 4, "missed_late": 5, "streak_at_risk": 3, "streak_lost": 5,
    "win": 0,
}  # fmt: skip
SUPPORTIVE_LEVEL = 0


def load_templates(model) -> int:
    rows = [
        (trigger, TIERS[trigger], level, text)
        for trigger, levels in COPY.items()
        for level, texts in levels.items()
        for text in texts
    ] + [
        (trigger, TIERS[trigger], SUPPORTIVE_LEVEL, text)
        for trigger, texts in SUPPORTIVE.items()
        for text in texts
    ]
    wanted = {(t, lvl, text) for t, _, lvl, text in rows}
    existing = {(t.trigger, t.sass_level, t.text): t for t in model.objects.all()}
    created = 0
    for trigger, tier, level, text in rows:
        if (trigger, level, text) not in existing:
            model.objects.create(
                trigger=trigger, tier=tier, sass_level=level, text=text,
                variables=sorted(placeholders(text)),
            )  # fmt: skip
            created += 1
    for key, template in existing.items():
        if key not in wanted and template.active:
            template.active = False
            template.save(update_fields=["active"])
    return created
