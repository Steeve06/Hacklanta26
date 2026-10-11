import io
from datetime import time, timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from lms.models import Assessment, Chapter, Enrollment
from lms.registration import Meeting, Registration, pending_teacher, register_course
from quizzes.models import CheckQuestion

from .factories import StudentFactory, TermFactory, UserFactory
from .test_auth import GOOD_PASSWORD, signup

pytestmark = pytest.mark.django_db

CHAPTER_BODY = (
    "A **stack** keeps the most recent item on top, so the last item in is the first out. "
    "A **queue** serves items in the order they arrived, first in and first out for everyone. "
    "A **hash table** maps keys to buckets so most lookups take constant time on average. "
    "A **heap** keeps the smallest item at the root, which makes priority queues efficient. "
    "A **graph** links nodes with edges and can model roads, friendships or the web itself. "
    "A **binary search tree** keeps smaller keys left and larger keys right of each node."
)


@pytest.fixture
def term():
    return TermFactory()


@pytest.fixture
def course(term):
    return register_course(
        Registration(
            code="CS 201",
            title="Data Structures",
            teacher_email="Prof.Okafor@school.edu",
            teacher_first_name="Ada",
            description="How to organize data.",
            meetings=[Meeting(0, time(10), time(11, 15), "Hall 120")],
        )
    )


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def teacher_signup(api, **overrides):
    body = {"role": "teacher", "email": "prof.okafor@school.edu", "first_name": "Ada"}
    return signup(api, **{**body, **overrides})


class TestRegistration:
    def test_course_waits_for_its_teacher(self, course):
        teacher = course.instructor
        assert teacher.email == "prof.okafor@school.edu"
        assert teacher.role == "instructor"
        assert not teacher.has_usable_password()
        assert pending_teacher("PROF.OKAFOR@school.edu") == teacher
        assert course.syllabus.description == "How to organize data."
        assert course.meetings.count() == 1
        assert (course.chapters.count(), course.assessments.count()) == (0, 0)

    def test_existing_students_join_the_new_course(self, term):
        student = StudentFactory()
        course = register_course(Registration("PSY 101", "Psych", "marsh@school.edu"))
        assert Enrollment.objects.filter(user=student, course=course, role="student").exists()

    def test_cannot_register_a_student_email_as_teacher(self, term):
        student = StudentFactory()
        with pytest.raises(ValueError):
            register_course(Registration("X 1", "X", student.email))

    def test_command(self, term):
        out = io.StringIO()
        call_command(
            "register_course", "BUS 210", "Marketing", "reyes@school.edu",
            "--teacher-name", "Luis Reyes", "--meeting", "tue 09:00-10:15 Room 4", stdout=out,
        )  # fmt: skip
        teacher = pending_teacher("reyes@school.edu")
        assert (teacher.first_name, teacher.last_name) == ("Luis", "Reyes")
        assert teacher.teaching.get().meetings.get().weekday == 1
        assert "can now sign up" in out.getvalue()


class TestTeacherSignup:
    def test_teacher_claims_their_course(self, api, course):
        response = teacher_signup(api)
        assert response.status_code == 201, response.data
        teacher = User.objects.get(email="prof.okafor@school.edu")
        assert teacher.check_password(GOOD_PASSWORD)
        assert teacher.timezone == "America/Chicago"
        assert pending_teacher(teacher.email) is None
        me = APIClient()
        me.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        courses = me.get("/api/v1/courses").data
        assert [c["code"] for c in courses] == ["CS 201"]
        assert courses[0]["instructor_name"] == "Ada Okoro"

    def test_teacher_signup_needs_a_registered_course(self, api, course):
        response = teacher_signup(api, email="someone@school.edu")
        assert response.status_code == 400
        assert "No course is registered" in response.data["email"][0]

    def test_cannot_claim_twice(self, api, course):
        assert teacher_signup(api).status_code == 201
        response = teacher_signup(APIClient())
        assert response.status_code == 400
        assert "already exists" in response.data["email"][0]

    def test_student_signup_with_a_teacher_email_points_to_teacher_signup(self, api, course):
        response = signup(api, email="prof.okafor@school.edu")
        assert response.status_code == 400
        assert "Sign up as a teacher" in response.data["email"][0]

    def test_unclaimed_login_explains_what_to_do(self, api, course):
        response = api.post(
            "/api/v1/auth/login",
            {"email": "prof.okafor@school.edu", "password": "whatever-it-is"},
            format="json",
        )
        assert response.status_code == 400
        assert "Sign up as a teacher" in response.data["detail"]

    def test_students_still_sign_up_and_join_registered_courses(self, api, course):
        assert signup(api).status_code == 201
        student = User.objects.get(email="nia@example.edu")
        assert student.role == "student"
        assert Enrollment.objects.filter(user=student, course=course).exists()


