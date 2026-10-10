from django.contrib import admin

from .models import (
    Assessment,
    Chapter,
    Course,
    DiscussionPost,
    DueDateOverride,
    Enrollment,
    Submission,
    Syllabus,
    SyllabusWeek,
    Term,
)

admin.site.register(Term)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["code", "title", "instructor", "term"]


admin.site.register(Enrollment, list_display=["user", "course", "role"], list_filter=["course"])


class SyllabusWeekInline(admin.TabularInline):
    model = SyllabusWeek
    extra = 0


@admin.register(Syllabus)
class SyllabusAdmin(admin.ModelAdmin):
    inlines = [SyllabusWeekInline]


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ["course", "order", "title", "available_from"]
    list_filter = ["course"]


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ["course", "title", "type", "due_at", "weight_pct", "published"]
    list_filter = ["course", "type", "published"]


admin.site.register(DueDateOverride, list_display=["assessment", "student", "due_at"])
admin.site.register(Submission, list_display=["assessment", "student", "status", "score"])
admin.site.register(DiscussionPost, list_display=["assessment", "author", "created_at"])
