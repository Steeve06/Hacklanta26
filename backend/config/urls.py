from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .health import health

api_v1 = [
    path("", include("accounts.urls")),
    path("", include("lms.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", health),
    path("api/v1/", include(api_v1)),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema")),
]
