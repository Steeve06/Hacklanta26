"""Sessions, tokens and login lockout.

Each sign-in creates an AuthSession. Its id travels in the refresh token and in every access
token minted from it (claim `sid`). Logging out, changing or resetting a password revokes
sessions, and the authentication class rejects access tokens from revoked sessions, so other
tabs are signed out on their next request instead of when their token expires.
"""

from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AuthSession, User

REMEMBER_LIFETIME = timedelta(days=30)
SESSION_CACHE_SECONDS = 60
LOCK_AFTER_FAILURES = 10
LOCK_SECONDS = 15 * 60


def refresh_lifetime(remember: bool) -> timedelta:
    return REMEMBER_LIFETIME if remember else settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]


def issue(session: AuthSession) -> RefreshToken:
    refresh = RefreshToken.for_user(session.user)
    refresh["sid"] = str(session.id)
    refresh.set_exp(lifetime=refresh_lifetime(session.remember))
    return refresh


def start_session(user: User, remember: bool = False) -> RefreshToken:
    return issue(AuthSession.objects.create(user=user, remember=remember))


def _cache_key(sid: str) -> str:
    return f"auth:session:{sid}"


def session_is_active(sid: str | None) -> bool:
    if not sid:
        return False
    cached = cache.get(_cache_key(sid))
    if cached is not None:
        return cached
    active = AuthSession.objects.filter(pk=sid, revoked_at__isnull=True).exists()
    cache.set(_cache_key(sid), active, SESSION_CACHE_SECONDS)
    return active


def revoke(sessions) -> int:
    ids = [str(i) for i in sessions.filter(revoked_at__isnull=True).values_list("id", flat=True)]
    AuthSession.objects.filter(pk__in=ids).update(revoked_at=timezone.now())
    cache.set_many({_cache_key(i): False for i in ids}, SESSION_CACHE_SECONDS)
    return len(ids)


def revoke_session(sid: str | None) -> None:
    if sid:
        revoke(AuthSession.objects.filter(pk=sid))


def revoke_all(user: User, keep: str | None = None) -> int:
    sessions = AuthSession.objects.filter(user=user)
    if keep:
        sessions = sessions.exclude(pk=keep)
    return revoke(sessions)


class SessionJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        if not session_is_active(token.get("sid")):
            raise AuthenticationFailed("Session expired.", code="session_revoked")
        return token


def _fail_key(email: str) -> str:
    return f"auth:fail:{email}"


def _lock_key(email: str) -> str:
    return f"auth:lock:{email}"


def is_locked(email: str) -> bool:
    return bool(cache.get(_lock_key(email)))


def record_failure(email: str) -> None:
    key = _fail_key(email)
    cache.add(key, 0, LOCK_SECONDS)
    failures = cache.incr(key)
    if failures >= LOCK_AFTER_FAILURES:
        cache.set(_lock_key(email), True, LOCK_SECONDS)
        cache.delete(key)


def clear_failures(email: str) -> None:
    cache.delete(_fail_key(email))
