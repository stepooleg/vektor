"""API аналитики: дашборд по сотруднику (SPEC §9.2, issue #15).

Права: сотрудник видит себя, руководитель — подчинённых, HR — всех.
Данные — только агрегаты (без сырых оценок, SPEC §6.3).
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orgstructure.models import Employee
from apps.users.models import Role

from .services import build_company_dashboard, build_employee_dashboard, can_view_employee_dashboard


class EmployeeDashboardView(APIView):
    """``GET /api/v1/analytics/employees/<id>/dashboard/`` — дашборд сотрудника."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request, employee_id: int) -> Response:
        """Вернуть агрегированный дашборд сотрудника с проверкой прав."""
        target = Employee.objects.filter(id=employee_id).first()
        if target is None:
            return Response({"detail": "Сотрудник не найден."}, status=status.HTTP_404_NOT_FOUND)

        viewer_user_id = request.user.id
        viewer = Employee.objects.filter(user_id=viewer_user_id).first() if viewer_user_id else None
        if viewer is None or not can_view_employee_dashboard(viewer, target):
            return Response(
                {"detail": "Недостаточно прав для просмотра дашборда."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(build_employee_dashboard(target))


class CompanyDashboardView(APIView):
    """``GET /api/v1/analytics/company-dashboard/`` — дашборд компании (§9.1).

    Доступ: HR и руководители. Агрегаты без сырых данных (§6.3).
    """

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        """Вернуть агрегированный дашборд компании."""
        user = request.user
        assert user.pk is not None  # IsAuthenticated гарантирует
        if not user.has_any_role(Role.Code.HR.value, Role.Code.MANAGER.value):
            return Response(
                {"detail": "Дашборд компании доступен HR и руководителям."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(build_company_dashboard())
