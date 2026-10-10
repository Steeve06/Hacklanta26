from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from accounts.models import StudentProfile, User
from pulse.models import AvailabilityBlock, Onboarding

from .factories import (
    AssessmentFactory,
    ChapterFactory,
    CourseFactory,
    InstructorFactory,
    StudentFactory,
    enroll,
)
from .test_pulse import client_for

pytestmark = pytest.mark.django_db
URL = "/api/v1/onboarding"
BLOCKS = [
    {"weekday": 0, "start_time": "18:00", "end_time": "21:00"},
    {"weekday": 2, "start_time": "18:00", "end_time": "21:00"},
    {"weekday": 5, "start_time": "10:00", "end_time": "14:00"},
]
PREFS = {
    "max_hours_per_day": "3.0",
    "session_minutes": 50,
    "earliest_time": "08:00",
    "latest_time": "22:00",
    "timezone": "America/Chicago",
}
STYLE = {"sass_level": 3, "quiet_start": "22:30", "quiet_end": "07:30"}


@pytest.fixture
def newcomer():
    student = StudentFactory()
    course = CourseFactory()
    enroll(student, course)
    chapter = ChapterFactory(course=course)
    homework = AssessmentFactory(
        course=course, est_minutes=60, due_at=timezone.now() + timedelta(days=5)
    )
    homework.chapters.set([chapter])
    return student


def patch(client, step, data=None, version=None):
    body = {"step": step}
    if data is not None:
        body["data"] = data
    if version is not None:
        body["version"] = version
    return client.patch(URL, body, format="json")


def finish_steps_1_to_4(client):
    for step, data in [(1, {}), (2, {"blocks": BLOCKS}), (3, PREFS), (4, STYLE)]:
        response = patch(client, step, data)
        assert response.status_code == 200, response.data
    return response


def test_new_student_starts_at_step_one_with_defaults(newcomer):
    data = client_for(newcomer).get(URL).data
    assert data["step"] == 1
    assert data["completed_steps"] == []
    assert data["done"] is False and data["schedule_ready"] is False
    assert data["notifications"]["sass_level"] == 2
    assert data["availability"]["blocks"] == []


def test_steps_must_be_done_in_order(newcomer):
    client = client_for(newcomer)
    response = patch(client, 3, PREFS)
    assert response.status_code == 400
    assert response.data["step"] == "Finish step 1 first."
    assert patch(client, 2).status_code == 400


def test_step_one_needs_a_course():
    lonely = StudentFactory()
    response = patch(client_for(lonely), 1, {})
    assert response.status_code == 400


def test_each_step_saves_to_its_real_table_and_advances(newcomer):
    client = client_for(newcomer)
    assert patch(client, 1, {}).data["step"] == 2

    empty = patch(client, 2, {"blocks": []})
    assert empty.status_code == 400
    overlapping = [*BLOCKS, {"weekday": 0, "start_time": "20:00", "end_time": "22:00"}]
    saved = patch(client, 2, {"blocks": overlapping})
    assert saved.data["step"] == 3
    assert saved.data["note"] == "Merged 1 overlapping block."
    assert AvailabilityBlock.objects.filter(student=newcomer).count() == 3

    patch(client, 3, PREFS)
    newcomer.refresh_from_db()
    assert newcomer.timezone == "America/Chicago"
    assert newcomer.profile.max_hours_per_day == Decimal("3.0")

    styled = patch(client, 4, STYLE)
    assert styled.data["step"] == 5
    assert styled.data["completed_steps"] == [1, 2, 3, 4]
    profile = StudentProfile.objects.get(user=newcomer)
    assert (profile.sass_level, profile.quiet_start) == (3, time(22, 30))


@pytest.mark.parametrize(
    ("step", "data", "field"),
    [
        (3, {**PREFS, "max_hours_per_day": "0.5"}, "max_hours_per_day"),
        (3, {**PREFS, "max_hours_per_day": "13"}, "max_hours_per_day"),
        (3, {**PREFS, "session_minutes": 30}, "session_minutes"),
        (3, {**PREFS, "latest_time": "07:00"}, "latest_time"),
        (3, {**PREFS, "timezone": "Mars/Olympus"}, "timezone"),
        (4, {**STYLE, "sass_level": 5}, "sass_level"),
        (4, {**STYLE, "sass_level": 0}, "sass_level"),
        (4, {**STYLE, "quiet_end": "22:30"}, "quiet_end"),
    ],
)
def test_step_validation(newcomer, step, data, field):
    client = client_for(newcomer)
    patch(client, 1, {})
    patch(client, 2, {"blocks": BLOCKS})
    if step == 4:
        patch(client, 3, PREFS)
    response = patch(client, step, data)
    assert response.status_code == 400
    assert field in response.data


