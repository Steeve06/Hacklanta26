from datetime import timedelta

from django.contrib import admin
from django.db.models import Count, Sum
from django.utils import timezone

from .models import AICache, AICallLog


@admin.register(AICallLog)
class AICallLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "purpose", "model", "input_tokens", "output_tokens", "cost_usd",
                    "latency_ms", "success", "fallback_used"]  # fmt: skip
    list_filter = ["purpose", "success", "fallback_used", "model"]
    readonly_fields = [f.name for f in AICallLog._meta.fields]

    def changelist_view(self, request, extra_context=None):
        since = timezone.now() - timedelta(days=1)
        today = AICallLog.objects.filter(created_at__gte=since).aggregate(
            cost=Sum("cost_usd"), calls=Count("id")
        )
        extra_context = {
            **(extra_context or {}),
            "title": f"AI calls · last 24 h: {today['calls']} calls, ${today['cost'] or 0:.4f}",
        }
        return super().changelist_view(request, extra_context=extra_context)


admin.site.register(AICache, list_display=["purpose", "key", "created_at"])
