import contextlib

from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.clock import now as clock_now
from config.throttles import LoginThrottle

from .export import build_export
from .models import StudentProfile, User
from .serializers import (
    AccessTokenSerializer,
    LoginSerializer,
    MeSerializer,
    MeUpdateSerializer,
    ProfileUpdateSerializer,
)


def _set_refresh_cookie(response: Response, refresh: str) -> None:
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path="/api/v1/auth/",
    )


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [LoginThrottle]

    @extend_schema(request=LoginSerializer, responses=AccessTokenSerializer)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refresh = RefreshToken.for_user(serializer.validated_data["user"])
        response = Response({"access": str(refresh.access_token)})
        _set_refresh_cookie(response, str(refresh))
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(request=None, responses=AccessTokenSerializer)
    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw:
            return Response({"detail": "Session expired."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            old = RefreshToken(raw)
            user_id = old["user_id"]
            old.blacklist()
        except TokenError:
            return Response({"detail": "Session expired."}, status=status.HTTP_401_UNAUTHORIZED)
        user = User.objects.filter(id=user_id, is_active=True).first()
        if user is None:
            return Response({"detail": "Session expired."}, status=status.HTTP_401_UNAUTHORIZED)
        new = RefreshToken.for_user(user)
        response = Response({"access": str(new.access_token)})
        _set_refresh_cookie(response, str(new))
        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if raw:
            with contextlib.suppress(TokenError):
                RefreshToken(raw).blacklist()
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/v1/auth/")
        return response


class MeView(APIView):
    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)

    @extend_schema(request=MeUpdateSerializer, responses=MeSerializer)
    def patch(self, request):
        serializer = MeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user
        profile_changed: list[str] = []
        with transaction.atomic():
            for field in ("first_name", "timezone"):
                if field in data:
                    setattr(user, field, data[field])
            user.save()
            if "profile" in data and user.is_student:
                profile, _ = StudentProfile.objects.get_or_create(user=user)
                profile_serializer = ProfileUpdateSerializer(
                    profile, data=request.data["profile"], partial=True
                )
                profile_serializer.is_valid(raise_exception=True)
                leaving_supportive = (
                    profile.supportive_mode
                    and profile_serializer.validated_data.get("supportive_mode") is False
                )
                profile_serializer.save(
                    **({"supportive_dismissed_at": clock_now(user)} if leaving_supportive else {})
                )
                profile_changed = list(profile_serializer.validated_data)
        if user.is_student and (
            "timezone" in data
            or {"max_hours_per_day", "session_minutes", "earliest_time", "latest_time"}
            & set(profile_changed)
        ):
            from pulse.services.replan import request_replan

            request_replan(user, reason="preferences")
        user.refresh_from_db()
        return Response(MeSerializer(user).data)

    @extend_schema(responses={204: None})
    def delete(self, request):
        request.user.delete()
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/v1/auth/")
        return response


class ExportView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request):
        response = Response(build_export(request.user))
        response["Content-Disposition"] = 'attachment; filename="pulse-export.json"'
        return response