def test_resume_after_closing_the_tab(newcomer):
    client = client_for(newcomer)
    patch(client, 1, {})
    patch(client, 2, {"blocks": BLOCKS})
    reopened = client_for(User.objects.get(pk=newcomer.pk)).get(URL).data
    assert reopened["step"] == 3
    assert len(reopened["availability"]["blocks"]) == 3


def test_back_navigation_is_saved(newcomer):
    client = client_for(newcomer)
    finish_steps_1_to_4(client)
    assert patch(client, 2).data["step"] == 2
    assert client.get(URL).data["step"] == 2


def generate(client, capture):
    with capture(execute=True):
        response = client.post("/api/v1/pulse/schedules/generate", {}, format="json")
    assert response.status_code == 202
    return response


def test_complete_needs_a_current_schedule(newcomer, django_capture_on_commit_callbacks):
    client = client_for(newcomer)
    finish_steps_1_to_4(client)
    early = client.post(f"{URL}/complete")
    assert early.status_code == 400 and "schedule" in early.data

    generate(client, django_capture_on_commit_callbacks)
    assert client.get(URL).data["schedule_ready"] is True

    patch(client, 2, {"blocks": BLOCKS[:2]})
    assert client.get(URL).data["schedule_ready"] is False
    assert client.post(f"{URL}/complete").status_code == 400

    generate(client, django_capture_on_commit_callbacks)
    done = client.post(f"{URL}/complete")
    assert done.status_code == 200
    assert done.data["profile"]["onboarding_done"] is True
    assert client.get(URL).data["done"] is True


def test_unchanged_answers_keep_the_schedule(newcomer, django_capture_on_commit_callbacks):
    client = client_for(newcomer)
    finish_steps_1_to_4(client)
    generate(client, django_capture_on_commit_callbacks)
    patch(client, 3, PREFS)
    patch(client, 4, {**STYLE, "sass_level": 1})
    assert client.get(URL).data["schedule_ready"] is True


def test_second_tab_learns_it_was_stale_and_last_save_wins(newcomer):
    tab_a, tab_b = client_for(newcomer), client_for(newcomer)
    patch(tab_a, 1, {})
    version = tab_a.get(URL).data["version"]
    first = patch(tab_a, 2, {"blocks": BLOCKS}, version=version)
    assert first.data["stale"] is False
    second = patch(tab_b, 2, {"blocks": BLOCKS[:1]}, version=version)
    assert second.data["stale"] is True
    assert len(second.data["availability"]["blocks"]) == 1
    assert AvailabilityBlock.objects.filter(student=newcomer).count() == 1


def test_only_students_have_onboarding():
    instructor = InstructorFactory()
    assert client_for(instructor).get(URL).status_code == 403


def test_onboarded_students_are_shown_as_done():
    student = StudentFactory()
    StudentProfile.objects.filter(user=student).update(onboarding_done=True)
    student.refresh_from_db()
    data = client_for(student).get(URL).data
    assert data["done"] is True and data["completed_steps"] == [1, 2, 3, 4, 5]


class TestConstraints:
    def test_one_onboarding_per_student(self, newcomer):
        client_for(newcomer).get(URL)
        with pytest.raises(IntegrityError), transaction.atomic():
            Onboarding.objects.create(student=newcomer)

    def test_email_is_unique_in_any_case(self):
        StudentFactory(email="dup@example.edu")
        with pytest.raises(IntegrityError), transaction.atomic():
            User.objects.create(email="dup@example.edu", first_name="B")
        user = User.objects.create(email="  Mixed@Example.EDU ", first_name="C")
        assert user.email == "mixed@example.edu"

    @pytest.mark.parametrize(
        "values",
        [
            {"sass_level": 0},
            {"sass_level": 5},
            {"max_hours_per_day": Decimal("0.5")},
            {"max_hours_per_day": 13},
            {"session_minutes": 30},
            {"earliest_time": time(23), "latest_time": time(7)},
        ],
    )
    def test_profile_ranges(self, values):
        student = StudentFactory()
        with pytest.raises(IntegrityError), transaction.atomic():
            StudentProfile.objects.filter(user=student).update(**values)

    def test_availability_end_after_start(self):
        student = StudentFactory()
        with pytest.raises(IntegrityError), transaction.atomic():
            AvailabilityBlock.objects.create(
                student=student, weekday=0, start_time=time(18), end_time=time(17)
            )

    @pytest.mark.skipif(
        connection.vendor != "postgresql", reason="SQLite can't evaluate time arithmetic checks"
    )
    def test_availability_minimum_30_minutes(self):
        student = StudentFactory()
        with pytest.raises(IntegrityError), transaction.atomic():
            AvailabilityBlock.objects.create(
                student=student, weekday=0, start_time=time(18), end_time=time(18, 20)
            )
        AvailabilityBlock.objects.create(
            student=student, weekday=0, start_time=time(22), end_time=time(0)
        )
