from django.contrib import admin

from .models import BankQuestion, ChapterQuiz, Streak, StreakEvent


@admin.register(BankQuestion)
class BankQuestionAdmin(admin.ModelAdmin):
    list_display = ["chapter", "type", "prompt", "origin", "retired"]
    list_filter = ["origin", "retired", "chapter__course"]


@admin.register(ChapterQuiz)
class ChapterQuizAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "scheduled_date",
        "opens_at",
        "closes_at",
        "submitted_at",
        "counted_for_streak",
    ]


admin.site.register(Streak, list_display=["student", "current", "longest", "freezes"])
admin.site.register(StreakEvent, list_display=["student", "result", "streak_after", "created_at"])
