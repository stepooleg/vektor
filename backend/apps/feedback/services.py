"""Сервисы обратной связи (SPEC §6.1, §6.3, issue #28).

- ``safe_praise_sender``: безопасное отображение отправителя (скрытие анонима);
- ``get_public_feed``: лента публичных благодарностей;
- ``mark_request_answered``: завершение запроса ОС.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone

from .models import Praise

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.orgstructure.models import Employee

    from .models import FeedbackRequest


def safe_praise_sender(praise: Praise) -> Employee | None:
    """Вернуть отправителя благодарности или None, если анонимно (SPEC §6.3).

    UI/API должны использовать эту функцию для отображения отправителя,
    чтобы не деанонимизировать анонимные благодарности.
    """
    if praise.is_anonymous:
        return None
    return praise.sender


def get_public_feed() -> QuerySet[Praise]:
    """Лента публичных благодарностей (SPEC §6.1)."""
    return Praise.objects.filter(is_public=True).select_related("recipient", "sender")


def mark_request_answered(request: FeedbackRequest) -> FeedbackRequest:
    """Отметить запрос ОС как отвеченный (SPEC §6.1)."""
    request.status = request.Status.ANSWERED.value
    request.answered_at = timezone.now()
    request.save(update_fields=["status", "answered_at"])
    return request
