"""URL-конфигурация модуля оценки (подключается под /api/v1/assessment/)."""

from __future__ import annotations

from rest_framework import routers

from .views import AssessmentCycleViewSet, ParticipantViewSet, ReviewerAssignmentViewSet

router = routers.DefaultRouter()
router.register("cycles", AssessmentCycleViewSet, basename="assessment-cycle")
router.register("participants", ParticipantViewSet, basename="assessment-participant")
router.register("assignments", ReviewerAssignmentViewSet, basename="assessment-assignment")

app_name = "assessment"
urlpatterns = router.urls
