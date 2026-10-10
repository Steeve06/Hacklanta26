import logging

from celery import shared_task

from .models import ChatMessage
from .replies import answer

logger = logging.getLogger(__name__)
FAILED_TEXT = "Sorry, I couldn't answer that just now. Try again in a moment."


@shared_task
def answer_message(message_id: int) -> None:
    reply = (
        ChatMessage.objects.select_related("conversation__student")
        .filter(pk=message_id, state=ChatMessage.State.PENDING)
        .first()
    )
    if reply is None:
        return
    try:
        answer(reply)
    except Exception:
        logger.exception("Assistant reply %s failed", message_id)
        ChatMessage.objects.filter(pk=message_id).update(
            state=ChatMessage.State.FAILED, text=FAILED_TEXT
        )
