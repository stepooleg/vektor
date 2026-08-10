"""Read-only сериалайзеры ИПР (SPEC §8, issue #63)."""

from __future__ import annotations

from rest_framework import serializers

from .models import DevAction, DevelopmentPlan, DevGoal


class DevActionSerializer(serializers.ModelSerializer[DevAction]):
    """Действие в составе цели развития."""

    class Meta:
        model = DevAction
        fields = ["id", "type", "title", "status", "due_date", "course", "mentor"]


class DevGoalSerializer(serializers.ModelSerializer[DevGoal]):
    """Цель ИПР с вложенными действиями."""

    actions = DevActionSerializer(many=True, read_only=True)

    class Meta:
        model = DevGoal
        fields = ["id", "title", "competency", "target_level", "actions"]


class DevelopmentPlanSerializer(serializers.ModelSerializer[DevelopmentPlan]):
    """ИПР с вложенными целями и действиями."""

    goals = DevGoalSerializer(many=True, read_only=True)

    class Meta:
        model = DevelopmentPlan
        fields = ["id", "title", "status", "goals"]
