"""Сериалайзеры обратной связи (DRF, SPEC §6.1)."""

from __future__ import annotations

from rest_framework import serializers

from .models import FeedbackRequest, Praise


class PraiseSerializer(serializers.ModelSerializer[Praise]):
    """Сериалайзер благодарности."""

    sender_name = serializers.SerializerMethodField()
    recipient_name = serializers.CharField(source="recipient.full_name", read_only=True)

    class Meta:
        """Метаданные сериалайзера благодарности."""

        model = Praise
        fields = [
            "id",
            "recipient",
            "recipient_name",
            "sender",
            "sender_name",
            "message",
            "is_public",
            "is_anonymous",
            "created_at",
        ]
        read_only_fields = ["sender", "created_at", "sender_name", "recipient_name"]

    def get_sender_name(self, obj: Praise) -> str | None:
        """Безопасное отображение отправителя (скрытие анонима, §6.3)."""
        from .services import safe_praise_sender

        sender = safe_praise_sender(obj)
        return sender.full_name if sender else None


class FeedbackRequestSerializer(serializers.ModelSerializer[FeedbackRequest]):
    """Сериалайзер запроса обратной связи."""

    requester_name = serializers.CharField(source="requester.full_name", read_only=True)
    recipient_name = serializers.CharField(source="recipient.full_name", read_only=True)

    class Meta:
        """Метаданные сериалайзера запроса ОС."""

        model = FeedbackRequest
        fields = [
            "id",
            "requester",
            "requester_name",
            "recipient",
            "recipient_name",
            "message",
            "status",
            "created_at",
        ]
        read_only_fields = ["requester", "status", "created_at", "requester_name", "recipient_name"]
