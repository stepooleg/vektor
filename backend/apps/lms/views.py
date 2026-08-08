"""API каталога курсов (DRF, SPEC §7.1, §7.3, issue #19).

Права:
- список курсов: аутентифицированным; сотрудник видит только опубликованные,
  Методолог/HR — все (включая черновики);
- создание/правка/удаление: Методолог (SPEC §7.3);
- категории: чтение всем, правка — Методолог.

Поиск: по title (icontains). Фильтры: category, competency, is_mandatory.
"""

from __future__ import annotations

from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.users.models import Role
from apps.users.permissions import IsAuthenticatedUser, IsMethodologist

from .models import Category, Course
from .serializers import CategorySerializer, CourseSerializer


class CourseFilter(filters.FilterSet):
    """Фильтры каталога курсов: категория, компетенция, обязательность."""

    # Привязка к компетенции проверяется через competency_links.
    competency = filters.NumberFilter(field_name="competency_links__competency_id")

    class Meta:
        """Метаданные фильтра курсов."""

        model = Course
        fields = ["category", "is_mandatory"]


class CategoryViewSet(viewsets.ModelViewSet[Category]):
    """CRUD категорий каталога: чтение всем, правка — Методолог."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Чтение — аутентифицированным; запись — Методолог."""
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsMethodologist()]
        return [IsAuthenticatedUser()]


class CourseViewSet(viewsets.ModelViewSet[Course]):
    """CRUD курсов с поиском и фильтрами (SPEC §7.1)."""

    serializer_class = CourseSerializer
    filterset_class = CourseFilter
    filter_backends = [SearchFilter, OrderingFilter, filters.DjangoFilterBackend]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "title"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Сотрудник видит только опубликованные; Методолог/HR — все."""
        qs = Course.objects.select_related("category").distinct()
        user = self.request.user
        is_staff = getattr(user, "is_authenticated", False)
        if is_staff and user.has_any_role(  # type: ignore[union-attr]
            Role.Code.METHODOLOGIST.value,
            Role.Code.HR.value,
        ):
            return qs
        return qs.filter(status=Course.Status.PUBLISHED.value)

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Чтение — аутентифицированным; запись — Методолог."""
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsMethodologist()]
        return [IsAuthenticatedUser()]
