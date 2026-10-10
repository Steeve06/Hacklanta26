from rest_framework import serializers

from .delivery import TITLES
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    heading = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "trigger",
            "tier",
            "heading",
            "text",
            "link",
            "sent_at",
            "read_at",
            "action_taken",
        ]
        read_only_fields = fields

    def get_heading(self, obj) -> str:
        return TITLES.get(obj.trigger, "Reminder")


class InboxSerializer(serializers.Serializer):
    unread = serializers.IntegerField()
    supportive_mode = serializers.BooleanField()
    support_url = serializers.URLField()
    results = NotificationSerializer(many=True)


class ActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["open", "snooze", "tone_down"])


class ActionResultSerializer(serializers.Serializer):
    notification = NotificationSerializer()
    sass_level = serializers.IntegerField()
    supportive_mode = serializers.BooleanField()


class PushKeysSerializer(serializers.Serializer):
    p256dh = serializers.CharField()
    auth = serializers.CharField()


class PushSubscribeSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=600)
    keys = PushKeysSerializer()


class PushUnsubscribeSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=600)


class PushTestSerializer(serializers.Serializer):
    sent = serializers.IntegerField(help_text="devices that accepted the test push")


class PushConfigSerializer(serializers.Serializer):
    public_key = serializers.CharField(allow_blank=True)
    enabled = serializers.BooleanField()
