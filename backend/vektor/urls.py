"""Корневая URL-конфигурация Vektor.

Структура:
- ``/admin/`` — встроенный админ-интерфейс Django;
- ``/api/v1/health/`` — health-check;
- ``/api/v1/schema/`` и ``/api/v1/docs/`` — OpenAPI-схема и Swagger UI.

URL-префикс версии (``v1``) берётся из ``vektor.API_VERSION``.
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from vektor import API_VERSION
from vektor.views import HealthView

# Все API-маршруты живут под этим префиксом.
API_PREFIX: str = f"api/{API_VERSION}"

urlpatterns = [
    path("admin/", admin.site.urls),
    # API v1.
    path(f"{API_PREFIX}/health/", HealthView.as_view(), name="api-health"),
    path(f"{API_PREFIX}/auth/", include("apps.users.urls")),
    path(f"{API_PREFIX}/competencies/", include("apps.competencies.urls")),
    path(f"{API_PREFIX}/assessment/", include("apps.assessment.urls")),
    path(f"{API_PREFIX}/notifications/", include("apps.notifications.urls")),
    path(f"{API_PREFIX}/lms/", include("apps.lms.urls")),
    path(f"{API_PREFIX}/analytics/", include("apps.analytics.urls")),
    path(f"{API_PREFIX}/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        f"{API_PREFIX}/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
]
