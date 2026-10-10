"""The periodic jobs, runnable from Celery Beat, `manage.py run_periodic` or the cron endpoint."""

import hmac

from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


def run_all() -> dict[str, int]:
    from notifications.tasks import scan_all
    from pulse.tasks import roll_forward_due_students
    from quizzes.tasks import sweep_streaks

    return {
        "streaks_settled": sweep_streaks(),
        "notifications": scan_all(),
        "rolled_forward": roll_forward_due_students(),
    }


@csrf_exempt
@require_POST
def cron(request):
    """POST /api/cron with header X-Cron-Token. Disabled (404) when CRON_TOKEN is empty."""
    token = settings.CRON_TOKEN
    if not token:
        raise Http404
    if not hmac.compare_digest(request.headers.get("X-Cron-Token", ""), token):
        return JsonResponse({"detail": "Forbidden."}, status=403)
    return JsonResponse(run_all())
