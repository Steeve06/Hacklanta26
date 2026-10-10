from django.contrib import admin

from .models import ChatMessage, Conversation


class MessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    fields = ["role", "text", "state", "proposal", "used_ai", "created_at"]
    readonly_fields = fields


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["student", "created_at", "closed_at"]
    inlines = [MessageInline]
