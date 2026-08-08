"""API уведомлений: подписка на push и публичный VAPID-ключ (SPEC §10.4, issue #24).

- GET /api/v1/notifications/vapid-public/ — публичный VAPID-ключ для браузера;
- POST /api/v1/notifications/subscribe/ — создать push-подписку;
- DELETE /api/v1/notifications/unsubscribe/<endpoint>/ — деактивировать подписку.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PushSubscription


class VapidPublicKeyView(APIView):
    """Публичный VAPID-ключ для подписки на push в браузере."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        """Вернуть публичный VAPID-ключ."""
        return Response({"public_key": settings.VAPID_PUBLIC_KEY})


class SubscribeView(APIView):
    """Создать push-подписку (SPEC §10.4 — согласие пользователя)."""

    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        """Создать подписку из данных Service Worker PushSubscription."""
        endpoint = request.data.get("endpoint")
        keys = request.data.get("keys", {})
        p256dh = keys.get("p256dh")
        auth = keys.get("auth")
        if not endpoint or not p256dh or not auth:
            return Response(
                {"detail": "Требуются endpoint, keys.p256dh, keys.auth."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user_id = request.user.pk
        assert user_id is not None  # IsAuthenticated гарантирует наличие pk
        sub, _ = PushSubscription.objects.update_or_create(
            user_id=user_id,
            endpoint=endpoint,
            defaults={"p256dh": p256dh, "auth": auth, "is_active": True},
        )
        return Response({"id": sub.id}, status=status.HTTP_201_CREATED)


class UnsubscribeView(APIView):
    """Деактивировать push-подписку (отписка)."""

    permission_classes = (IsAuthenticated,)

    def delete(self, request: Request, endpoint: str) -> Response:
        """Деактивировать подписку по endpoint."""
        user_id = request.user.pk
        assert user_id is not None  # IsAuthenticated гарантирует наличие pk
        updated = PushSubscription.objects.filter(user_id=user_id, endpoint=endpoint).update(
            is_active=False
        )
        if updated == 0:
            return Response({"detail": "Подписка не найдена."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"detail": "Отписка выполнена."})
