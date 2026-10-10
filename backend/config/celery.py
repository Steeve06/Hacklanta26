import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("pulse")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "notification-scan": {
        "task": "notifications.tasks.scan_all",
        "schedule": crontab(minute="*/10"),
    },
    "quiz-window-sweep": {
        "task": "quizzes.tasks.sweep_windows",
        "schedule": crontab(minute="*/10"),
    },
    "nightly-roll-forward": {
        "task": "pulse.tasks.roll_forward_due_students",
        "schedule": crontab(minute=5),
    },
}
