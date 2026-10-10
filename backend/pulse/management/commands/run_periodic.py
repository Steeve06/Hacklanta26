from django.core.management.base import BaseCommand

from config.periodic import run_all


class Command(BaseCommand):
    help = "Run the periodic jobs once. Use from cron every 10 minutes when Celery Beat is off."

    def handle(self, *args, **options):
        result = run_all()
        self.stdout.write(
            f"Quiz windows settled: {result['quiz_windows']}. "
            f"Notifications created: {result['notifications']}. "
            f"Students rolled forward: {result['rolled_forward']}."
        )
