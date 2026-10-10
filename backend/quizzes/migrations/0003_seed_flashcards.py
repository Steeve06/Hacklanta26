from django.db import migrations


def forwards(apps, schema_editor):
    from quizzes.cards import CARDS

    Flashcard = apps.get_model("quizzes", "Flashcard")
    for slug, topic, front, back in CARDS:
        Flashcard.objects.update_or_create(
            slug=slug, defaults={"topic": topic, "front": front, "back": back, "active": True}
        )
    # Streaks carried over from chapter quizzes become daily streaks that last ran on the day of
    # their latest event, so the first missed day after the switch is settled normally.
    Streak = apps.get_model("quizzes", "Streak")
    StreakEvent = apps.get_model("quizzes", "StreakEvent")
    for streak in Streak.objects.filter(current__gt=0, last_day__isnull=True):
        last = StreakEvent.objects.filter(student_id=streak.student_id).order_by("-created_at")
        latest = last.first()
        if latest:
            streak.last_day = latest.created_at.date()
            streak.save(update_fields=["last_day"])


class Migration(migrations.Migration):
    dependencies = [("quizzes", "0002_daily_flashcards")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
