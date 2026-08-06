"""URL-конфигурация модуля компетенций (подключается под /api/v1/competencies/)."""

from __future__ import annotations

from rest_framework import routers

from .views import (
    CompetencyFrameworkViewSet,
    CompetencyGroupViewSet,
    CompetencyViewSet,
    IndicatorViewSet,
    ScaleViewSet,
)

router = routers.DefaultRouter()
router.register("scales", ScaleViewSet, basename="scale")
router.register("groups", CompetencyGroupViewSet, basename="competency-group")
router.register("competencies", CompetencyViewSet, basename="competency")
router.register("indicators", IndicatorViewSet, basename="indicator")
router.register("frameworks", CompetencyFrameworkViewSet, basename="framework")

app_name = "competencies"
urlpatterns = router.urls
