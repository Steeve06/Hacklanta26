from django.contrib import admin

from .models import AvailabilityBlock, Blackout, PlanJob, Schedule, Session


class SessionInline(admin.TabularInline):
    model = Session
    extra = 0
    fields = ["start", "end", "kind", "title", "status", "completed_minutes"]


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ["student", "version", "is_active", "generated_at"]
    list_filter = ["is_active"]
    inlines = [SessionInline]


admin.site.register(
    AvailabilityBlock, list_display=["student", "weekday", "start_time", "end_time"]
)
admin.site.register(Blackout, list_display=["student", "start", "end", "label"])
admin.site.register(PlanJob, list_display=["student", "kind", "state", "progress", "created_at"])
