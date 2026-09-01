"""URL-конфигурация модуля обучения (подключается под /api/v1/lms/)."""

from __future__ import annotations

from rest_framework import routers

from .views import CategoryViewSet, CourseViewSet, SubmissionViewSet

router = routers.DefaultRouter()
router.register("categories", CategoryViewSet, basename="lms-category")
router.register("courses", CourseViewSet, basename="lms-course")
router.register("submissions", SubmissionViewSet, basename="lms-submission")

app_name = "lms"
urlpatterns = router.urls