class TestTeacherContentReachesStudents:
    def test_teacher_adds_chapter_and_assignments_students_see_them(self, course):
        teacher = course.instructor
        student = StudentFactory()
        Enrollment.objects.create(user=student, course=course)
        api = client_for(teacher)
        now = timezone.now()

        chapter = api.post(
            f"/api/v1/courses/{course.id}/chapters",
            {
                "order": 1, "title": "Stacks and queues", "body_md": CHAPTER_BODY,
                "objectives": ["Pick a structure"], "reading_minutes": 15,
                "available_from": (now - timedelta(hours=1)).isoformat(),
            },
            format="json",
        )  # fmt: skip
        assert chapter.status_code == 201, chapter.data
        due = (now + timedelta(days=3)).isoformat()
        opens = (now - timedelta(hours=1)).isoformat()
        base = {"instructions": "Read and answer.", "open_at": opens, "due_at": due}
        for body in [
            {"type": "homework", "title": "Problem set 1"},
            {
                "type": "discussion",
                "title": "When to use a queue",
                "discussion_replies_required": 2,
            },
            {
                "type": "quiz",
                "title": "Quiz 1",
                "chapter_ids": [chapter.data["id"]],
                "questions": [
                    {
                        "order": 1,
                        "type": "true_false",
                        "prompt": "A stack is LIFO.",
                        "options": ["True", "False"],
                        "correct_index": 0,
                    },
                ],
            },  # fmt: skip
        ]:
            response = api.post(
                f"/api/v1/courses/{course.id}/assessments", {**base, **body}, format="json"
            )
            assert response.status_code == 201, response.data

        empty_quiz = api.post(
            f"/api/v1/courses/{course.id}/assessments",
            {**base, "type": "quiz", "title": "Empty"},
            format="json",
        )
        assert empty_quiz.status_code == 400
        assert "questions" in empty_quiz.data

        student_api = client_for(student)
        titles = {
            a["title"] for a in student_api.get(f"/api/v1/courses/{course.id}/assessments").data
        }
        assert titles == {"Problem set 1", "When to use a queue", "Quiz 1"}
        chapters = student_api.get(f"/api/v1/courses/{course.id}/chapters").data
        assert [c["title"] for c in chapters] == ["Stacks and queues"]
        quiz = Assessment.objects.get(title="Quiz 1")
        attempt = student_api.post(f"/api/v1/assessments/{quiz.id}/attempts")
        assert attempt.status_code == 201
        assert len(attempt.data["questions"]) == 1

    def test_new_chapter_builds_the_daily_deck_bank(
        self, course, django_capture_on_commit_callbacks
    ):
        Enrollment.objects.create(user=StudentFactory(), course=course)
        with django_capture_on_commit_callbacks(execute=True):
            response = client_for(course.instructor).post(
                f"/api/v1/courses/{course.id}/chapters",
                {
                    "order": 1, "title": "Structures", "body_md": CHAPTER_BODY,
                    "objectives": ["Name the structures"], "reading_minutes": 10,
                    "available_from": timezone.now().isoformat(),
                },
                format="json",
            )  # fmt: skip
        assert response.status_code == 201, response.data
        chapter = Chapter.objects.get()
        assert CheckQuestion.objects.filter(chapter=chapter).exists()


class TestOverview:
    def test_overview_counts(self, course):
        teacher = course.instructor
        StudentFactory.create_batch(2)
        Enrollment.objects.bulk_create(
            Enrollment(user=s, course=course) for s in User.objects.filter(role="student")
        )
        from .factories import AssessmentFactory

        AssessmentFactory(course=course, type="homework")
        AssessmentFactory(course=course, type="discussion", published=False)
        rows = client_for(teacher).get("/api/v1/teach/overview").data
        assert len(rows) == 1
        row = rows[0]
        assert (row["students"], row["homework"], row["discussions"], row["quizzes"]) == (
            2, 1, 1, 0,
        )  # fmt: skip
        assert row["hidden"] == 1
        assert row["next_due"]["type"] == "homework"

    def test_students_have_no_overview(self, course):
        assert client_for(StudentFactory()).get("/api/v1/teach/overview").status_code == 403

    def test_teacher_edits_syllabus(self, course):
        api = client_for(course.instructor)
        response = api.patch(
            f"/api/v1/courses/{course.id}/syllabus/edit",
            {
                "office_hours": "Tue 2-4pm",
                "grading": [
                    {"label": "Homework", "weight_pct": 60},
                    {"label": "Quizzes", "weight_pct": 40},
                ],
            },
            format="json",
        )
        assert response.status_code == 200, response.data
        assert response.data["office_hours"] == "Tue 2-4pm"
        bad = api.patch(
            f"/api/v1/courses/{course.id}/syllabus/edit",
            {"grading": [{"label": "All", "weight_pct": 90}]},
            format="json",
        )
        assert bad.status_code == 400
        other = client_for(StudentFactory())
        assert (
            other.patch(f"/api/v1/courses/{course.id}/syllabus/edit", {}, format="json").status_code
            == 404
        )


