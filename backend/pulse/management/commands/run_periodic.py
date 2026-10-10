from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the periodic jobs once. Use from cron every 10 minutes when Celery Beat is off."

    def handle(self, *args, **options):
        from notifications.tasks import scan_all
        from pulse.tasks import roll_forward_due_students

        created = scan_all()
        rolled = roll_forward_due_students()
        self.stdout.write(f"Notifications created: {created}. Students rolled forward: {rolled}.")
