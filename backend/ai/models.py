from django.db import models

from config.models import TimeStamped


class AICallLog(TimeStamped):
    purpose = models.CharField(max_length=40, db_index=True)
    provider = models.CharField(max_length=20, blank=True)
    model = models.CharField(max_length=80, blank=True)
    prompt_version = models.CharField(max_length=40, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=False)
    fallback_used = models.BooleanField(default=False)
    error = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]


class AICache(TimeStamped):
    """AI outputs keyed by a hash of everything that went into them."""

    purpose = models.CharField(max_length=40)
    key = models.CharField(max_length=64, unique=True)
    payload = models.JSONField()
