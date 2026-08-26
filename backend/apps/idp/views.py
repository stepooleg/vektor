"""API создания, редактирования и прогресса ИПР (SPEC §8, issue #73)."""

from __future__ import annotations

from typing import cast

from django.db.models import QuerySet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.assessment.models import AssessmentCycle
from apps.audit.services import log_action
from apps.competencies.models import Competency
from apps.orgstructure.models import Employee
from apps.users.models import Role, User

from .models import DevAction, DevelopmentPlan, DevGoal
from .serializers import DevActionSerializer, DevelopmentPlanSerializer, DevGoalSerializer
from .services import generate_idp_from_zones, get_zones_from_assessment, transition_plan


def _current_employee(user: User) -> Employee | None:
    """Получить профиль текущего пользователя."""
    return Employee.objects.filter(user_id=user.pk).first()


def _is_editor(user: User) -> bool:
    """HR и руководитель могут редактировать ИПР в своей области доступа."""
    return user.has_any_role(Role.Code.HR.value, Role.Code.MANAGER.value)


def _assert_can_manage(user: User, target: Employee) -> None:
    """Проверить объектное право HR/руководителя на ИПР сотрудника."""
    if user.has_any_role(Role.Code.HR.value):
        return
    viewer = _current_employee(user)
    if (
        viewer is not None
        and user.has_any_role(Role.Code.MANAGER.value)
        and viewer.get_subordinates().filter(pk=target.pk).exists()
    ):
        return
    raise PermissionDenied("Изменять ИПР можно только сотрудникам своей команды.")


def _readable_plans(user: User) -> QuerySet[DevelopmentPlan]:
    """Ограничить чтение ИПР ролью и оргструктурой."""
    queryset = DevelopmentPlan.objects.select_related("employee").prefetch_related(
        "goals__source_cycle", "goals__actions"
    )
    if user.has_any_role(Role.Code.HR.value):
        return queryset
    viewer = _current_employee(user)
    if viewer is None:
        return queryset.none()
    if user.has_any_role(Role.Code.MANAGER.value):
        employee_ids = list(viewer.get_subordinates().values_list("id", flat=True))
        employee_ids.append(viewer.id)
        return queryset.filter(employee_id__in=employee_ids)
    return queryset.filter(employee=viewer)


