"""API обратной связи (DRF, SPEC §6.1, issue #34).

Права:
- список публичных благодарностей — всем аутентифицированным;
- создание благодарности/запроса ОС — аутентифицированным;
- отправитель автоматически = текущий сотрудник.
"""

from __future__ import annotations

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.orgstructure.models import Employee

from .models import FeedbackRequest, Praise
from .serializers import FeedbackRequestSerializer, PraiseSerializer


def _current_employee(user: object) -> Employee | None:
    """Текущий сотрудник по пользователю (для установки отправителя)."""
    user_id = getattr(user, "pk", None)
    if user_id is None:
        return None
    return Employee.objects.filter(user_id=user_id).first()


class PraiseViewSet(viewsets.ModelViewSet[Praise]):
    """CRUD благодарностей: лента публичных + создание."""

    serializer_class = PraiseSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Лента: публичные благодарности (SPEC §6.1)."""
        return Praise.objects.filter(is_public=True).select_related("recipient", "sender")

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Все действия — аутентифицированным (создание и просмотр)."""
        return [IsAuthenticated()]

    def perform_create(self, serializer: PraiseSerializer) -> None:  # type: ignore[override]
        """Установить отправителя = текущий сотрудник."""
        employee = _current_employee(self.request.user)
        if employee is not None:
            serializer.save(sender=employee)
        else:
            serializer.save()


class FeedbackRequestViewSet(viewsets.ModelViewSet[FeedbackRequest]):
    """CRUD запросов обратной связи."""

    serializer_class = FeedbackRequestSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Список запросов: полученные + отправленные текущим сотрудником."""
        employee = _current_employee(self.request.user)
        if employee is None:
            return FeedbackRequest.objects.none()
        return FeedbackRequest.objects.filter(recipient=employee) | FeedbackRequest.objects.filter(
            requester=employee
        )

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Все действия — аутентифицированным."""
        return [IsAuthenticated()]

    def perform_create(self, serializer: FeedbackRequestSerializer) -> None:  # type: ignore[override]
        """Установить запросчика = текущий сотрудник."""
        employee = _current_employee(self.request.user)
        if employee is not None:
            serializer.save(requester=employee)
        else:
            serializer.save()
