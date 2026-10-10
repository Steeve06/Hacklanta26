from django.db import migrations


def seed(apps, schema_editor):
    from notifications.templates_loader import load_templates

    load_templates(apps.get_model("notifications", "NotificationTemplate"))


class Migration(migrations.Migration):
    """Reminder copy names the app Leon."""

    dependencies = [("notifications", "0005_study_check_copy")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
