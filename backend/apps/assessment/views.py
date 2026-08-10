"""API циклов оценки (DRF, SPEC §5, §14.2, issue #17).

Права:
- список/чтение циклов — всем аутентифицированным;
- создание/изменение цикла — HR (SPEC §5.2);
- результаты цикла — агрегаты (без сырых данных), с учётом порога анонимности
  (SPEC §6.3); доступ: HR/руководитель участника/сам участник.
"""

from __future__ import annotations

from typing import cast

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.competencies.models import CompetencyFramework
from apps.users.models import User
from apps.users.permissions import IsHR, IsManager

from .models import AssessmentCycle, Participant, ReviewerAssignment
from .serializers import (
    AssessmentCycleSerializer,
    AssignmentSubmitSerializer,
    ParticipantSerializer,
    ReviewerAssignmentSerializer,
)
from .services import (
    CycleTransitionError,
    aggregate_cycle,
    eligible_participants_for_user,
    transition_cycle,
)


class AssessmentCycleViewSet(ModelViewSet[AssessmentCycle]):
    """CRUD циклов оценки + эндпоинт агрегированных результатов."""

    queryset = AssessmentCycle.objects.all().order_by("-created_at")
    serializer_class = AssessmentCycleSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """HR видит все циклы, руководитель — только созданные им."""
        user = cast(User, self.request.user)
        if user.has_any_role("hr"):
            return self.queryset
        if user.has_any_role("manager"):
            return self.queryset.filter(created_by=user)
        return self.queryset.none()

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Чтение — аутентифицированным; запись — HR."""
        if self.action in {"create", "setup_options", "start"}:
            return [(IsHR | IsManager)()]
        if self.action in {"update", "partial_update", "destroy"}:
            return [IsHR()]
        if self.action == "results":
            return [(IsHR | IsManager)()]
        return [IsAuthenticated()]

    @action(detail=False, methods=["get"], url_path="setup-options")
    def setup_options(self, request: Request) -> Response:
        """Вернуть модели и только доступных пользователю участников мастера."""
        user = cast(User, request.user)
        participants = eligible_participants_for_user(user).select_related("department")
        frameworks = CompetencyFramework.objects.order_by("name")
        return Response(
            {
                "frameworks": [{"id": item.id, "name": item.name} for item in frameworks],
                "participants": [
                    {
                        "id": employee.id,
                        "full_name": employee.full_name,
                        "department": employee.department.name,
                    }
                    for employee in participants
                ],
            }
        )

    @action(detail=True, methods=["post"])
    def start(self, request: Request, pk: int) -> Response:
        """Запустить подготовленный цикл его автором или HR."""
        cycle = self.get_object()
        user = cast(User, request.user)
        if not user.has_any_role("hr") and cycle.created_by_id != user.id:
            raise PermissionDenied("Запустить цикл может только его автор или HR.")
        try:
            transition_cycle(cycle, AssessmentCycle.Status.IN_PROGRESS)
        except CycleTransitionError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(AssessmentCycleSerializer(cycle).data)

    @extend_schema(
        summary="Агрегированные результаты цикла",
        description=(
            "Возвращает средние оценки по группам оценщиков (руководитель/"
            "коллеги/подчинённые/самооценка). Сырые ответы НЕ возвращаются. "
            "Группы ниже порога анонимности помечаются hidden_by_threshold (SPEC §6.3)."
        ),
        responses={200: dict, 400: dict},
        tags=["assessment"],
    )
    @action(detail=True, methods=["get"], url_path="results")
    def results(self, request: Request, pk: int) -> Response:
        """Вернуть агрегированные результаты цикла (только агрегаты)."""
        cycle = self.get_object()
        user = cast(User, request.user)
        if not user.has_any_role("hr") and cycle.created_by_id != user.id:
            raise PermissionDenied("Результаты доступны HR или руководителю — автору цикла.")
        aggregate = aggregate_cycle(cycle)
        # Аудит доступа к результатам цикла (SPEC §12.3).
        from apps.audit.services import log_action

        actor = user
        log_action(
            actor=actor,
            action="assessment.result.view",
            target_type="assessment.cycle",
            target_id=str(cycle.id),
            details={"cycle_name": cycle.name},
        )
        return Response(
            {
                "cycle_id": aggregate.cycle_id,
                "groups": [
                    {
                        "group": g.group,
                        "participants_count": g.participants_count,
                        "mean_score": g.mean_score,
                        "hidden_by_threshold": g.hidden_by_threshold,
                    }
                    for g in aggregate.groups
                ],
            }
        )


class ParticipantViewSet(ModelViewSet[Participant]):
    """CRUD участников цикла (назначение оцениваемых)."""

    queryset = Participant.objects.select_related("employee", "cycle").all()
    serializer_class = ParticipantSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Не раскрывать сотруднику состав чужих циклов."""
        user = cast(User, self.request.user)
        if user.has_any_role("hr"):
            return self.queryset
        if user.has_any_role("manager"):
            return self.queryset.filter(cycle__created_by=user)
        return self.queryset.none()

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Чтение — аутентифицированным; запись — HR."""
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsHR()]
        return [IsAuthenticated()]


class ReviewerAssignmentViewSet(ReadOnlyModelViewSet[ReviewerAssignment]):
    """Задания текущего оценщика и безопасная одноразовая отправка опросника."""

    serializer_class = ReviewerAssignmentSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Никогда не раскрывать задания других оценщиков."""
        user = cast(User, self.request.user)
        return (
            ReviewerAssignment.objects.filter(reviewer__user=user)
            .select_related(
                "cycle__framework",
                "participant__employee",
            )
            .prefetch_related("cycle__framework__competencies__scale")
            .order_by("completed", "cycle__deadline", "id")
        )

    @action(detail=True, methods=["post"])
    def submit(self, request: Request, pk: int) -> Response:
        """Сохранить ответы без возврата сырых данных клиенту."""
        assignment = self.get_object()
        user = cast(User, request.user)
        serializer = AssignmentSubmitSerializer(
            data=request.data,
            context={"assignment": assignment},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        from apps.audit.services import log_action

        log_action(
            actor=user,
            action="assessment.assignment.submit",
            target_type="assessment.assignment",
            target_id=str(assignment.id),
            details={"cycle_id": assignment.cycle_id},
        )
        return Response({"completed": True}, status=status.HTTP_200_OK)
