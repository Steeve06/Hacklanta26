import json

from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.clock import now as clock_now
from accounts.models import StudentProfile
from lms.access import require_student

from . import delivery
from .models import Notification, PushSubscription
from .serializers import (
    ActionResultSerializer,
    ActionSerializer,
    InboxSerializer,
    NotificationSerializer,
    PushConfigSerializer,
    PushSubscribeSerializer,
    PushTestSerializer,
    PushUnsubscribeSerializer,
)
from .services import inbox, take_action

PAGE = 50


class InboxView(APIView):
    @extend_schema(responses=InboxSerializer)
    def get(self, request):
        require_student(request.user)
        rows = inbox(request.user)
        profile, _ = StudentProfile.objects.get_or_create(user=request.user)
        return Response(
            InboxSerializer(
                {
                    "unread": rows.filter(read_at__isnull=True).count(),
                    "supportive_mode": profile.supportive_mode,
                    "support_url": settings.CAMPUS_SUPPORT_URL,
                    "results": rows[:PAGE],
                }
            ).data
        )


class ReadView(APIView):
    @extend_schema(request=None, responses=NotificationSerializer)
    def post(self, request, notification_id: int):
        n = get_object_or_404(Notification, pk=notification_id, student=request.user)
        if n.read_at is None:
            n.read_at = clock_now(request.user)
            n.save(update_fields=["read_at", "updated_at"])
        return Response(NotificationSerializer(n).data)


class ReadAllView(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        inbox(request.user).filter(read_at__isnull=True).update(read_at=clock_now(request.user))
        return Response(status=204)


class ActionView(APIView):
    @extend_schema(request=ActionSerializer, responses=ActionResultSerializer)
    def post(self, request, notification_id: int):
        n = get_object_or_404(Notification, pk=notification_id, student=request.user)
        serializer = ActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = take_action(request.user, n, serializer.validated_data["action"])
        return Response(
            ActionResultSerializer(
                {
                    "notification": n,
                    "sass_level": profile.sass_level,
                    "supportive_mode": profile.supportive_mode,
                }
            ).data
        )


class PushTestView(APIView):
    """Send a sample reminder to this user's devices, so they can see push works."""

    @extend_schema(request=None, responses=PushTestSerializer)
    def post(self, request):
        if not delivery.push_configured():
            return Response({"detail": "Push isn't set up on this server."}, status=503)
        if not PushSubscription.objects.filter(user=request.user).exists():
            return Response({"detail": "Turn on push on this device first."}, status=409)
        payload = json.dumps(
            {
                "title": "Leon · Test",
                "body": "Push works. This is how your reminders will arrive.",
                "url": "/pulse/today",
            }
        )
        sent = delivery.send_to_devices(request.user, payload)
        return Response({"sent": sent})


class PushView(APIView):
    @extend_schema(responses=PushConfigSerializer)
    def get(self, request):
        return Response(
            {"public_key": settings.VAPID_PUBLIC_KEY, "enabled": delivery.push_configured()}
        )

    @extend_schema(request=PushSubscribeSerializer, responses={201: None})
    def post(self, request):
        serializer = PushSubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        PushSubscription.objects.update_or_create(
            endpoint=data["endpoint"], defaults={"user": request.user, "keys": dict(data["keys"])}
        )
        StudentProfile.objects.filter(user=request.user).update(push_prompt_seen=True)
        return Response(status=201)

    @extend_schema(
        parameters=[OpenApiParameter("endpoint", str, required=True)], responses={204: None}
    )
    def delete(self, request):
        serializer = PushUnsubscribeSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        PushSubscription.objects.filter(
            user=request.user, endpoint=serializer.validated_data["endpoint"]
        ).delete()
        return Response(status=204)
