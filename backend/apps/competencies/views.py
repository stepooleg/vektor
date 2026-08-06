"""API компетенций (DRF, SPEC §4).

Права:
- чтение — всем аутентифицированным (компетенции нужны для оценки);
- создание/изменение/удаление — только HR/Методолог (SPEC §4.1, §2.1).
"""

from __future__ import annotations

from rest_framework import viewsets

from apps.users.permissions import IsAuthenticatedUser, IsHR, IsMethodologist

from .models import Competency, CompetencyFramework, CompetencyGroup, Indicator, Scale
from .serializers import (
    CompetencyFrameworkSerializer,
    CompetencyGroupSerializer,
    CompetencySerializer,
    IndicatorSerializer,
    ScaleSerializer,
)


class ScaleViewSet(viewsets.ModelViewSet[Scale]):
    """CRUD шкал оценки."""

    queryset = Scale.objects.all()
    serializer_class = ScaleSerializer

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Чтение — аутентифицированным; запись — HR/Методолог."""
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [(IsHR | IsMethodologist)()]
        return [IsAuthenticatedUser()]


class CompetencyGroupViewSet(viewsets.ModelViewSet[CompetencyGroup]):
    """CRUD групп компетенций."""

    queryset = CompetencyGroup.objects.all()
    serializer_class = CompetencyGroupSerializer

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Чтение — аутентифицированным; запись — HR/Методолог."""
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [(IsHR | IsMethodologist)()]
        return [IsAuthenticatedUser()]


class CompetencyViewSet(viewsets.ModelViewSet[Competency]):
    """CRUD компетенций."""

    queryset = Competency.objects.select_related("group", "scale").all()
    serializer_class = CompetencySerializer

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Чтение — аутентифицированным; запись — HR/Методолог."""
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [(IsHR | IsMethodologist)()]
        return [IsAuthenticatedUser()]


class IndicatorViewSet(viewsets.ModelViewSet[Indicator]):
    """CRUD поведенческих индикаторов."""

    queryset = Indicator.objects.select_related("competency").all()
    serializer_class = IndicatorSerializer

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Чтение — аутентифицированным; запись — HR/Методолог."""
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [(IsHR | IsMethodologist)()]
        return [IsAuthenticatedUser()]


class CompetencyFrameworkViewSet(viewsets.ModelViewSet[CompetencyFramework]):
    """CRUD моделей компетенций (framework) с привязкой."""

    queryset = CompetencyFramework.objects.all()
    serializer_class = CompetencyFrameworkSerializer

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Чтение — аутентифицированным; запись — HR/Методолог."""
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [(IsHR | IsMethodologist)()]
        return [IsAuthenticatedUser()]
