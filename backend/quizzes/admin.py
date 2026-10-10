from django.contrib import admin

from .models import DailyDeck, Flashcard, Streak, StreakEvent


@admin.register(Flashcard)
class FlashcardAdmin(admin.ModelAdmin):
    list_display = ["front", "topic", "active"]
    list_filter = ["topic", "active"]
    search_fields = ["front", "back"]


@admin.register(DailyDeck)
class DailyDeckAdmin(admin.ModelAdmin):
    list_display = ["student", "day", "completed_at", "knew", "counted_for_streak"]


admin.site.register(Streak, list_display=["student", "current", "longest", "freezes", "last_day"])
admin.site.register(StreakEvent, list_display=["student", "day", "result", "streak_after"])
