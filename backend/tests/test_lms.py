import io
from datetime import timedelta

import pytest
import time_machine
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from lms.models import DiscussionPost, QuizQuestion, Submission

from .factories import (
    AssessmentFactory,
    ChapterFactory,
    CourseFactory,
    StudentFactory,
    enroll,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def course(student):
    course = CourseFactory()
    enroll(student, course)
    return course


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def pdf(name="answer.pdf", size=100):
    return SimpleUploadedFile(name, b"%PDF" + b"0" * size, content_type="application/pdf")


class TestPermissions:
    def test_student_only_sees_enrolled_courses(self, student_api, course):
        other = CourseFactory()
        ids = [c["id"] for c in student_api.get("/api/v1/courses").data]
        assert ids == [course.id]
        assert student_api.get(f"/api/v1/courses/{other.id}").status_code == 404
        assert student_api.get(f"/api/v1/courses/{other.id}/chapters").status_code == 404

    def test_student_cannot_see_other_course_assessment_or_chapter(self, student_api, course):
        other = CourseFactory()
        assessment = AssessmentFactory(course=other)
        chapter = ChapterFactory(course=other)
        assert student_api.get(f"/api/v1/assessments/{assessment.id}").status_code == 404
        assert student_api.get(f"/api/v1/chapters/{chapter.id}").status_code == 404

    def test_instructor_only_sees_own_courses(self, course):
        mine = CourseFactory()
        client = client_for(mine.instructor)
        ids = [c["id"] for c in client.get("/api/v1/courses").data]
        assert ids == [mine.id]

    def test_student_cannot_use_instructor_endpoints(self, student_api, course, student):
        assessment = AssessmentFactory(course=course)
        assert student_api.get(f"/api/v1/assessments/{assessment.id}/roster").status_code == 403
        response = student_api.post(
            f"/api/v1/assessments/{assessment.id}/overrides",
            {"student": student.id, "due_at": timezone.now().isoformat()},
            format="json",
        )
        assert response.status_code == 403

    def test_other_instructor_cannot_edit(self, course):
        assessment = AssessmentFactory(course=course)
        stranger = CourseFactory().instructor
        response = client_for(stranger).patch(
            f"/api/v1/assessments/{assessment.id}", {"title": "x"}, format="json"
        )
        assert response.status_code == 404

    def test_unpublished_hidden_from_students(self, student_api, course):
        hidden = AssessmentFactory(course=course, published=False)
        assert student_api.get(f"/api/v1/assessments/{hidden.id}").status_code == 404
        listed = student_api.get(f"/api/v1/courses/{course.id}/assessments").data
        assert hidden.id not in [a["id"] for a in listed]

    def test_submission_file_only_for_owner_and_teacher(self, student_api, student, course):
        assessment = AssessmentFactory(course=course)
        created = student_api.post(
            f"/api/v1/assessments/{assessment.id}/submissions", {"file": pdf()}, format="multipart"
        )
        sub_id = created.data["id"]
        assert student_api.get(f"/api/v1/submissions/{sub_id}/file").status_code == 200
        assert (
            client_for(course.instructor).get(f"/api/v1/submissions/{sub_id}/file").status_code
            == 200
        )
        intruder = StudentFactory()
        enroll(intruder, course)
        assert client_for(intruder).get(f"/api/v1/submissions/{sub_id}/file").status_code == 404


class TestChapters:
    def test_open_and_complete(self, student_api, student, course):
        chapter = ChapterFactory(course=course)
        detail = student_api.get(f"/api/v1/chapters/{chapter.id}")
        assert detail.status_code == 200
        assert detail.data["opened_at"] is not None
        assert "<p>" in detail.data["body_html"]
        done = student_api.post(f"/api/v1/chapters/{chapter.id}/complete")
        assert done.data["completed_at"] is not None

    def test_locked_chapter_hides_body_and_cannot_complete(self, student_api, course):
        chapter = ChapterFactory(course=course, available_from=timezone.now() + timedelta(days=3))
        detail = student_api.get(f"/api/v1/chapters/{chapter.id}")
        assert detail.data["locked"] is True
        assert detail.data["body_html"] == ""
        assert student_api.post(f"/api/v1/chapters/{chapter.id}/complete").status_code == 400

    def test_markdown_is_sanitized(self, student_api, course):
        chapter = ChapterFactory(
            course=course, body_md="Hi <script>alert(1)</script> [x](javascript:alert(1))"
        )
        html = student_api.get(f"/api/v1/chapters/{chapter.id}").data["body_html"]
        assert "<script>" not in html
        assert "javascript:" not in html


class TestHomework:
    def test_on_time_submission_and_resubmission(self, student_api, course):
        assessment = AssessmentFactory(course=course)
        url = f"/api/v1/assessments/{assessment.id}/submissions"
        assert student_api.post(url, {"text": "first"}, format="json").data["status"] == "submitted"
        second = student_api.post(url, {"text": "second"}, format="json")
        assert second.data["attempt_no"] == 2

    def test_late_before_cutoff_and_rejected_after(self, student_api, course):
        now = timezone.now()
        late = AssessmentFactory(
            course=course, due_at=now - timedelta(hours=2), cutoff_at=now + timedelta(days=1)
        )
        closed = AssessmentFactory(
            course=course, due_at=now - timedelta(days=3), cutoff_at=now - timedelta(days=1)
        )
        ok = student_api.post(
            f"/api/v1/assessments/{late.id}/submissions", {"text": "x"}, format="json"
        )
        assert ok.data["status"] == "late"
        rejected = student_api.post(
            f"/api/v1/assessments/{closed.id}/submissions", {"text": "x"}, format="json"
        )
        assert rejected.status_code == 400
        assert "late window" in str(rejected.data)

    def test_no_resubmission_after_due(self, student_api, course):
        now = timezone.now()
        assessment = AssessmentFactory(
            course=course, due_at=now - timedelta(hours=1), cutoff_at=now + timedelta(days=1)
        )
        url = f"/api/v1/assessments/{assessment.id}/submissions"
        student_api.post(url, {"text": "late"}, format="json")
        assert student_api.post(url, {"text": "again"}, format="json").status_code == 400

    @pytest.mark.parametrize(
        ("upload", "message"),
        [
            (
                SimpleUploadedFile("a.exe", b"MZ..", content_type="application/x-msdownload"),
                "PDF, DOCX or ZIP",
            ),
            (SimpleUploadedFile("a.pdf", b"not a pdf", content_type="application/pdf"), "damaged"),
            (SimpleUploadedFile("a.pdf", b"%PDF", content_type="text/html"), "doesn't match"),
        ],
    )
    def test_upload_validation(self, student_api, course, upload, message):
        assessment = AssessmentFactory(course=course)
        response = student_api.post(
            f"/api/v1/assessments/{assessment.id}/submissions", {"file": upload}, format="multipart"
        )
        assert response.status_code == 400
        assert message in str(response.data)

    def test_upload_too_large(self, student_api, course):
        assessment = AssessmentFactory(course=course)
        big = pdf(size=10 * 1024 * 1024 + 1)
        response = student_api.post(
            f"/api/v1/assessments/{assessment.id}/submissions", {"file": big}, format="multipart"
        )
        assert response.status_code == 400
        assert "10 MB" in str(response.data)

    def test_override_extends_deadline(self, student_api, student, course):
        now = timezone.now()
        assessment = AssessmentFactory(
            course=course, due_at=now - timedelta(days=3), cutoff_at=now - timedelta(days=2)
        )
        client_for(course.instructor).post(
            f"/api/v1/assessments/{assessment.id}/overrides",
            {"student": student.id, "due_at": (now + timedelta(days=2)).isoformat()},
            format="json",
        )
        detail = student_api.get(f"/api/v1/assessments/{assessment.id}").data
        assert detail["extended"] is True
        assert detail["status"] == "not_started"
        ok = student_api.post(
            f"/api/v1/assessments/{assessment.id}/submissions", {"text": "x"}, format="json"
        )
        assert ok.data["status"] == "submitted"


class TestDiscussion:
    def test_requirement_needs_original_and_replies(self, student_api, student, course):
        assessment = AssessmentFactory(
            course=course, type="discussion", discussion_replies_required=1
        )
        peer = StudentFactory()
        enroll(peer, course)
        peer_post = DiscussionPost.objects.create(assessment=assessment, author=peer, body="hi")
        url = f"/api/v1/assessments/{assessment.id}/posts"
        student_api.post(url, {"body": "reply first", "parent": peer_post.id}, format="json")
        assert (
            student_api.get(f"/api/v1/assessments/{assessment.id}").data["status"] == "in_progress"
        )
        student_api.post(url, {"body": "my original"}, format="json")
        assert student_api.get(f"/api/v1/assessments/{assessment.id}").data["status"] == "submitted"
        progress = student_api.get(url).data["progress"]
        assert progress == {"original_posted": True, "replies_made": 1, "replies_required": 1}


class TestInstructorQuiz:
    @pytest.fixture
    def quiz(self, course):
        assessment = AssessmentFactory(course=course, type="quiz", cutoff_at=None, points=10)
        for i in range(2):
            QuizQuestion.objects.create(
                assessment=assessment, order=i, type="true_false", prompt=f"Q{i}",
                options=["True", "False"], correct_index=0,
            )  # fmt: skip
        return assessment

    def test_answers_not_leaked_before_submit(self, student_api, quiz):
        attempt = student_api.post(f"/api/v1/assessments/{quiz.id}/attempts").data
        assert attempt["results"] is None
        assert all("correct_index" not in q for q in attempt["questions"])

    def test_submit_grades_and_is_idempotent(self, student_api, quiz):
        attempt = student_api.post(f"/api/v1/assessments/{quiz.id}/attempts").data
        q = attempt["questions"]
        answers = {str(q[0]["id"]): 0, str(q[1]["id"]): 1}
        first = student_api.post(
            f"/api/v1/attempts/{attempt['id']}/submit", {"answers": answers}, format="json"
        )
        assert float(first.data["score"]) == 5.0
        again = student_api.post(
            f"/api/v1/attempts/{attempt['id']}/submit",
            {"answers": {str(q[1]["id"]): 0}},
            format="json",
        )
        assert again.data["score"] == first.data["score"]
        assert Submission.objects.filter(assessment=quiz).count() == 1

    def test_time_limit_auto_submits_answered_questions(self, student_api, quiz):
        attempt = student_api.post(f"/api/v1/assessments/{quiz.id}/attempts").data
        qid = str(attempt["questions"][0]["id"])
        student_api.patch(f"/api/v1/attempts/{attempt['id']}", {"answers": {qid: 0}}, format="json")
        with time_machine.travel(timezone.now() + timedelta(minutes=quiz.time_limit_minutes + 1)):
            result = student_api.get(f"/api/v1/attempts/{attempt['id']}").data
        assert result["auto_submitted"] is True
        assert float(result["score"]) == 5.0

    def test_attempt_limit(self, student_api, quiz):
        for _ in range(quiz.max_attempts):
            attempt = student_api.post(f"/api/v1/assessments/{quiz.id}/attempts").data
            student_api.post(
                f"/api/v1/attempts/{attempt['id']}/submit", {"answers": {}}, format="json"
            )
        assert student_api.post(f"/api/v1/assessments/{quiz.id}/attempts").status_code == 400


class TestInstructor:
    def test_roster_and_manual_score(self, student, course):
        assessment = AssessmentFactory(course=course)
        client_for(student).post(
            f"/api/v1/assessments/{assessment.id}/submissions", {"text": "x"}, format="json"
        )
        teacher = client_for(course.instructor)
        roster = teacher.get(f"/api/v1/assessments/{assessment.id}/roster").data
        assert roster[0]["status"] == "submitted"
        scored = teacher.patch(
            f"/api/v1/submissions/{roster[0]['submission_id']}/score",
            {"score": "8.5"},
            format="json",
        )
        assert scored.status_code == 200
        too_high = teacher.patch(
            f"/api/v1/submissions/{roster[0]['submission_id']}/score",
            {"score": "99"},
            format="json",
        )
        assert too_high.status_code == 400

    def test_create_assessment_validates_dates(self, course):
        teacher = client_for(course.instructor)
        now = timezone.now()
        bad = teacher.post(
            f"/api/v1/courses/{course.id}/assessments",
            {
                "type": "homework", "title": "HW", "instructions": "x",
                "open_at": now.isoformat(), "due_at": (now - timedelta(days=1)).isoformat(),
            },
            format="json",
        )  # fmt: skip
        assert bad.status_code == 400
        assert "due_at" in bad.data


class TestQueryCounts:
    def test_course_list_is_constant(self, student_api, student, django_assert_max_num_queries):
        for _ in range(3):
            course = CourseFactory()
            enroll(student, course)
            ChapterFactory.create_batch(4, course=course)
            AssessmentFactory.create_batch(4, course=course)
        with django_assert_max_num_queries(8):
            student_api.get("/api/v1/courses")

    def test_assessment_list_is_constant(self, student_api, course, django_assert_max_num_queries):
        AssessmentFactory.create_batch(12, course=course)
        with django_assert_max_num_queries(10):
            student_api.get(f"/api/v1/courses/{course.id}/assessments")


def test_seed_demo_is_idempotent():
    from django.core.management import call_command

    from lms.models import Assessment, Chapter, Course

    call_command("seed_demo", stdout=io.StringIO())
    counts = (Course.objects.count(), Chapter.objects.count(), Assessment.objects.count())
    call_command("seed_demo", stdout=io.StringIO())
    assert (Course.objects.count(), Chapter.objects.count(), Assessment.objects.count()) == counts
    assert counts == (3, 24, 30)
    assert all(len(c.body_md.split()) >= 600 for c in Chapter.objects.all())


@pytest.mark.parametrize("hour", [1, 9, 15, 23])
def test_seed_gives_on_track_student_an_open_quiz_at_any_time_of_day(
    hour, django_capture_on_commit_callbacks
):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from django.core.management import call_command

    from quizzes.models import ChapterQuiz

    moment = datetime(2026, 10, 10, hour, 0, tzinfo=ZoneInfo("America/New_York"))
    with time_machine.travel(moment, tick=False):
        with django_capture_on_commit_callbacks(execute=True):
            call_command("seed_demo", stdout=io.StringIO())
        open_quizzes = ChapterQuiz.objects.filter(
            student__email="maya@pulse.test", opens_at__lte=moment, closes_at__gt=moment
        )
        assert open_quizzes.count() == 1
