from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
import time_machine
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import StudentProfile
from pulse.models import AvailabilityBlock, PlanJob, Schedule
from pulse.services.planner import plan

from .factories import AssessmentFactory, ChapterFactory, CourseFactory, StudentFactory, enroll

pytestmark = pytest.mark.django_db
NY = ZoneInfo("America/New_York")


def make_student(blocks=None, **profile):
    student = StudentFactory()
    StudentProfile.objects.filter(user=student).update(onboarding_done=True, **profile)
    for weekday, start, end in (
        blocks if blocks is not None else [(d, time(9), time(21)) for d in range(7)]
    ):
        AvailabilityBlock.objects.create(
            student=student, weekday=weekday, start_time=start, end_time=end
        )
    student.refresh_from_db()
    return student


@pytest.fixture
def setup():
    student = make_student()
    course = CourseFactory()
    enroll(student, course)
    chapter = ChapterFactory(course=course)
    homework = AssessmentFactory(
        course=course, est_minutes=90, due_at=timezone.now() + timedelta(days=4)
    )
    homework.chapters.set([chapter])
    return student, course, chapter, homework


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def future_sessions(schedule, kind=None):
    qs = schedule.sessions.filter(start__gte=timezone.now(), status="planned").select_related(
        "task"
    )
    return [s for s in qs if kind is None or s.kind == kind]


class TestGeneration:
    def test_zero_availability_blocks_generation(self):
        student = make_student(blocks=[])
        response = client_for(student).post("/api/v1/pulse/schedules/generate", {}, format="json")
        assert response.status_code == 400
        assert response.data["code"] == "no_availability"

    def test_generate_job_runs_and_schedule_is_readable(
        self, setup, django_capture_on_commit_callbacks
    ):
        student, *_ = setup
        client = client_for(student)
        with django_capture_on_commit_callbacks(execute=True):
            job = client.post("/api/v1/pulse/schedules/generate", {}, format="json").data
        assert client.get(f"/api/v1/pulse/jobs/{job['id']}").data["state"] == "done"
        week = client.get("/api/v1/pulse/schedule?view=week").data
        overall = client.get("/api/v1/pulse/schedule?view=overall").data
        assert overall["sessions"]
        assert {"sessions", "deadlines", "summary", "overload_report"} <= set(week)

    def test_one_open_job_per_student(self, setup):
        student, *_ = setup
        client = client_for(student)
        first = client.post("/api/v1/pulse/schedules/generate", {}, format="json").data
        second = client.post("/api/v1/pulse/schedules/generate", {}, format="json").data
        assert first["id"] == second["id"]
        assert PlanJob.objects.filter(student=student).count() == 1

    def test_dependencies_chapter_before_homework(self, setup):
        student, _, chapter, homework = setup
        schedule = plan(student, reason="test")
        read = [
            s
            for s in schedule.sessions.all()
            if s.task.source_type == "chapter" and s.kind == "study"
        ]
        work = [s for s in schedule.sessions.all() if s.task.source_type == "assessment"]
        assert max(s.end for s in read) <= min(s.start for s in work)

    def test_available_less_than_work_gives_overload_report(self):
        student = make_student(blocks=[(0, time(19), time(19, 30))])
        course = CourseFactory()
        enroll(student, course)
        AssessmentFactory(course=course, est_minutes=300, due_at=timezone.now() + timedelta(days=2))
        schedule = plan(student, reason="test")
        report = schedule.overload_report
        assert report["items"][0]["minutes_short"] > 0
        assert report["extra_hours_needed"] > 0
        assert any(s["type"] == "request_extension" for s in report["suggestions"])

    def test_overdue_with_open_late_window_goes_first(self):
        student = make_student()
        course = CourseFactory()
        enroll(student, course)
        now = timezone.now()
        late = AssessmentFactory(course=course, est_minutes=30, weight_pct=5,
                                 due_at=now - timedelta(hours=3), cutoff_at=now + timedelta(days=2))  # fmt: skip
        AssessmentFactory(
            course=course, est_minutes=30, weight_pct=30, due_at=now + timedelta(days=3)
        )
        schedule = plan(student, reason="test")
        first = schedule.sessions.order_by("start").first()
        assert first.task.source_id == late.id

    def test_overdue_with_closed_window_is_excluded_and_noted(self):
        student = make_student()
        course = CourseFactory()
        enroll(student, course)
        now = timezone.now()
        gone = AssessmentFactory(course=course, title="Lost cause",
                                 due_at=now - timedelta(days=3), cutoff_at=now - timedelta(days=1))  # fmt: skip
        schedule = plan(student, reason="test")
        assert not schedule.sessions.filter(task__source_id=gone.id).exists()
        assert "Lost cause" in schedule.summary

    def test_due_inside_buffer_is_flagged_at_risk(self):
        student = make_student(
            blocks=[(d, time(0), time(23, 59)) for d in range(7)],
            earliest_time=time(0),
            latest_time=time(23, 59),
        )
        course = CourseFactory()
        enroll(student, course)
        soon = AssessmentFactory(
            course=course, est_minutes=30, due_at=timezone.now() + timedelta(hours=6)
        )
        schedule = plan(student, reason="test")
        sessions = schedule.sessions.filter(task__source_id=soon.id)
        assert sessions.exists()
        assert all(s.at_risk for s in sessions)

    def test_locked_chapter_not_before_unlock(self):
        student = make_student()
        course = CourseFactory()
        enroll(student, course)
        unlock = timezone.now() + timedelta(days=5)
        chapter = ChapterFactory(course=course, available_from=unlock)
        schedule = plan(student, reason="test")
        chapter_sessions = schedule.sessions.filter(
            task__source_type="chapter", task__source_id=chapter.id
        )
        assert all(s.start >= unlock for s in chapter_sessions)

    def test_nothing_after_term_end(self, setup):
        student, course, *_ = setup
        course.term.end_date = (timezone.now() + timedelta(days=6)).date()
        course.term.save()
        ChapterFactory(course=course, available_from=timezone.now() + timedelta(days=10))
        schedule = plan(student, reason="test")
        assert all(s.end <= schedule.horizon_end for s in schedule.sessions.all())


