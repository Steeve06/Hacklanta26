from django.core.management.base import BaseCommand
from django.db import transaction

from lms import catalog
from seed import lms_seed, pulse_seed, quiz_seed


class Command(BaseCommand):
    help = (
        "Create (or reset) the demo term, pre-registered courses and accounts. Courses start "
        "empty until their teacher signs up and adds content; --sample-content fills them with "
        "the sample chapters, assignments and student history instead."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--sample-content",
            action="store_true",
            help="Fill the courses with sample content and history (teachers already signed up).",
        )

    def handle(self, *args, **options):
        sample = options["sample_content"]
        with transaction.atomic():
            lms_seed.reset()
            demo = lms_seed.build_term(with_content=sample)
            if sample:
                lms_seed.seed_history(demo)
            lms_seed.mark_profiles(demo)
            if sample:
                quiz_seed.seed_banks()
                quiz_seed.seed_streaks(demo.students)
                quiz_seed.seed_xp(demo.students, demo.classmates)
            pulse_seed.seed_plans(demo.students)
            pulse_seed.seed_onboarding(demo.students)
            reenrolled = lms_seed.reenroll_signups()
        catalog.invalidate_all()
        self.stdout.write(self.style.SUCCESS(f"Seeded {demo.term.name}, starting {demo.start}."))
        if reenrolled:
            self.stdout.write(f"Re-enrolled {reenrolled} signed-up students in the new term.")
        self.stdout.write("")
        self.stdout.write(f"All demo passwords: {lms_seed.PASSWORD}")
        teachers = [
            ("prof.okafor@pulse.test", "instructor, CS 201"),
            ("dr.marsh@pulse.test", "instructor, PSY 101"),
            ("prof.reyes@pulse.test", "instructor, BUS 210"),
        ]
        if not sample:
            self.stdout.write("")
            self.stdout.write("Courses are empty. Teachers sign up (choose 'I teach') with:")
            for email, note in teachers:
                self.stdout.write(f"  {email:<26} {note.removeprefix('instructor, ')}")
            self.stdout.write("")
        for spec in [
            ("maya@pulse.test", "student, on track"),
            ("sam@pulse.test", "student, slightly behind"),
            ("jordan@pulse.test", "student, badly behind"),
            ("alex@pulse.test", "student, has an extension in CS 201"),
            ("riley@pulse.test", "student, brand new (onboarding not started)"),
            ("casey@pulse.test", "student, halfway through onboarding (step 3)"),
            *(teachers if sample else []),
            ("admin@pulse.test", "admin, demo controls and Django admin"),
        ]:
            self.stdout.write(f"  {spec[0]:<26} {spec[1]}")
        self.stdout.write("")
        self.stdout.write("App:          http://localhost:5173")
        self.stdout.write("API docs:     http://localhost:8000/api/docs")
        self.stdout.write("Django admin: http://localhost:8000/admin")
