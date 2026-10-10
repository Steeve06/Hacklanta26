import os

from celery import Celery
from celery.schedules import crontab

from config.env import load_dotenv_file

load_dotenv_file()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("pulse")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

BEAT_SCHEDULE = {
    "notification-scan": {
        "task": "notifications.tasks.scan_all",
        "schedule": crontab(minute="*/10"),
    },
    "study-check-sweep": {
        "task": "quizzes.tasks.sweep_checks",
        "schedule": crontab(minute="*/10"),
    },
    "nightly-roll-forward": {
        "task": "pulse.tasks.roll_forward_due_students",
        "schedule": crontab(minute=5),
    },
}


@app.on_after_finalize.connect
def _configure_beat(sender, **kwargs):
    from django.conf import settings

    sender.conf.beat_schedule = BEAT_SCHEDULE if settings.USE_CELERY_BEAT else {}