class TestReplanning:
    def test_extension_moves_future_sessions_and_keeps_past(
        self, setup, django_capture_on_commit_callbacks
    ):
        student, course, _, homework = setup
        first = plan(student, reason="test")
        past = first.sessions.order_by("start").first()
        past.status, past.completed_minutes = "done", past.minutes
        past.save()
        with time_machine.travel(past.end + timedelta(minutes=1)):
            with django_capture_on_commit_callbacks(execute=True):
                client_for(course.instructor).post(
                    f"/api/v1/assessments/{homework.id}/overrides",
                    {
                        "student": student.id,
                        "due_at": (homework.due_at + timedelta(days=7)).isoformat(),
                    },
                    format="json",
                )
            active = Schedule.objects.get(student=student, is_active=True)
            assert active.version == first.version + 1
            kept = active.sessions.get(start=past.start)
            assert kept.status == "done"

    def test_skipped_minutes_are_redistributed(self, setup, django_capture_on_commit_callbacks):
        student, *_ = setup
        schedule = plan(student, reason="test")
        target = schedule.sessions.filter(kind="assignment").order_by("start").first()
        total_before = sum(
            s.minutes for s in schedule.sessions.filter(task=target.task, status="planned")
        )
        with time_machine.travel(target.end + timedelta(minutes=1)):
            with django_capture_on_commit_callbacks(execute=True):
                response = client_for(student).patch(
                    f"/api/v1/pulse/sessions/{target.id}", {"status": "skipped"}, format="json"
                )
            assert response.status_code == 200
            active = Schedule.objects.get(student=student, is_active=True)
            planned = sum(
                s.minutes for s in active.sessions.filter(task=target.task, status="planned")
            )
        assert planned == total_before

    def test_partial_and_done_early(self, setup, django_capture_on_commit_callbacks):
        student, *_ = setup
        schedule = plan(student, reason="test")
        work = list(schedule.sessions.filter(kind="assignment").order_by("start"))
        total = sum(s.minutes for s in work)
        client = client_for(student)
        with django_capture_on_commit_callbacks(execute=True):
            client.patch(f"/api/v1/pulse/sessions/{work[0].id}",
                         {"status": "partial", "completed_minutes": 10}, format="json")  # fmt: skip
        active = Schedule.objects.get(student=student, is_active=True)
        remaining = sum(
            s.minutes for s in active.sessions.filter(kind="assignment", status="planned")
        )
        assert remaining == total - 10
        bad = client.patch(f"/api/v1/pulse/sessions/{work[1].id}",
                           {"status": "partial", "completed_minutes": 999}, format="json")  # fmt: skip
        assert bad.status_code in (400, 404)

    def test_submission_frees_sessions(self, setup, django_capture_on_commit_callbacks):
        student, _, _, homework = setup
        plan(student, reason="test")
        with django_capture_on_commit_callbacks(execute=True):
            client_for(student).post(
                f"/api/v1/assessments/{homework.id}/submissions", {"text": "done"}, format="json"
            )
        active = Schedule.objects.get(student=student, is_active=True)
        assert not active.sessions.filter(
            task__source_type="assessment", task__source_id=homework.id, status="planned"
        ).exists()

    def test_reschedule_avoids_the_old_slot(self, setup, django_capture_on_commit_callbacks):
        student, *_ = setup
        schedule = plan(student, reason="test")
        target = future_sessions(schedule, "assignment")[0]
        with django_capture_on_commit_callbacks(execute=True):
            response = client_for(student).post(f"/api/v1/pulse/sessions/{target.id}/reschedule")
        assert response.data["status"] == "rescheduled"
        active = Schedule.objects.get(student=student, is_active=True)
        assert not active.sessions.filter(status="planned", start=target.start).exists()

    def test_deleted_assessment_removes_future_sessions(
        self, setup, django_capture_on_commit_callbacks
    ):
        student, course, _, homework = setup
        plan(student, reason="test")
        with django_capture_on_commit_callbacks(execute=True):
            client_for(course.instructor).delete(f"/api/v1/assessments/{homework.id}")
        active = Schedule.objects.get(student=student, is_active=True)
        assert not active.sessions.filter(
            task__source_type="assessment", task__source_id=homework.id, status="planned"
        ).exists()

    def test_students_cannot_touch_other_sessions(self, setup):
        student, *_ = setup
        schedule = plan(student, reason="test")
        other = make_student()
        response = client_for(other).patch(
            f"/api/v1/pulse/sessions/{schedule.sessions.first().id}",
            {"status": "done"},
            format="json",
        )
        assert response.status_code == 404


