import contextlib

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.clock import now as clock_now
from config.throttles import AUTH_THROTTLES, AuthIPThrottle
from lms.enrolment import enroll_in_current_term

from . import auth
from .export import build_export
from .models import AuthSession, StudentProfile, User
from .reset import send_reset_email, user_from_reset_link
from .serializers import (
    AccessTokenSerializer,
    DetailSerializer,
    LoginSerializer,
    MeSerializer,
    MeUpdateSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileUpdateSerializer,
    SignupSerializer,
)

COOKIE_PATH = "/api/v1/auth/"
RESET_SENT = "If that email exists, we sent a link."
BAD_LOGIN = "Email or password is incorrect."
LOCKED = "Too many failed sign-in attempts. Try again in 15 minutes."


def _set_refresh_cookie(response: Response, refresh: RefreshToken, remember: bool) -> None:
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        str(refresh),
        max_age=int(auth.refresh_lifetime(remember).total_seconds()),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=COOKIE_PATH,
    )


def _signed_in(refresh: RefreshToken, remember: bool, status_code: int = 200) -> Response:
    response = Response({"access": str(refresh.access_token)}, status=status_code)
    _set_refresh_cookie(response, refresh, remember)
    return response


def _clear_cookie(response: Response) -> Response:
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=COOKIE_PATH)
    return response


def _csrf_ok(request) -> bool:
    """Cookie-authenticated endpoints need our custom header (which forces a CORS preflight that
    only the frontend origin passes) and, when the browser sends one, an allowed Origin."""
    if request.headers.get("X-Requested-With") != "pulse":
        return False
    origin = request.headers.get("Origin")
    return (
        not origin
        or origin in settings.CORS_ALLOWED_ORIGINS
        or (origin.split("://", 1)[-1] == request.get_host())
    )


def _forbidden_csrf() -> Response:
    return Response({"detail": "Request blocked."}, status=status.HTTP_403_FORBIDDEN)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = AUTH_THROTTLES

    @extend_schema(request=LoginSerializer, responses=AccessTokenSerializer)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        if auth.is_locked(email):
            return Response({"detail": LOCKED}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        user = authenticate(request, email=email, password=serializer.validated_data["password"])
        if user is None or not user.is_active:
            auth.record_failure(email)
            return Response({"detail": BAD_LOGIN}, status=status.HTTP_400_BAD_REQUEST)
        auth.clear_failures(email)
        remember = serializer.validated_data["remember"]
        return _signed_in(auth.start_session(user, remember), remember)


class SignupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = AUTH_THROTTLES

    @extend_schema(request=SignupSerializer, responses={201: AccessTokenSerializer})
    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    data["email"],
                    data["password"],
                    first_name=data["first_name"].strip(),
                    last_name=data["last_name"].strip(),
                    timezone=data.get("timezone") or User._meta.get_field("timezone").default,
                    role=User.Role.STUDENT,
                )
                enroll_in_current_term(user)
        except IntegrityError:
            return Response(
                {"email": ["An account with this email already exists."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _signed_in(auth.start_session(user), False, status.HTTP_201_CREATED)


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(request=None, responses=AccessTokenSerializer)
    def post(self, request):
        if not _csrf_ok(request):
            return _forbidden_csrf()
        expired = _clear_cookie(
            Response({"detail": "Session expired."}, status=status.HTTP_401_UNAUTHORIZED)
        )
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw:
            return expired
        try:
            old = RefreshToken(raw)
            old.blacklist()
        except TokenError:
            return expired
        session = (
            AuthSession.objects.select_related("user")
            .filter(pk=old.get("sid"), revoked_at__isnull=True, user__is_active=True)
            .first()
        )
        if session is None:
            return expired
        return _signed_in(auth.issue(session), session.remember)


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        if not _csrf_ok(request):
            return _forbidden_csrf()
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if raw:
            with contextlib.suppress(TokenError):
                token = RefreshToken(raw)
                auth.revoke_session(token.get("sid"))
                token.blacklist()
        return _clear_cookie(Response(status=status.HTTP_204_NO_CONTENT))


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = AUTH_THROTTLES

    @extend_schema(request=PasswordResetRequestSerializer, responses=DetailSerializer)
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"], is_active=True
        ).first()
        if user is not None:
            send_reset_email(user)
        return Response({"detail": RESET_SENT})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [AuthIPThrottle]

    @extend_schema(request=PasswordResetConfirmSerializer, responses=DetailSerializer)
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = user_from_reset_link(data["uid"], data["token"])
        if user is None:
            return Response(
                {"detail": "This reset link is invalid or has expired. Ask for a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_password(data["password"], user=user)
        except DjangoValidationError as exc:
            return Response({"password": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            user.set_password(data["password"])
            user.save(update_fields=["password", "updated_at"])
            auth.revoke_all(user)
        auth.clear_failures(user.email)
        return Response({"detail": "Password changed. Sign in with your new password."})


class PasswordChangeView(APIView):
    @extend_schema(request=PasswordChangeSerializer, responses=DetailSerializer)
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        user = request.user
        with transaction.atomic():
            user.set_password(serializer.validated_data["new_password"])
            user.save(update_fields=["password", "updated_at"])
            auth.revoke_all(user, keep=request.auth.get("sid") if request.auth else None)
        return Response({"detail": "Password changed. Other devices have been signed out."})


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
        return _clear_cookie(Response(status=status.HTTP_204_NO_CONTENT))


class ExportView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request):
        response = Response(build_export(request.user))
        response["Content-Disposition"] = 'attachment; filename="pulse-export.json"'
        return response
