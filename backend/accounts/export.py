"""Student data export (FERPA/GDPR access request)."""

from django.apps import apps
from django.forms.models import model_to_dict

EXPORTED = [
    ("lms", "ChapterProgress", "student"),
    ("lms", "Submission", "student"),
    ("lms", "DiscussionPost", "author"),
    ("lms", "QuizAttempt", "student"),
    ("pulse", "AvailabilityBlock", "student"),
    ("pulse", "Blackout", "student"),
    ("pulse", "Schedule", "student"),
    ("pulse", "StatusSnapshot", "student"),
    ("notifications", "Notification", "student"),
]


def _plain(row: dict) -> dict:
    return {key: (str(value) if value is not None else None) for key, value in row.items()}


def build_export(user) -> dict:
    data: dict = {
        "user": {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "timezone": user.timezone,
        }
    }
    profile = getattr(user, "profile", None)
    if profile is not None:
        data["profile"] = _plain(model_to_dict(profile, exclude=["id", "user"]))
    for app_label, model_name, owner in EXPORTED:
        model = apps.get_model(app_label, model_name)
        rows = model.objects.filter(**{owner: user}).order_by("pk")
        data[f"{app_label}.{model_name}"] = [
            _plain(model_to_dict(row, exclude=[owner, "file"])) for row in rows
        ]
    return data
