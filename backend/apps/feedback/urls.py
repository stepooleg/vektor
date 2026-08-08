"""URL-конфигурация обратной связи (под /api/v1/feedback/)."""

from __future__ import annotations

from rest_framework import routers

from .views import FeedbackRequestViewSet, PraiseViewSet

router = routers.DefaultRouter()
router.register("praises", PraiseViewSet, basename="praise")
router.register("requests", FeedbackRequestViewSet, basename="feedback-request")

app_name = "feedback"
urlpatterns = router.urls
