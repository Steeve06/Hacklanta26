
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lms", "0001_initial"),
        ("quizzes", "0005_timed_sessions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(
            name="DeckAnswer",
        ),
        migrations.RemoveField(
            model_name="streakevent",
            name="deck",
        ),
        migrations.DeleteModel(
            name="CardReview",
        ),
        migrations.DeleteModel(
            name="DailyDeck",
        ),
        migrations.DeleteModel(
            name="Flashcard",
        ),
        migrations.CreateModel(
            name="CheckAttempt",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("number", models.PositiveSmallIntegerField()),
                (
                    "cards",
                    models.JSONField(
                        default=list,
                        help_text="[{question_id, order: [option indexes]}]",
                    ),
                ),
                ("started_at", models.DateTimeField()),
                ("last_answer_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("correct", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "ordering": ["number"],
            },
        ),
        migrations.RemoveField(
            model_name="streak",
            name="last_day",
        ),
        migrations.CreateModel(
            name="CheckQuestion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("multiple_choice", "Multiple Choice"),
                            ("true_false", "True False"),
                        ],
                        max_length=20,
                    ),
                ),
                ("prompt", models.TextField()),
                ("options", models.JSONField()),
                ("correct_index", models.PositiveSmallIntegerField()),
                ("explanation", models.TextField()),
                ("source_excerpt", models.TextField()),
                (
                    "content_hash",
                    models.CharField(
                        db_index=True, help_text="chapter version", max_length=64
                    ),
                ),
                (
                    "origin",
                    models.CharField(
                        choices=[("ai", "Ai"), ("cloze", "Cloze")], max_length=10
                    ),
                ),
                ("retired", models.BooleanField(default=False)),
                (
                    "chapter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bank",
                        to="lms.chapter",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CheckAnswer",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("position", models.PositiveSmallIntegerField()),
                (
                    "chosen_index",
                    models.PositiveSmallIntegerField(
                        help_text="index in the original options"
                    ),
                ),
                ("correct", models.BooleanField()),
                (
                    "attempt",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="answers",
                        to="quizzes.checkattempt",
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="answers",
                        to="quizzes.checkquestion",
                    ),
                ),
            ],
            options={
                "ordering": ["position"],
            },
        ),
        migrations.CreateModel(
            name="StudyCheck",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[("scheduled", "Scheduled"), ("early", "Early")],
                        default="scheduled",
                        max_length=20,
                    ),
                ),
                ("scheduled_date", models.DateField()),
                ("opens_at", models.DateTimeField(db_index=True)),
                ("closes_at", models.DateTimeField(db_index=True)),
                (
                    "timezone",
                    models.CharField(
                        help_text="the student's zone when it was made", max_length=64
                    ),
                ),
                ("passed", models.BooleanField(default=False)),
                ("counted_for_streak", models.BooleanField(default=False)),
                (
                    "resolved",
                    models.BooleanField(
                        default=False, help_text="streak outcome recorded"
                    ),
                ),
                (
                    "chapters",
                    models.ManyToManyField(
                        related_name="study_checks", to="lms.chapter"
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="study_checks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["opens_at"],
            },
        ),
        migrations.AddField(
            model_name="checkattempt",
            name="study_check",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="attempts",
                to="quizzes.studycheck",
            ),
        ),
        migrations.AddField(
            model_name="streakevent",
            name="study_check",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="event",
                to="quizzes.studycheck",
            ),
        ),
        migrations.AddIndex(
            model_name="checkquestion",
            index=models.Index(
                fields=["chapter", "retired"], name="quizzes_che_chapter_082808_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="checkanswer",
            constraint=models.UniqueConstraint(
                fields=("attempt", "position"), name="uniq_check_answer"
            ),
        ),
        migrations.AddIndex(
            model_name="studycheck",
            index=models.Index(
                fields=["student", "closes_at"], name="quizzes_stu_student_e172e7_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="checkattempt",
            constraint=models.UniqueConstraint(
                fields=("study_check", "number"), name="uniq_check_attempt"
            ),
        ),
        migrations.AddConstraint(
            model_name="checkattempt",
            constraint=models.CheckConstraint(
                condition=models.Q(("number__gte", 1), ("number__lte", 2)),
                name="check_attempt_1_or_2",
            ),
        ),
    ]
