"""API обратной связи (DRF, SPEC §6.1, issue #34).

Права:
- список публичных благодарностей — всем аутентифицированным;
- создание благодарности/запроса ОС — аутентифицированным;
- отправитель автоматически = текущий сотрудник.
"""

from __future__ import annotations

from typing import cast

from django.db.models import Q
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.orgstructure.models import Employee
from apps.users.models import User

from .models import FeedbackRequest, Praise
from .serializers import FeedbackRequestSerializer, PraiseSerializer


def _current_employee(user: object) -> Employee | None:
    """Текущий сотрудник по пользователю (для установки отправителя)."""
    user_id = getattr(user, "pk", None)
    if user_id is None:
        return None
    return Employee.objects.filter(user_id=user_id).first()


class PraiseViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet[Praise],
):
    """CRUD благодарностей: лента публичных + создание."""

    serializer_class = PraiseSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Публичная лента + приватные благодарности участника."""
        employee = _current_employee(self.request.user)
        visible = Q(is_public=True)
        if employee is not None:
            visible |= Q(sender=employee) | Q(recipient=employee)
        return Praise.objects.filter(visible).select_related("recipient", "sender").distinct()

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Все действия — аутентифицированным (создание и просмотр)."""
        return [IsAuthenticated()]

    def perform_create(self, serializer: PraiseSerializer) -> None:  # type: ignore[override]
        """Установить отправителя = текущий сотрудник."""
        employee = _current_employee(self.request.user)
        if employee is None:
            raise NotFound("Профиль сотрудника не найден.")
        recipient = serializer.validated_data["recipient"]
        if recipient == employee:
            raise ValidationError({"recipient": "Выберите другого сотрудника."})
        praise = serializer.save(sender=employee)

        from apps.audit.services import log_action
        from apps.notifications.models import NotificationEvent
        from apps.notifications.services import dispatch_notification
        from apps.portfolio.services import add_praise_to_portfolio

        add_praise_to_portfolio(praise)
        dispatch_notification(
            event=NotificationEvent.FEEDBACK_RECEIVED.value,
            user=recipient.user,
            context={},
        )
        log_action(
            actor=cast(User, self.request.user),
            action="feedback.praise.create",
            target_type="feedback.praise",
            target_id=str(praise.id),
            details={"recipient_id": recipient.id, "anonymous": praise.is_anonymous},
        )


class FeedbackRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet[FeedbackRequest],
):
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

    def perform_create(  # type: ignore[override]
        self, serializer: FeedbackRequestSerializer
    ) -> None:
        """Установить запросчика = текущий сотрудник."""
        employee = _current_employee(self.request.user)
        if employee is None:
            raise NotFound("Профиль сотрудника не найден.")
        recipient = serializer.validated_data["recipient"]
        if recipient == employee:
            raise ValidationError({"recipient": "Выберите другого сотрудника."})
        feedback_request = serializer.save(requester=employee)

        from apps.audit.services import log_action
        from apps.notifications.models import NotificationEvent
        from apps.notifications.services import dispatch_notification

        dispatch_notification(
            event=NotificationEvent.FEEDBACK_RECEIVED.value,
            user=recipient.user,
            context={},
        )
        log_action(
            actor=cast(User, self.request.user),
            action="feedback.request.create",
            target_type="feedback.request",
            target_id=str(feedback_request.id),
            details={"recipient_id": recipient.id},
        )

    @action(detail=False, methods=["get"])
    def recipients(self, request: Request) -> Response:
        """Вернуть активных коллег для форм благодарности и запроса ОС."""
        employee = _current_employee(request.user)
        if employee is None:
            raise NotFound("Профиль сотрудника не найден.")
        colleagues = (
            Employee.objects.filter(is_active=True)
            .exclude(pk=employee.pk)
            .select_related("department")
        )
        return Response(
            [
                {
                    "id": colleague.id,
                    "full_name": colleague.full_name,
                    "department": colleague.department.name,
                }
                for colleague in colleagues
            ]
        )
