"""Корневые представления проекта Vektor.

Health-check — единственный инфра-эндпоинт на старте; используется для
проверки живости приложения в Docker/CI/Nginx (issue #1, #3).
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from vektor import API_VERSION, __version__

# Содержимое ответа health-check — детерминированный, безопасный JSON.
_HEALTH_OK: dict[str, Any] = {
    "status": "ok",
    "version": __version__,
    "api_version": API_VERSION,
}


class HealthView(APIView):
    """``GET /api/v1/health/`` — диагностика живости сервиса.

    Возвращает версию приложения и API. Не раскрывает чувствительные
    данные (без конфигурации БД, без метрик) — комплаенс (SPEC §12).
    """

    # Health-check доступен без аутентификации: используется для liveness-проб.
    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []
    swagger_schema = True

    @extend_schema(
        summary="Проверка живости сервиса",
        description="Возвращает статус приложения и версию API.",
        tags=["system"],
    )
    def get(self, request: Request) -> Response:
        """Вернуть статус ``ok`` с метаданными версии."""
        return Response(_HEALTH_OK, status=status.HTTP_200_OK)
