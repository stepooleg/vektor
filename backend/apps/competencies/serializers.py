"""Сериалайзеры компетенций (DRF, SPEC §4)."""

from __future__ import annotations

from rest_framework import serializers

from .models import Competency, CompetencyFramework, CompetencyGroup, Indicator, Scale


class ScaleSerializer(serializers.ModelSerializer[Scale]):
    """Сериалайзер шкалы оценки."""

    class Meta:
        """Метаданные сериалайзера шкалы."""

        model = Scale
        fields = ["id", "name", "min_value", "max_value"]


class IndicatorSerializer(serializers.ModelSerializer[Indicator]):
    """Сериалайзер поведенческого индикатора."""

    class Meta:
        """Метаданные сериалайзера индикатора."""

        model = Indicator
        fields = ["id", "competency", "level", "description"]


class CompetencySerializer(serializers.ModelSerializer[Competency]):
    """Сериалайзер компетенции."""

    class Meta:
        """Метаданные сериалайзера компетенции."""

        model = Competency
        fields = ["id", "name", "description", "group", "scale"]


class CompetencyGroupSerializer(serializers.ModelSerializer[CompetencyGroup]):
    """Сериалайзер группы компетенций."""

    class Meta:
        """Метаданные сериалайзера группы."""

        model = CompetencyGroup
        fields = ["id", "name", "description"]


class CompetencyFrameworkSerializer(serializers.ModelSerializer[CompetencyFramework]):
    """Сериалайзер модели компетенций (framework)."""

    class Meta:
        """Метаданные сериалайзера framework."""

        model = CompetencyFramework
        fields = ["id", "name", "scope", "competencies", "position", "employee"]
