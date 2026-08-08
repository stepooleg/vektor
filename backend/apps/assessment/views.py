"""API циклов оценки (DRF, SPEC §5, §14.2, issue #17).

Права:
- список/чтение циклов — всем аутентифицированным;
- создание/изменение цикла — HR (SPEC §5.2);
- результаты цикла — агрегаты (без сырых данных), с учётом порога анонимности
  (SPEC §6.3); доступ: HR/руководитель участника/сам участник.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.users.permissions import IsHR

from .models import AssessmentCycle, Participant
from .serializers import AssessmentCycleSerializer, ParticipantSerializer
from .services import aggregate_cycle


class AssessmentCycleViewSet(ModelViewSet[AssessmentCycle]):
    """CRUD циклов оценки + эндпоинт агрегированных результатов."""

    queryset = AssessmentCycle.objects.all().order_by("-created_at")
    serializer_class = AssessmentCycleSerializer

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Чтение — аутентифицированным; запись — HR."""
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsHR()]
        return [IsAuthenticated()]

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
        aggregate = aggregate_cycle(cycle)
        # Аудит доступа к результатам цикла (SPEC §12.3).
        from apps.audit.services import log_action

        actor = request.user if request.user.is_authenticated else None
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

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Чтение — аутентифицированным; запись — HR."""
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsHR()]
        return [IsAuthenticated()]
