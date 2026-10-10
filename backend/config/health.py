import logging

from django.conf import settings
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health(request):
    checks = {"database": "ok", "redis": "not configured", "ai": "fallback only"}
    healthy = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        logger.exception("Database health check failed")
        checks["database"] = "error"
        healthy = False
    if settings.REDIS_URL:
        try:
            import redis

            redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2).ping()
            checks["redis"] = "ok"
        except Exception:
            logger.warning("Redis health check failed")
            checks["redis"] = "error"
            healthy = False
    if settings.AI_PROVIDER and settings.AI_API_KEY:
        checks["ai"] = f"configured ({settings.AI_PROVIDER})"
    return JsonResponse(
        {"status": "ok" if healthy else "degraded", **checks}, status=200 if healthy else 503
    )
