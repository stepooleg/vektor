"""Сериалайзеры циклов оценки (DRF, SPEC §5, §14.2)."""

from __future__ import annotations

from rest_framework import serializers

from .models import AssessmentCycle, Participant


class AssessmentCycleSerializer(serializers.ModelSerializer[AssessmentCycle]):
    """Сериалайзер цикла оценки."""

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
        ]
        read_only_fields = ["status", "created_at"]


class ParticipantSerializer(serializers.ModelSerializer[Participant]):
    """Сериалайзер участника цикла."""

    employee_full_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        """Метаданные сериалайзера участника."""

        model = Participant
        fields = ["id", "cycle", "employee", "employee_full_name"]
