from datetime import time

from django.core.management.base import BaseCommand, CommandError

from lms.registration import Meeting, Registration, register_course

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def parse_meeting(raw: str) -> Meeting:
    """`mon 10:00-11:15 Hartley Hall 120`"""
    try:
        day, span, *room = raw.split()
        start, end = span.split("-")
        return Meeting(DAYS.index(day.lower()[:3]), time.fromisoformat(start),
                       time.fromisoformat(end), " ".join(room))  # fmt: skip
    except ValueError as exc:
        raise CommandError(f"Can't read meeting {raw!r}; use 'mon 10:00-11:15 Room'.") from exc


class Command(BaseCommand):
    help = "Pre-register a course for the current term. Its teacher claims it by signing up."

    def add_arguments(self, parser):
        parser.add_argument("code", help='Course code, e.g. "CS 201"')
        parser.add_argument("title")
        parser.add_argument("teacher_email")
        parser.add_argument("--teacher-name", default="", help='"First Last"')
        parser.add_argument("--color", default="#1f6f5c")
        parser.add_argument("--description", default="")
        parser.add_argument("--office-hours", default="")
        parser.add_argument(
            "--meeting", action="append", default=[], help="'mon 10:00-11:15 Room', repeatable"
        )

    def handle(self, *args, **opts):
        first, _, last = opts["teacher_name"].partition(" ")
        try:
            course = register_course(
                Registration(
                    code=opts["code"], title=opts["title"], teacher_email=opts["teacher_email"],
                    teacher_first_name=first, teacher_last_name=last, color=opts["color"],
                    description=opts["description"], office_hours=opts["office_hours"],
                    meetings=[parse_meeting(m) for m in opts["meeting"]],
                )
            )  # fmt: skip
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Registered {course.code} for {course.term.name}. "
                f"{opts['teacher_email']} can now sign up as a teacher to claim it."
            )
        )
