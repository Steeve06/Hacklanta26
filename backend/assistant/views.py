from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.clock import now as clock_now
from config.throttles import AssistantThrottle
from lms.access import require_student

from .models import ChatMessage, Conversation
from .replies import confirm
from .serializers import ChatMessageSerializer, ConversationSerializer, NewMessageSerializer
from .tasks import answer_message

EMPTY = {"id": None, "created_at": None, "messages": []}


def _student(request):
    require_student(request.user)
    if not request.user.profile.onboarding_done:
        raise PermissionDenied("Finish setting up Pulse first.")
    return request.user


def _current(student) -> Conversation | None:
    return (
        Conversation.objects.filter(student=student, closed_at__isnull=True)
        .prefetch_related("messages")
        .first()
    )


def _conversation_data(student) -> dict:
    conversation = _current(student)
    return ConversationSerializer(conversation).data if conversation else EMPTY


def _proposal(request, message_id: int) -> ChatMessage:
    student = _student(request)
    message = get_object_or_404(
        ChatMessage.objects.select_for_update().select_related("conversation__student"),
        pk=message_id,
        conversation__student=student,
        conversation__closed_at__isnull=True,
        role=ChatMessage.Role.ASSISTANT,
    )
    if message.proposal != ChatMessage.Proposal.PENDING:
        raise ValidationError({"detail": "This suggestion is no longer open."})
    return message


class ConversationView(APIView):
    @extend_schema(responses=ConversationSerializer)
    def get(self, request):
        return Response(_conversation_data(_student(request)))

    @extend_schema(request=None, responses={204: None})
    def delete(self, request):
        """Start over: the current conversation is closed and kept for the record."""
        student = _student(request)
        Conversation.objects.filter(student=student, closed_at__isnull=True).update(
            closed_at=clock_now(student)
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageCreateView(APIView):
    throttle_classes = [AssistantThrottle]

    @extend_schema(request=NewMessageSerializer, responses={202: ConversationSerializer})
    def post(self, request):
        student = _student(request)
        body = NewMessageSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        with transaction.atomic():
            conversation = _current(student) or Conversation.objects.create(student=student)
            conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
            if conversation.messages.filter(state=ChatMessage.State.PENDING).exists():
                raise ValidationError({"text": "Wait for the answer to your last message."})
            ChatMessage.objects.create(
                conversation=conversation, role=ChatMessage.Role.STUDENT,
                text=body.validated_data["text"],
            )  # fmt: skip
            reply = ChatMessage.objects.create(
                conversation=conversation, role=ChatMessage.Role.ASSISTANT,
                state=ChatMessage.State.PENDING,
            )  # fmt: skip
            transaction.on_commit(lambda: answer_message.delay(reply.id))
        return Response(_conversation_data(student), status=status.HTTP_202_ACCEPTED)


class ConfirmView(APIView):
    @extend_schema(request=None, responses=ChatMessageSerializer)
    def post(self, request, message_id: int):
        with transaction.atomic():
            message = confirm(_proposal(request, message_id))
        return Response(ChatMessageSerializer(message).data)


class DeclineView(APIView):
    @extend_schema(request=None, responses=ChatMessageSerializer)
    def post(self, request, message_id: int):
        with transaction.atomic():
            message = _proposal(request, message_id)
            message.proposal = ChatMessage.Proposal.DECLINED
            message.save(update_fields=["proposal", "updated_at"])
        return Response(ChatMessageSerializer(message).data)
