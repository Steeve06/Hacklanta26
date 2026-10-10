import re
from datetime import timedelta

import pytest
import time_machine
from django.conf import settings
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AuthSession, User
from lms.models import Enrollment

from .factories import CourseFactory, StudentFactory, TermFactory

pytestmark = pytest.mark.django_db
CSRF = {"HTTP_X_REQUESTED_WITH": "pulse"}
GOOD_PASSWORD = "maple-river-lantern"


def login(api, email, password="correct-horse", **extra):
    return api.post(
        "/api/v1/auth/login", {"email": email, "password": password, **extra}, format="json"
    )


def refresh(api):
    return api.post("/api/v1/auth/refresh", **CSRF)


def bearer(token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def signup(api, **overrides):
    body = {
        "first_name": "Nia",
        "last_name": "Okoro",
        "email": "nia@example.edu",
        "password": GOOD_PASSWORD,
        "password_confirm": GOOD_PASSWORD,
        "timezone": "America/Chicago",
        **overrides,
    }
    return api.post("/api/v1/auth/signup", body, format="json")


class TestLogin:
    def test_returns_access_and_sets_httponly_lax_refresh_cookie(self, api, student):
        response = login(api, student.email)
        assert response.status_code == 200
        assert "access" in response.data and "refresh" not in response.data
        cookie = response.cookies[settings.REFRESH_COOKIE_NAME]
        assert cookie["httponly"]
        assert cookie["samesite"] == "Lax"
        assert int(cookie["max-age"]) == 7 * 24 * 3600

    def test_remember_me_keeps_the_session_30_days(self, api, student):
        response = login(api, student.email, remember=True)
        assert int(response.cookies[settings.REFRESH_COOKIE_NAME]["max-age"]) == 30 * 24 * 3600
        rotated = refresh(api)
        assert int(rotated.cookies[settings.REFRESH_COOKIE_NAME]["max-age"]) == 30 * 24 * 3600

    def test_email_is_case_and_space_insensitive(self, api, student):
        assert login(api, f"  {student.email.upper()} ").status_code == 200

    def test_wrong_password_and_unknown_email_get_the_same_error(self, api, student):
        wrong = login(api, student.email, "nope")
        unknown = login(api, "nobody@example.edu", "nope")
        assert wrong.status_code == unknown.status_code == 400
        assert wrong.data == unknown.data == {"detail": "Email or password is incorrect."}

    def test_rate_limited_per_ip(self, api, student):
        for _ in range(5):
            login(api, student.email, "wrong")
        assert login(api, student.email).status_code == 429

    def test_rate_limited_per_email_across_ips(self, student):
        for i in range(5):
            login(APIClient(REMOTE_ADDR=f"10.0.0.{i}"), student.email, "wrong")
        assert login(APIClient(REMOTE_ADDR="10.0.1.1"), student.email).status_code == 429

    def test_ten_failures_lock_the_email_for_15_minutes(self, student, monkeypatch):
        from config.throttles import AuthEmailThrottle, AuthIPThrottle

        for throttle in (AuthIPThrottle, AuthEmailThrottle):
            monkeypatch.setattr(throttle, "allow_request", lambda *args: True)
        for _ in range(10):
            login(APIClient(), student.email, "wrong")
        locked = login(APIClient(), student.email)
        assert locked.status_code == 429
        assert "15 minutes" in locked.data["detail"]
        with time_machine.travel(timezone.now() + timedelta(minutes=16)):
            assert login(APIClient(), student.email).status_code == 200

    def test_passwords_are_hashed_with_argon2_outside_tests(self):
        assert settings.PASSWORD_HASHERS  # tests use MD5 for speed
        from config.settings import base

        assert base.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")


class TestRefreshAndLogout:
    def test_refresh_rotates_and_blacklists_old_token(self, api, student):
        login(api, student.email)
        old_cookie = api.cookies[settings.REFRESH_COOKIE_NAME].value
        first = refresh(api)
        assert first.status_code == 200
        assert api.cookies[settings.REFRESH_COOKIE_NAME].value != old_cookie
        api.cookies[settings.REFRESH_COOKIE_NAME] = old_cookie
        assert refresh(api).status_code == 401

    def test_refresh_without_cookie_is_unauthorized(self, api):
        assert refresh(api).status_code == 401

    def test_refresh_needs_the_csrf_header_and_an_allowed_origin(self, api, student):
        login(api, student.email)
        assert api.post("/api/v1/auth/refresh").status_code == 403
        evil = api.post("/api/v1/auth/refresh", HTTP_ORIGIN="https://evil.example", **CSRF)
        assert evil.status_code == 403
        allowed = api.post(
            "/api/v1/auth/refresh", HTTP_ORIGIN=settings.CORS_ALLOWED_ORIGINS[0], **CSRF
        )
        assert allowed.status_code == 200

    def test_logout_ends_the_session_in_every_tab(self, api, student):
        access = login(api, student.email).data["access"]
        other_tab = bearer(access)
        assert other_tab.get("/api/v1/me").status_code == 200
        assert api.post("/api/v1/auth/logout", **CSRF).status_code == 204
        assert other_tab.get("/api/v1/me").status_code == 401
        assert refresh(api).status_code == 401

    def test_access_tokens_from_older_sessions_are_rejected(self, student):
        from rest_framework_simplejwt.tokens import AccessToken

        legacy = AccessToken.for_user(student)
        assert bearer(str(legacy)).get("/api/v1/me").status_code == 401


class TestSignup:
    def test_creates_a_student_signs_in_and_enrols_in_the_current_term(self, api):
        old_term = TermFactory(start_date=timezone.localdate() - timedelta(days=400))
        CourseFactory(term=old_term)
        term = TermFactory(start_date=timezone.localdate() - timedelta(days=10))
        courses = [CourseFactory(term=term) for _ in range(3)]
        response = signup(api, email="  Nia@Example.EDU ")
        assert response.status_code == 201
        user = User.objects.get(email="nia@example.edu")
        assert user.role == "student" and user.timezone == "America/Chicago"
        assert user.check_password(GOOD_PASSWORD)
        assert not user.password.startswith(GOOD_PASSWORD)
        enrolled = set(Enrollment.objects.filter(user=user).values_list("course_id", flat=True))
        assert enrolled == {c.id for c in courses}
        assert bearer(response.data["access"]).get("/api/v1/me").status_code == 200
        assert settings.REFRESH_COOKIE_NAME in response.cookies

    def test_existing_email_in_any_case_is_a_field_error(self, api, student):
        response = signup(api, email=student.email.upper())
        assert response.status_code == 400
        assert response.data["email"] == ["An account with this email already exists."]

    @pytest.mark.parametrize(
        ("password", "fragment"),
        [
            ("short-pw", "at least 10"),
            ("1234567890123", "entirely numeric"),
            ("password123", "too common"),
            ("nia.example.edu", "too similar"),
        ],
    )
    def test_password_rules(self, api, password, fragment):
        response = signup(api, password=password, password_confirm=password)
        assert response.status_code == 400
        assert any(fragment in m for m in response.data["password"]), response.data

    def test_confirmation_must_match(self, api):
        response = signup(api, password_confirm="something-else-entirely")
        assert response.data["password_confirm"] == ["Passwords don't match."]

    def test_signup_is_throttled(self, api):
        for i in range(5):
            signup(api, email=f"x{i}@example.edu")
        assert signup(api, email="x9@example.edu").status_code == 429


class TestPasswordReset:
    def _link(self, user, api):
        mail.outbox.clear()
        response = api.post("/api/v1/auth/password/reset", {"email": user.email}, format="json")
        assert response.data == {"detail": "If that email exists, we sent a link."}
        body = mail.outbox[0].body
        uid, token = re.search(r"uid=([^&\s]+)&token=(\S+)", body).groups()
        return uid, token

    def _confirm(self, api, uid, token, password=GOOD_PASSWORD):
        return api.post(
            "/api/v1/auth/password/reset/confirm",
            {"uid": uid, "token": token, "password": password, "password_confirm": password},
            format="json",
        )

    def test_unknown_email_gets_the_same_answer_and_no_mail(self, api):
        mail.outbox.clear()
        response = api.post(
            "/api/v1/auth/password/reset", {"email": "ghost@example.edu"}, format="json"
        )
        assert response.status_code == 200
        assert response.data == {"detail": "If that email exists, we sent a link."}
        assert mail.outbox == []

    def test_link_resets_once_and_signs_out_everywhere(self, api, student):
        session_access = login(APIClient(), student.email).data["access"]
        uid, token = self._link(student, api)
        assert "localhost:5173/reset-password" in mail.outbox[0].body
        assert self._confirm(api, uid, token).status_code == 200
        student.refresh_from_db()
        assert student.check_password(GOOD_PASSWORD)
        assert bearer(session_access).get("/api/v1/me").status_code == 401
        assert self._confirm(api, uid, token, "another-good-phrase").status_code == 400

    def test_link_expires_after_an_hour(self, api, student):
        uid, token = self._link(student, api)
        with time_machine.travel(timezone.now() + timedelta(minutes=61)):
            assert self._confirm(api, uid, token).status_code == 400

    def test_new_password_is_validated(self, api, student):
        uid, token = self._link(student, api)
        response = self._confirm(api, uid, token, "1234567890")
        assert response.status_code == 400 and "password" in response.data


class TestPasswordChange:
    def test_change_keeps_this_session_and_ends_the_others(self, student):
        this = APIClient()
        this_access = login(this, student.email).data["access"]
        other_access = login(APIClient(), student.email).data["access"]
        response = bearer(this_access).post(
            "/api/v1/auth/password/change",
            {
                "current_password": "correct-horse",
                "new_password": GOOD_PASSWORD,
                "new_password_confirm": GOOD_PASSWORD,
            },
            format="json",
        )
        assert response.status_code == 200
        assert bearer(this_access).get("/api/v1/me").status_code == 200
        assert bearer(other_access).get("/api/v1/me").status_code == 401
        assert AuthSession.objects.filter(user=student, revoked_at__isnull=True).count() == 1

    def test_wrong_current_password(self, student_api):
        response = student_api.post(
            "/api/v1/auth/password/change",
            {
                "current_password": "nope",
                "new_password": GOOD_PASSWORD,
                "new_password_confirm": GOOD_PASSWORD,
            },
            format="json",
        )
        assert response.status_code == 400 and "current_password" in response.data


def test_me_requires_auth(api):
    assert api.get("/api/v1/me").status_code == 401


def test_public_endpoints_are_only_the_auth_ones(api):
    for path in ["/api/v1/courses", "/api/v1/pulse/status", "/api/v1/notifications", "/api/v1/me"]:
        assert api.get(path).status_code == 401
    assert api.post("/api/v1/auth/password/change", {}, format="json").status_code == 401


def test_me_patch_updates_profile_and_validates(student_api):
    ok = student_api.patch("/api/v1/me/profile", {"profile": {"sass_level": 2}}, format="json")
    assert ok.status_code == 200
    assert ok.data["profile"]["sass_level"] == 2
    bad = student_api.patch("/api/v1/me/profile", {"profile": {"sass_level": 9}}, format="json")
    assert bad.status_code == 400


def test_me_rejects_unknown_timezone(student_api):
    response = student_api.patch("/api/v1/me", {"timezone": "Mars/Olympus"}, format="json")
    assert response.status_code == 400


def test_export_and_delete_account(student_api, student):
    export = student_api.get("/api/v1/me/export")
    assert export.status_code == 200
    assert export.data["user"]["email"] == student.email
    assert student_api.delete("/api/v1/me").status_code == 204
    assert not User.objects.filter(pk=student.pk).exists()


def test_health(api):
    response = api.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_factory_students_can_log_in():
    student = StudentFactory()
    assert login(APIClient(), student.email).status_code == 200