class DevelopmentPlanViewSet(viewsets.ModelViewSet[DevelopmentPlan]):
    """Планы: чтение по RBAC, изменение — HR и руководителем команды."""

    serializer_class = DevelopmentPlanSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self) -> QuerySet[DevelopmentPlan]:
        """Вернуть доступные текущему пользователю планы."""
        return _readable_plans(cast(User, self.request.user))

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Не запускать валидацию тела до проверки роли редактора."""
        if not _is_editor(cast(User, request.user)):
            raise PermissionDenied("Создавать ИПР могут только HR и руководители.")
        return super().create(request, *args, **kwargs)

    def perform_create(  # type: ignore[override]
        self, serializer: DevelopmentPlanSerializer
    ) -> None:
        """Создать план в разрешённой области и записать аудит."""
        user = cast(User, self.request.user)
        target = serializer.validated_data["employee"]
        _assert_can_manage(user, target)
        plan = serializer.save()
        log_action(
            actor=user,
            action="idp.plan.create",
            target_type="idp.plan",
            target_id=str(plan.id),
            details={"employee_id": target.id},
        )

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Обновить поля и статус только через допустимый переход."""
        if not _is_editor(cast(User, request.user)):
            raise PermissionDenied("Изменять ИПР могут только HR и руководители.")
        partial = kwargs.pop("partial", False)
        plan = self.get_object()
        user = cast(User, request.user)
        _assert_can_manage(user, plan.employee)
        serializer = self.get_serializer(plan, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        target_status = serializer.validated_data.pop("status", None)
        if target_status is not None:
            try:
                transition_plan(plan, DevelopmentPlan.Status(target_status))
            except ValueError as error:
                raise ValidationError({"status": str(error)}) from error
        plan = serializer.save(employee=plan.employee)
        log_action(
            actor=user,
            action="idp.plan.update",
            target_type="idp.plan",
            target_id=str(plan.id),
            details={"status": plan.status},
        )
        return Response(self.get_serializer(plan).data)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Удалить план только в разрешённой области с аудитом."""
        if not _is_editor(cast(User, request.user)):
            raise PermissionDenied("Удалять ИПР могут только HR и руководители.")
        plan = self.get_object()
        user = cast(User, request.user)
        _assert_can_manage(user, plan.employee)
        plan_id = plan.id
        plan.delete()
        log_action(
            actor=user,
            action="idp.plan.delete",
            target_type="idp.plan",
            target_id=str(plan_id),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="auto-generate")
    def auto_generate(self, request: Request) -> Response:
        """Сформировать ИПР из безопасных агрегатов завершённой оценки."""
        user = cast(User, request.user)
        if not _is_editor(user):
            raise PermissionDenied("Формировать ИПР могут только HR и руководители.")
        employee_id = request.data.get("employee")
        cycle_id = request.data.get("cycle")
        if not isinstance(employee_id, int) or not isinstance(cycle_id, int):
            raise ValidationError("Укажите сотрудника и цикл оценки.")
        try:
            target = Employee.objects.get(pk=employee_id, is_active=True)
            cycle = AssessmentCycle.objects.get(pk=cycle_id)
        except (Employee.DoesNotExist, AssessmentCycle.DoesNotExist) as error:
            raise ValidationError("Сотрудник или цикл оценки не найден.") from error
        _assert_can_manage(user, target)
        zones = get_zones_from_assessment(employee=target, cycle=cycle)
        if not zones:
            raise ValidationError("В доступных агрегатах оценки нет зон развития.")
        plan = generate_idp_from_zones(employee=target, zones=zones, source_cycle=cycle)
        log_action(
            actor=user,
            action="idp.plan.auto_generate",
            target_type="idp.plan",
            target_id=str(plan.id),
            details={"employee_id": target.id, "cycle_id": cycle.id},
        )
        return Response(self.get_serializer(plan).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="options")
    def form_options(self, request: Request) -> Response:
        """Справочники формы с сотрудниками в области доступа редактора."""
        user = cast(User, request.user)
        if not _is_editor(user):
            raise PermissionDenied("Справочники редактирования доступны HR и руководителям.")
        if user.has_any_role(Role.Code.HR.value):
            employees = Employee.objects.filter(is_active=True)
        else:
            viewer = _current_employee(user)
            employees = viewer.get_subordinates() if viewer is not None else Employee.objects.none()
        cycles = AssessmentCycle.objects.filter(
            status__in=[
                AssessmentCycle.Status.AGGREGATED.value,
                AssessmentCycle.Status.CLOSED.value,
            ]
        )
        return Response(
            {
                "employees": [
                    {"id": employee.id, "name": employee.full_name} for employee in employees
                ],
                "cycles": [{"id": cycle.id, "name": cycle.name} for cycle in cycles],
                "competencies": [
                    {"id": competency.id, "name": competency.name}
                    for competency in Competency.objects.all()
                ],
            }
        )


class _ManagedChildViewSet:
    """Общие проверки изменения вложенных сущностей ИПР."""

    def _require_editor(self) -> User:
        request = cast(Request, self.__dict__["request"])
        user = cast(User, request.user)
        if not _is_editor(user):
            raise PermissionDenied("Изменять ИПР могут только HR и руководители.")
        return user


class DevGoalViewSet(_ManagedChildViewSet, viewsets.ModelViewSet[DevGoal]):
    """Ручное управление целями ИПР."""

    serializer_class = DevGoalSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self) -> QuerySet[DevGoal]:
        """Цели только доступных планов."""
        user = cast(User, self.request.user)
        return DevGoal.objects.filter(plan__in=_readable_plans(user)).select_related(
            "plan__employee", "source_cycle"
        )

    def perform_create(  # type: ignore[override]
        self, serializer: DevGoalSerializer
    ) -> None:
        """Добавить ручную цель с объектной проверкой и аудитом."""
        user = self._require_editor()
        plan = serializer.validated_data["plan"]
        _assert_can_manage(user, plan.employee)
        goal = serializer.save(source_cycle=None, source_current_level=None)
        self._audit(user, "create", goal)

    def perform_update(  # type: ignore[override]
        self, serializer: DevGoalSerializer
    ) -> None:
        """Изменить цель в разрешённом плане."""
        user = self._require_editor()
        goal = self.get_object()
        _assert_can_manage(user, goal.plan.employee)
        updated = serializer.save(plan=goal.plan)
        self._audit(user, "update", updated)

    def perform_destroy(self, instance: DevGoal) -> None:
        """Удалить цель в разрешённом плане."""
        user = self._require_editor()
        _assert_can_manage(user, instance.plan.employee)
        goal_id = instance.id
        instance.delete()
        log_action(
            actor=user,
            action="idp.goal.delete",
            target_type="idp.goal",
            target_id=str(goal_id),
        )

    @staticmethod
    def _audit(user: User, verb: str, goal: DevGoal) -> None:
        log_action(
            actor=user,
            action=f"idp.goal.{verb}",
            target_type="idp.goal",
            target_id=str(goal.id),
            details={"plan_id": goal.plan_id},
        )


class DevActionViewSet(_ManagedChildViewSet, viewsets.ModelViewSet[DevAction]):
    """Ручное управление действиями и их прогрессом."""

    serializer_class = DevActionSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self) -> QuerySet[DevAction]:
        """Действия только доступных планов."""
        user = cast(User, self.request.user)
        return DevAction.objects.filter(goal__plan__in=_readable_plans(user)).select_related(
            "goal__plan__employee"
        )

    def perform_create(  # type: ignore[override]
        self, serializer: DevActionSerializer
    ) -> None:
        """Добавить действие в разрешённую цель."""
        user = self._require_editor()
        goal = serializer.validated_data["goal"]
        _assert_can_manage(user, goal.plan.employee)
        item = serializer.save()
        self._audit(user, "create", item)

    def perform_update(  # type: ignore[override]
        self, serializer: DevActionSerializer
    ) -> None:
        """Изменить действие, не позволяя перенести его в чужую цель."""
        user = self._require_editor()
        item = self.get_object()
        _assert_can_manage(user, item.goal.plan.employee)
        updated = serializer.save(goal=item.goal)
        self._audit(user, "update", updated)

    def perform_destroy(self, instance: DevAction) -> None:
        """Удалить действие с объектной проверкой и аудитом."""
        user = self._require_editor()
        _assert_can_manage(user, instance.goal.plan.employee)
        item_id = instance.id
        instance.delete()
        log_action(
            actor=user,
            action="idp.action.delete",
            target_type="idp.action",
            target_id=str(item_id),
        )

    @staticmethod
    def _audit(user: User, verb: str, item: DevAction) -> None:
        log_action(
            actor=user,
            action=f"idp.action.{verb}",
            target_type="idp.action",
            target_id=str(item.id),
            details={"goal_id": item.goal_id, "progress_percent": item.progress_percent},
        )
