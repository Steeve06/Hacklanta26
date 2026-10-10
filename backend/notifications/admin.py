from django.contrib import admin

from .models import Notification, NotificationTemplate, PushSubscription


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ["trigger", "sass_level", "text", "active"]
    list_filter = ["trigger", "sass_level", "active"]
    search_fields = ["text"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "trigger",
        "tier",
        "scheduled_for",
        "sent_at",
        "cancelled_at",
        "action_taken",
    ]
    list_filter = ["trigger", "tier"]


admin.site.register(PushSubscription, list_display=["user", "created_at"])