class TestAdminRegistration:
    def test_admin_registers_a_course_from_the_app(self, term):
        admin = UserFactory(role="admin", is_staff=True, is_superuser=True)
        api = client_for(admin)
        body = {
            "code": "ENG 105", "title": "Writing", "teacher_email": "kim@school.edu",
            "meetings": [{"weekday": 2, "start_time": "13:00", "end_time": "14:00"}],
        }  # fmt: skip
        response = api.post("/api/v1/teach/registrations", body, format="json")
        assert response.status_code == 201, response.data
        assert response.data["claimed"] is False
        assert pending_teacher("kim@school.edu") is not None
        dup = api.post("/api/v1/teach/registrations", body, format="json")
        assert dup.status_code == 400 and "code" in dup.data
        listed = api.get("/api/v1/teach/registrations").data
        assert [c["code"] for c in listed] == ["ENG 105"]

    def test_only_admins_register(self, course):
        response = client_for(course.instructor).post(
            "/api/v1/teach/registrations",
            {"code": "X", "title": "X", "teacher_email": "x@school.edu"},
            format="json",
        )
        assert response.status_code == 403


def without_quiet_hours(student):
    """Announcements wait out quiet hours (22:00 to 08:00 by default), so tests that expect an
    immediate send would fail in the evening without this."""
    from accounts.models import StudentProfile

    StudentProfile.objects.update_or_create(
        user=student, defaults={"quiet_start": time(0), "quiet_end": time(0)}
    )


class TestNewContentNotifications:
    def _post_homework(self, course, **extra):
        now = timezone.now()
        body = {
            "type": "homework", "title": "Problem set 1", "instructions": "Answer.",
            "open_at": (now - timedelta(hours=1)).isoformat(),
            "due_at": (now + timedelta(days=3)).isoformat(), **extra,
        }  # fmt: skip
        return client_for(course.instructor).post(
            f"/api/v1/courses/{course.id}/assessments", body, format="json"
        )

    def test_students_are_told_about_new_work_by_push(
        self, course, settings, django_capture_on_commit_callbacks
    ):
        import json
        from unittest import mock

        from notifications.models import Notification, PushSubscription

        settings.VAPID_PUBLIC_KEY, settings.VAPID_PRIVATE_KEY = "pub", "priv"
        student = StudentFactory()
        without_quiet_hours(student)
        Enrollment.objects.create(user=student, course=course)
        StudentFactory()  # not in the course
        PushSubscription.objects.create(
            user=student, endpoint="https://push.example/abc", keys={"p256dh": "x", "auth": "y"}
        )
        with (
            mock.patch("pywebpush.webpush") as send,
            django_capture_on_commit_callbacks(execute=True),
        ):
            assert self._post_homework(course).status_code == 201
        n = Notification.objects.get()
        assert n.student == student
        assert n.text == "New assignment in CS 201: Problem set 1"
        assert n.sent_at is not None and n.channels == ["inapp", "push"]
        payload = json.loads(send.call_args.kwargs["data"])
        assert payload["title"] == "Leon · New in your course"
        assert payload["url"] == f"/lms/courses/{course.id}/assignments/{n.source_id}"
        inbox = client_for(student).get("/api/v1/notifications").data
        assert inbox["unread"] == 1

    def test_hidden_work_is_announced_when_published(
        self, course, django_capture_on_commit_callbacks
    ):
        from notifications.models import Notification

        student = StudentFactory()
        without_quiet_hours(student)
        Enrollment.objects.create(user=student, course=course)
        with django_capture_on_commit_callbacks(execute=True):
            created = self._post_homework(course, published=False)
        assert not Notification.objects.exists()
        with django_capture_on_commit_callbacks(execute=True):
            client_for(course.instructor).patch(
                f"/api/v1/assessments/{created.data['id']}", {"published": True}, format="json"
            )
        assert Notification.objects.filter(student=student, sent_at__isnull=False).count() == 1

    def test_future_chapter_is_announced_when_it_unlocks(
        self, course, django_capture_on_commit_callbacks
    ):
        from notifications.engine import dispatch_due
        from notifications.models import Notification

        student = StudentFactory()
        Enrollment.objects.create(user=student, course=course)
        unlock = timezone.now() + timedelta(days=2)
        with django_capture_on_commit_callbacks(execute=True):
            client_for(course.instructor).post(
                f"/api/v1/courses/{course.id}/chapters",
                {
                    "order": 1, "title": "Heaps", "body_md": CHAPTER_BODY,
                    "objectives": ["Use a heap"], "reading_minutes": 10,
                    "available_from": unlock.isoformat(),
                },
                format="json",
            )  # fmt: skip
        n = Notification.objects.get()
        assert n.sent_at is None and n.scheduled_for >= unlock
        dispatch_due(now=unlock + timedelta(hours=12))
        n.refresh_from_db()
        assert n.sent_at is not None
