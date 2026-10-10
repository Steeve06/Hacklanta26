import pytest
from django.conf import settings

pytestmark = pytest.mark.django_db


def login(api, email, password="correct-horse"):
    return api.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")


def test_login_returns_access_and_sets_httponly_refresh_cookie(api, student):
    response = login(api, student.email)
    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" not in response.data
    cookie = response.cookies[settings.REFRESH_COOKIE_NAME]
    assert cookie["httponly"]


def test_login_rejects_wrong_password(api, student):
    response = login(api, student.email, "nope")
    assert response.status_code == 400


def test_refresh_rotates_and_blacklists_old_token(api, student):
    login(api, student.email)
    old_cookie = api.cookies[settings.REFRESH_COOKIE_NAME].value
    first = api.post("/api/v1/auth/refresh")
    assert first.status_code == 200
    assert api.cookies[settings.REFRESH_COOKIE_NAME].value != old_cookie
    api.cookies[settings.REFRESH_COOKIE_NAME] = old_cookie
    reused = api.post("/api/v1/auth/refresh")
    assert reused.status_code == 401


def test_refresh_without_cookie_is_unauthorized(api):
    assert api.post("/api/v1/auth/refresh").status_code == 401


def test_login_is_rate_limited(api, student):
    for _ in range(5):
        login(api, student.email, "wrong")
    assert login(api, student.email).status_code == 429


def test_me_requires_auth(api):
    assert api.get("/api/v1/me").status_code == 401


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
    from accounts.models import User

    assert not User.objects.filter(pk=student.pk).exists()


def test_health(api):
    response = api.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
