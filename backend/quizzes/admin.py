from django.contrib import admin

from .models import CheckAttempt, CheckQuestion, Streak, StreakEvent, StudyCheck


@admin.register(CheckQuestion)
class CheckQuestionAdmin(admin.ModelAdmin):
    list_display = ["chapter", "type", "prompt", "origin", "retired"]
    list_filter = ["origin", "retired", "chapter__course"]


class AttemptInline(admin.TabularInline):
    model = CheckAttempt
    extra = 0
    fields = ["number", "started_at", "finished_at", "correct"]
    readonly_fields = fields


@admin.register(StudyCheck)
class StudyCheckAdmin(admin.ModelAdmin):
    list_display = ["student", "scheduled_date", "opens_at", "closes_at", "passed", "resolved"]
    list_filter = ["passed", "resolved"]
    inlines = [AttemptInline]


admin.site.register(Streak, list_display=["student", "current", "longest", "freezes"])
admin.site.register(
    StreakEvent, list_display=["student", "result", "streak_after", "study_check", "created_at"]
)
