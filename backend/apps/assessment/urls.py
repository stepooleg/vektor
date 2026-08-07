"""URL-конфигурация модуля оценки (подключается под /api/v1/assessment/)."""

from __future__ import annotations

from rest_framework import routers

from .views import AssessmentCycleViewSet, ParticipantViewSet

router = routers.DefaultRouter()
router.register("cycles", AssessmentCycleViewSet, basename="assessment-cycle")
router.register("participants", ParticipantViewSet, basename="assessment-participant")

app_name = "assessment"
urlpatterns = router.urls
