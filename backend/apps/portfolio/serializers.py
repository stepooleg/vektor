"""Сериалайзер портфолио (DRF, SPEC §6.2)."""

from __future__ import annotations

from rest_framework import serializers

from apps.orgstructure.models import Employee

from .models import PortfolioEntry


class PortfolioEntrySerializer(serializers.ModelSerializer[PortfolioEntry]):
    """Сериалайзер записи портфолио."""

    employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(is_active=True),
        write_only=True,
        required=False,
    )
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        """Метаданные сериалайзера портфолио."""

        model = PortfolioEntry
        fields = [
            "id",
            "employee",
            "employee_name",
            "type",
            "title",
            "description",
            "created_at",
        ]
        read_only_fields = ["employee_name", "created_at"]

    def validate_type(self, value: str) -> str:
        """Разрешить вручную только достижения и проекты."""
        manual_types = {
            PortfolioEntry.Type.ACHIEVEMENT.value,
            PortfolioEntry.Type.PROJECT.value,
        }
        if value not in manual_types:
            raise serializers.ValidationError("Этот тип записи создаётся автоматически.")
        return value
