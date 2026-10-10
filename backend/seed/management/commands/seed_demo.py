from django.core.management.base import BaseCommand
from django.db import transaction

from lms import catalog
from seed import lms_seed, pulse_seed, quiz_seed


class Command(BaseCommand):
    help = "Create (or reset) the demo term, courses, accounts and history."

    def handle(self, *args, **options):
        with transaction.atomic():
            lms_seed.reset()
            demo = lms_seed.build_term()
            lms_seed.seed_history(demo)
            lms_seed.mark_profiles(demo)
            quiz_seed.seed_cards()
            quiz_seed.seed_streaks(demo.students)
            pulse_seed.seed_plans(demo.students)
            pulse_seed.seed_onboarding(demo.students)
            reenrolled = lms_seed.reenroll_signups()
        catalog.invalidate_all()
        self.stdout.write(self.style.SUCCESS(f"Seeded {demo.term.name}, starting {demo.start}."))
        if reenrolled:
            self.stdout.write(f"Re-enrolled {reenrolled} signed-up students in the new term.")
        self.stdout.write("")
        self.stdout.write(f"All demo passwords: {lms_seed.PASSWORD}")
        for spec in [
            ("maya@pulse.test", "student, on track"),
            ("sam@pulse.test", "student, slightly behind"),
            ("jordan@pulse.test", "student, badly behind"),
            ("alex@pulse.test", "student, has an extension in CS 201"),
            ("riley@pulse.test", "student, brand new (onboarding not started)"),
            ("casey@pulse.test", "student, halfway through onboarding (step 3)"),
            ("prof.okafor@pulse.test", "instructor, CS 201"),
            ("dr.marsh@pulse.test", "instructor, PSY 101"),
            ("prof.reyes@pulse.test", "instructor, BUS 210"),
            ("admin@pulse.test", "admin, demo controls and Django admin"),
        ]:
            self.stdout.write(f"  {spec[0]:<26} {spec[1]}")
        self.stdout.write("")
        self.stdout.write("App:          http://localhost:5173")
        self.stdout.write("API docs:     http://localhost:8000/api/docs")
        self.stdout.write("Django admin: http://localhost:8000/admin")
