"""URL-конфигурация ИПР (под /api/v1/idp/)."""

from __future__ import annotations

from rest_framework import routers

from .views import DevelopmentPlanViewSet

router = routers.DefaultRouter()
router.register("plans", DevelopmentPlanViewSet, basename="development-plan")

app_name = "idp"
urlpatterns = router.urls
