from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .health import health
from .periodic import cron

api_v1 = [
    path("", include("accounts.urls")),
    path("", include("lms.urls")),
    path("pulse/", include("pulse.urls")),
    path("", include("notifications.urls")),
    path("", include("quizzes.urls")),
    path("", include("pulse.onboarding_views")),
    path("assistant/", include("assistant.urls")),
    path("demo/", include("pulse.demo_urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", health),
    path("api/cron", cron),
    path("api/v1/", include(api_v1)),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema")),
]
