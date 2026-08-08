"""Сериалайзер портфолио (DRF, SPEC §6.2)."""

from __future__ import annotations

from rest_framework import serializers

from .models import PortfolioEntry


class PortfolioEntrySerializer(serializers.ModelSerializer[PortfolioEntry]):
    """Сериалайзер записи портфолио."""

    class Meta:
        """Метаданные сериалайзера портфолио."""

        model = PortfolioEntry
        fields = ["id", "employee", "type", "title", "description", "created_at"]
        read_only_fields = ["created_at"]
