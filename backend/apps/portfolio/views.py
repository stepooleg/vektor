"""API портфолио (DRF, SPEC §6.2, issue #34).

Просмотр: сотрудник видит своё портфолио; руководитель/HR — подчинённых.
"""

from __future__ import annotations

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.orgstructure.models import Employee
from apps.users.models import Role

from .models import PortfolioEntry
from .serializers import PortfolioEntrySerializer


def _current_employee(user: object) -> Employee | None:
    """Текущий сотрудник по пользователю."""
    user_id = getattr(user, "pk", None)
    if user_id is None:
        return None
    return Employee.objects.filter(user_id=user_id).first()


class PortfolioEntryViewSet(viewsets.ModelViewSet[PortfolioEntry]):
    """CRUD записей портфолио."""

    serializer_class = PortfolioEntrySerializer
    permission_classes = (IsAuthenticated,)

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
        if emp_id and is_manager:
            return PortfolioEntry.objects.filter(employee_id=emp_id)
        return PortfolioEntry.objects.filter(employee=viewer)
