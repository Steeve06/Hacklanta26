from django.db import migrations


def seed(apps, schema_editor):
    from notifications.templates_loader import load_templates

    load_templates(apps.get_model("notifications", "NotificationTemplate"))


class Migration(migrations.Migration):
    dependencies = [("notifications", "0003_daily_streak_copy")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
