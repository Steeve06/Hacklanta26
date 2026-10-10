from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import ChatMessage, Conversation


class ProposedChangeSerializer(serializers.Serializer):
    type = serializers.CharField()
    summary = serializers.CharField()


class ChatMessageSerializer(serializers.ModelSerializer):
    changes = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        read_only_fields = fields = [
            "id",
            "role",
            "text",
            "state",
            "changes",
            "proposal",
            "proposal_note",
            "created_at",
        ]

    @staticmethod
    @extend_schema_field(ProposedChangeSerializer(many=True))
    def get_changes(message: ChatMessage) -> list[dict]:
        data = [{"type": a["type"], "summary": a.get("summary", "")} for a in message.actions]
        return ProposedChangeSerializer(data, many=True).data


class ConversationSerializer(serializers.ModelSerializer):
    """Also used for "no conversation yet", with a null id and no messages."""

    id = serializers.IntegerField(allow_null=True, read_only=True)
    created_at = serializers.DateTimeField(allow_null=True, read_only=True)
    messages = ChatMessageSerializer(many=True)

    class Meta:
        model = Conversation
        fields = ["id", "created_at", "messages"]


class NewMessageSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=1000, trim_whitespace=True)
