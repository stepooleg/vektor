"""Сериалайзеры циклов оценки (DRF, SPEC §5, §14.2)."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from rest_framework import serializers

from apps.competencies.models import CompetencyFramework
from apps.users.models import User

from .models import AssessmentCycle, Participant, ReviewerAssignment
from .services import (
    AssignmentResponseInput,
    CycleCreationData,
    CycleTransitionError,
    create_cycle_with_participants,
    submit_assignment,
)


class AssessmentCycleSerializer(serializers.ModelSerializer[AssessmentCycle]):
    """Сериалайзер цикла оценки."""

    participant_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), write_only=True, required=False
    )
    participants_count = serializers.IntegerField(source="participants.count", read_only=True)

    class Meta:
        """Метаданные сериалайзера цикла."""

        model = AssessmentCycle
        fields = [
            "id",
            "name",
            "framework",
            "status",
            "anonymity_threshold",
            "start_date",
            "deadline",
            "created_at",
            "participant_ids",
            "participants_count",
        ]
        read_only_fields = ["status", "created_at"]

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Проверить сроки и полноту данных мастера."""
        start_date = cast(date | None, attrs.get("start_date"))
        deadline = cast(date | None, attrs.get("deadline"))
        if start_date is not None and deadline is not None and deadline < start_date:
            raise serializers.ValidationError({"deadline": "Дедлайн не может быть раньше старта."})
        participant_ids = attrs.get("participant_ids")
        if participant_ids is not None and not participant_ids:
            raise serializers.ValidationError(
                {"participant_ids": "Выберите хотя бы одного участника."}
            )
        return attrs

    def create(self, validated_data: dict[str, object]) -> AssessmentCycle:
        """Создать цикл через доменный сервис и зафиксировать автора."""
        participant_ids = cast(list[int], validated_data.pop("participant_ids", []))
        request = self.context["request"]
        creation_data = CycleCreationData(
            name=cast(str, validated_data["name"]),
            framework=cast(
                CompetencyFramework | None,
                validated_data.get("framework"),
            ),
            anonymity_threshold=cast(int, validated_data.get("anonymity_threshold", 3)),
            start_date=cast(date | None, validated_data.get("start_date")),
            deadline=cast(date | None, validated_data.get("deadline")),
        )
        try:
            return create_cycle_with_participants(
                data=creation_data,
                creator=cast(User, request.user),
                participant_ids=participant_ids,
            )
        except CycleTransitionError as exc:
            raise serializers.ValidationError({"participant_ids": str(exc)}) from exc


class ParticipantSerializer(serializers.ModelSerializer[Participant]):
    """Сериалайзер участника цикла."""

    employee_full_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        """Метаданные сериалайзера участника."""

        model = Participant
        fields = ["id", "cycle", "employee", "employee_full_name"]


class ReviewerAssignmentSerializer(serializers.ModelSerializer[ReviewerAssignment]):
    """Безопасное задание оценщика без ранее сохранённых сырых ответов."""

    cycle_name = serializers.CharField(source="cycle.name", read_only=True)
    deadline = serializers.DateField(source="cycle.deadline", read_only=True)
    participant_name = serializers.CharField(
        source="participant.employee.full_name", read_only=True
    )
    competencies = serializers.SerializerMethodField()

    class Meta:
        """Поля карточки опросника."""

        model = ReviewerAssignment
        fields = [
            "id",
            "cycle",
            "cycle_name",
            "deadline",
            "participant_name",
            "group",
            "completed",
            "competencies",
        ]

    def get_competencies(self, assignment: ReviewerAssignment) -> list[dict[str, object]]:
        """Вернуть только структуру опросника и границы шкалы."""
        framework = assignment.cycle.framework
        if framework is None:
            return []
        return [
            {
                "id": competency.id,
                "name": competency.name,
                "description": competency.description,
                "min_value": competency.scale.min_value,
                "max_value": competency.scale.max_value,
            }
            for competency in framework.competencies.select_related("scale").all()
        ]


class AssignmentResponseSerializer(serializers.Serializer[dict[str, object]]):
    """Один ответ по компетенции."""

    competency_id = serializers.IntegerField(min_value=1)
    score = serializers.IntegerField()
    comment = serializers.CharField(required=False, allow_blank=True, max_length=5000)


class AssignmentSubmitSerializer(serializers.Serializer[dict[str, object]]):
    """Полная одноразовая отправка опросника."""

    responses = AssignmentResponseSerializer(many=True, allow_empty=False)
    general_comment = serializers.CharField(required=False, allow_blank=True, max_length=5000)

    def save(self, **kwargs: Any) -> dict[str, object]:
        """Передать проверенные ответы доменному сервису."""
        assignment = self.context["assignment"]
        try:
            submit_assignment(
                assignment,
                responses=cast(list[AssignmentResponseInput], self.validated_data["responses"]),
                general_comment=cast(str, self.validated_data.get("general_comment", "")),
            )
        except CycleTransitionError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc
        return cast(dict[str, object], self.validated_data)
