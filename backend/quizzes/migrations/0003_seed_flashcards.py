from django.db import migrations


def forwards(apps, schema_editor):
    # The general flashcard library this migration used to load was removed when study checks
    # replaced daily decks (0005 drops the table), so only the streak carry-over remains.
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
