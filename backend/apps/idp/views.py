"""Read-only API индивидуальных планов развития (SPEC §8, issue #63)."""

from __future__ import annotations

from typing import cast

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.orgstructure.models import Employee
from apps.users.models import Role, User

from .models import DevelopmentPlan
from .serializers import DevelopmentPlanSerializer


class DevelopmentPlanViewSet(viewsets.ReadOnlyModelViewSet[DevelopmentPlan]):
    """Просмотр ИПР с ограничением по оргструктуре и ролям."""

    serializer_class = DevelopmentPlanSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self) -> QuerySet[DevelopmentPlan]:
        """Сотрудник видит себя, руководитель — команду, HR — всех."""
        user = cast(User, self.request.user)
        viewer = Employee.objects.filter(user_id=user.pk).first()
        queryset = DevelopmentPlan.objects.select_related("employee").prefetch_related(
            "goals__actions"
        )
        if viewer is None:
            return queryset.none()

        if user.has_any_role(Role.Code.HR.value):
            return queryset
        if user.has_any_role(Role.Code.MANAGER.value):
            employee_ids = list(viewer.get_subordinates().values_list("id", flat=True))
            employee_ids.append(viewer.id)
            return queryset.filter(employee_id__in=employee_ids)
        return queryset.filter(employee=viewer)
