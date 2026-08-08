"""URL-конфигурация портфолио (под /api/v1/portfolio/)."""

from __future__ import annotations

from rest_framework import routers

from .views import PortfolioEntryViewSet

router = routers.DefaultRouter()
router.register("entries", PortfolioEntryViewSet, basename="portfolio-entry")

app_name = "portfolio"
urlpatterns = router.urls
