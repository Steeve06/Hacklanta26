from django.conf import settings
from django.db import models

from config.models import TimeStamped

User = settings.AUTH_USER_MODEL


class Conversation(TimeStamped):
    """A student's chat with the assistant. Starting over closes the current one."""

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="conversations")
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["student", "closed_at"])]


class ChatMessage(TimeStamped):
    class Role(models.TextChoices):
        STUDENT = "student"
        ASSISTANT = "assistant"

    class State(models.TextChoices):
        PENDING = "pending"
        DONE = "done"
        FAILED = "failed"

    class Proposal(models.TextChoices):
        NONE = "none"
        PENDING = "pending"
        APPLIED = "applied"
        DECLINED = "declined"
        FAILED = "failed"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    text = models.TextField(blank=True)
    state = models.CharField(max_length=10, choices=State.choices, default=State.DONE)
    actions = models.JSONField(default=list, help_text="validated changes the reply proposes")
    proposal = models.CharField(max_length=10, choices=Proposal.choices, default=Proposal.NONE)
    proposal_note = models.CharField(max_length=300, blank=True)
    used_ai = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["conversation", "created_at"])]
