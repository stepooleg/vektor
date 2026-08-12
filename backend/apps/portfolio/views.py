"""API портфолио (DRF, SPEC §6.2, issue #34).

Просмотр: сотрудник видит своё портфолио; руководитель/HR — подчинённых.
"""

from __future__ import annotations

from typing import cast

from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.orgstructure.models import Employee
from apps.users.models import Role, User

from .models import PortfolioEntry
from .serializers import PortfolioEntrySerializer


def _current_employee(user: object) -> Employee | None:
    """Текущий сотрудник по пользователю."""
    user_id = getattr(user, "pk", None)
    if user_id is None:
        return None
    return Employee.objects.filter(user_id=user_id).first()


class PortfolioEntryViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet[PortfolioEntry],
):
    """CRUD записей портфолио."""

    serializer_class = PortfolioEntrySerializer
    permission_classes = (IsAuthenticated,)

    @action(detail=False, methods=["get"])
    def targets(self, request: Request) -> Response:
        """Вернуть себя и доступных руководителю подчинённых для формы."""
        viewer = _current_employee(request.user)
        if viewer is None:
            raise NotFound("Профиль сотрудника не найден.")
        user = cast(User, request.user)
        employees = [viewer]
        if user.has_any_role(Role.Code.MANAGER.value):
            employees.extend(viewer.get_subordinates().select_related("department"))
        return Response(
            [
                {
                    "id": employee.id,
                    "full_name": employee.full_name,
                    "department": employee.department.name,
                    "is_self": employee.id == viewer.id,
                }
                for employee in employees
            ]
        )

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Сотрудник видит своё портфолио; руководитель/HR — подчинённых."""
        viewer = _current_employee(self.request.user)
        if viewer is None:
            return PortfolioEntry.objects.none()
        user = self.request.user
        is_hr = getattr(user, "has_any_role", lambda *a: False)(Role.Code.HR.value)
        if is_hr:
            return PortfolioEntry.objects.select_related("employee").all()
        emp_id = self.request.query_params.get("employee")
        is_manager = getattr(user, "has_any_role", lambda *a: False)(Role.Code.MANAGER.value)
        if emp_id:
            if not is_manager:
                raise PermissionDenied("Портфолио команды доступно только руководителю.")
            allowed_ids = viewer.get_subordinates().values_list("id", flat=True)
            if not Employee.objects.filter(id=emp_id, id__in=allowed_ids).exists():
                raise PermissionDenied("Сотрудник не входит в вашу команду.")
            return PortfolioEntry.objects.filter(employee_id=emp_id)
        return PortfolioEntry.objects.filter(employee=viewer)

    def perform_create(  # type: ignore[override]
        self, serializer: PortfolioEntrySerializer
    ) -> None:
        """Добавить запись себе либо подчинённому для руководителя."""
        viewer = _current_employee(self.request.user)
        if viewer is None:
            raise NotFound("Профиль сотрудника не найден.")
        requested_employee = serializer.validated_data.get("employee")
        target = viewer
        user = cast(User, self.request.user)
        if requested_employee is not None and user.has_any_role(Role.Code.MANAGER.value):
            if not viewer.get_subordinates().filter(pk=requested_employee.pk).exists():
                raise PermissionDenied("Добавлять записи можно только сотрудникам своей команды.")
            target = requested_employee
        entry = serializer.save(employee=target)

        from apps.audit.services import log_action

        log_action(
            actor=user,
            action="portfolio.entry.create",
            target_type="portfolio.entry",
            target_id=str(entry.id),
            details={"employee_id": target.id, "type": entry.type},
        )
