"""URL-конфигурация ИПР (под /api/v1/idp/)."""

from __future__ import annotations

from rest_framework import routers

from .views import DevActionViewSet, DevelopmentPlanViewSet, DevGoalViewSet

router = routers.DefaultRouter()
router.register("plans", DevelopmentPlanViewSet, basename="development-plan")
router.register("goals", DevGoalViewSet, basename="development-goal")
router.register("actions", DevActionViewSet, basename="development-action")

app_name = "idp"
urlpatterns = router.urls
