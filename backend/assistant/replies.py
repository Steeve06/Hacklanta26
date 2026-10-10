"""Answering a student's message: the model when it's available, the keyword fallback otherwise.
Every proposed change is checked before it's shown; changes that fail the check are dropped and
the reply says why."""

import logging

from django.db import transaction

from ai.client import AIError, available, complete_json, note_fallback
from ai.schemas import AssistantTurn

from . import actions, context, fallback
from .models import ChatMessage

logger = logging.getLogger(__name__)
PROMPT = "assistant_v1"


def _from_model(student, conversation, question: ChatMessage) -> tuple[str, list[dict]]:
    payload = {
        "context": context.build(student, conversation, before_id=question.id),
        "message": question.text,
    }
    turn = complete_json(
        purpose="assistant", tier="planner", prompt=PROMPT,
        payload=payload, schema=AssistantTurn, max_tokens=1200,
    )  # fmt: skip
    return turn.reply, [a.model_dump(exclude_none=True) for a in turn.actions]


def answer(reply: ChatMessage) -> ChatMessage:
    conversation = reply.conversation
    student = conversation.student
    question = (
        conversation.messages.filter(role=ChatMessage.Role.STUDENT, id__lt=reply.id)
        .order_by("-id")
        .first()
    )
    text, raw_actions, used_ai = "", [], False
    if question and available():
        try:
            text, raw_actions = _from_model(student, conversation, question)
            used_ai = True
        except AIError as exc:
            note_fallback("assistant", str(exc))
    if not used_ai:
        result = fallback.answer(student, question.text if question else "")
        text, raw_actions = result.text, result.actions

    checked, problems = actions.check_all(student, raw_actions)
    if problems:
        text += "\n\nI couldn't set up part of that: " + " ".join(dict.fromkeys(problems))
    with transaction.atomic():
        if checked:
            conversation.messages.filter(proposal=ChatMessage.Proposal.PENDING).update(
                proposal=ChatMessage.Proposal.DECLINED,
                proposal_note="Replaced by a newer suggestion.",
            )
        reply.text = text.strip()
        reply.actions = [{**c.data, "summary": c.text} for c in checked]
        reply.proposal = ChatMessage.Proposal.PENDING if checked else ChatMessage.Proposal.NONE
        reply.state = ChatMessage.State.DONE
        reply.used_ai = used_ai
        reply.save()
    return reply


def confirm(message: ChatMessage) -> ChatMessage:
    """Apply a pending proposal. Each change is checked again, since the plan may have moved."""
    student = message.conversation.student
    stored = [{k: v for k, v in a.items() if k != "summary"} for a in message.actions]
    try:
        actions.apply_all(student, stored)
    except Exception as exc:  # noqa: BLE001 - every failure becomes a plain note on the card
        if not isinstance(exc, actions.Rejected):
            logger.exception("Applying assistant changes failed for message %s", message.id)
        message.proposal = ChatMessage.Proposal.FAILED
        message.proposal_note = actions.describe_rejection(exc)[:300]
    else:
        message.proposal = ChatMessage.Proposal.APPLIED
        message.proposal_note = ""
    message.save(update_fields=["proposal", "proposal_note", "updated_at"])
    return message