class TestTimezones:
    def test_timezone_change_keeps_wall_clock_availability(self):
        student = make_student(blocks=[(d, time(18), time(20)) for d in range(7)])
        course = CourseFactory()
        enroll(student, course)
        homework = AssessmentFactory(
            course=course, est_minutes=60, due_at=timezone.now() + timedelta(days=5)
        )
        student.timezone = "Europe/Berlin"
        student.save()
        schedule = plan(student, reason="test")
        berlin = ZoneInfo("Europe/Berlin")
        assert {s.start.astimezone(berlin).hour for s in schedule.sessions.all()} <= {18, 19}
        homework.refresh_from_db()
        assert all(s.end <= homework.due_at for s in schedule.sessions.all())

    def test_due_today_vs_tomorrow_in_student_zone(self):
        student = make_student()
        course = CourseFactory()
        enroll(student, course)
        with time_machine.travel(datetime(2026, 10, 9, 14, 0, tzinfo=NY)):
            today = AssessmentFactory(
                course=course, due_at=datetime(2026, 10, 9, 23, 59, tzinfo=NY)
            )
            tomorrow = AssessmentFactory(
                course=course, due_at=datetime(2026, 10, 10, 0, 0, tzinfo=NY)
            )
            plan(student, reason="test")
            data = client_for(student).get("/api/v1/pulse/schedule?view=today").data
        ids = {d["id"] for d in data["deadlines"]}
        assert today.id in ids
        assert tomorrow.id not in ids


def test_schedule_endpoint_query_count(setup, django_assert_max_num_queries):
    student, course, *_ = setup
    for _ in range(5):
        AssessmentFactory(course=course)
    plan(student, reason="test")
    client = client_for(student)
    with django_assert_max_num_queries(16):
        client.get("/api/v1/pulse/schedule?view=overall")


def test_availability_merges_overlaps_and_validates_length():
    student = make_student()
    client = client_for(student)
    overlapping = {
        "blocks": [
            {"weekday": 0, "start_time": "18:00", "end_time": "20:00"},
            {"weekday": 0, "start_time": "19:00", "end_time": "21:00"},
            {"weekday": 0, "start_time": "21:00", "end_time": "22:00"},
            {"weekday": 2, "start_time": "22:00", "end_time": "00:00"},
        ]
    }
    response = client.put("/api/v1/pulse/availability", overlapping, format="json")
    assert response.status_code == 200
    assert response.data["merged"] == 2
    assert [(b["weekday"], b["start_time"], b["end_time"]) for b in response.data["blocks"]] == [
        (0, "18:00:00", "22:00:00"),
        (2, "22:00:00", "00:00:00"),
    ]
    too_short = {"blocks": [{"weekday": 0, "start_time": "18:00", "end_time": "18:20"}]}
    bad = client.put("/api/v1/pulse/availability", too_short, format="json")
    assert bad.status_code == 400
    backwards = {"blocks": [{"weekday": 0, "start_time": "18:00", "end_time": "17:00"}]}
    assert client.put("/api/v1/pulse/availability", backwards, format="json").status_code == 400
