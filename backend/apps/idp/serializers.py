"""Сериалайзеры редактируемого ИПР (SPEC §8, issue #73)."""

from __future__ import annotations

from rest_framework import serializers

from .models import DevAction, DevelopmentPlan, DevGoal


class DevActionSerializer(serializers.ModelSerializer[DevAction]):
    """Действие в составе цели развития."""

    class Meta:
        model = DevAction
        fields = [
            "id",
            "goal",
            "type",
            "title",
            "status",
            "progress_percent",
            "due_date",
            "course",
            "mentor",
        ]

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Синхронизировать статус действия и числовой прогресс."""
        status_value = attrs.get(
            "status", getattr(self.instance, "status", DevAction.Status.PLANNED)
        )
        progress = attrs.get("progress_percent", getattr(self.instance, "progress_percent", 0))
        if status_value == DevAction.Status.COMPLETED.value:
            attrs["progress_percent"] = 100
        elif progress == 100:
            attrs["status"] = DevAction.Status.COMPLETED.value
        elif (
            isinstance(progress, int)
            and progress > 0
            and status_value == DevAction.Status.PLANNED.value
        ):
            attrs["status"] = DevAction.Status.IN_PROGRESS.value
        return attrs


class DevGoalSerializer(serializers.ModelSerializer[DevGoal]):
    """Цель ИПР с вложенными действиями."""

    actions = DevActionSerializer(many=True, read_only=True)
    source = serializers.SerializerMethodField()  # type: ignore[assignment]

    class Meta:
        model = DevGoal
        fields = [
            "id",
            "plan",
            "title",
            "description",
            "competency",
            "target_level",
            "source",
            "actions",
        ]

    def get_source(self, obj: DevGoal) -> dict[str, object]:
        """Объяснить происхождение автоподобранной цели без сырых оценок."""
        cycle = obj.source_cycle
        if cycle is None:
            return {"type": "manual"}
        return {
            "type": "assessment",
            "cycle_id": obj.source_cycle_id,
            "cycle_name": cycle.name,
            "current_level": float(obj.source_current_level or 0),
            "expected_level": obj.target_level,
        }


class DevelopmentPlanSerializer(serializers.ModelSerializer[DevelopmentPlan]):
    """ИПР с вложенными целями и действиями."""

    goals = DevGoalSerializer(many=True, read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    progress_percent = serializers.SerializerMethodField()

    class Meta:
        model = DevelopmentPlan
        fields = [
            "id",
            "employee",
            "employee_name",
            "title",
            "status",
            "progress_percent",
            "goals",
        ]

    def get_progress_percent(self, obj: DevelopmentPlan) -> int:
        """Средний прогресс всех действий плана."""
        progress = [
            action.progress_percent for goal in obj.goals.all() for action in goal.actions.all()
        ]
        return round(sum(progress) / len(progress)) if progress else 0
