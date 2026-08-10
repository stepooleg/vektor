"""API авторизации: login/logout с защитой от перебора (SPEC §10.2, issue #6).

Вход по email + пароль (запасной механизм при недоступности AD или для
консультантов). SSO (SAML/OIDC/LDAP) — отдельный расширяемый бэкенд (TODO #6,
SPEC §17 п.2), активируется флагом ``AUTH_LDAP_ENABLED``.

Защита от перебора: счётчик неудачных попыток в кеше; при превышении
``LOGIN_MAX_ATTEMPTS`` — блокировка на ``LOGIN_LOCKOUT_SECONDS``.
Все попытки входа журналируются (audit-log — отдельный домен; здесь — лог).
"""

from __future__ import annotations

import logging
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orgstructure.models import Employee

from .models import User

logger = logging.getLogger(__name__)

# Ключ кеша для счётчика неудачных попыток по email.
_CACHE_KEY_PREFIX = "login-failures:"


def _failures_key(email: str) -> str:
    """Ключ кеша счётчика неудачных попыток для email."""
    return f"{_CACHE_KEY_PREFIX}{email.lower()}"


def _record_failure(email: str) -> int:
    """Увеличить счётчик неудач, вернуть новое значение."""
    key = _failures_key(email)
    count: int = int(cache.get(key, 0)) + 1
    cache.set(key, count, timeout=settings.LOGIN_LOCKOUT_SECONDS)
    return count


def _reset_failures(email: str) -> None:
    """Сбросить счётчик неудач (после успешного входа)."""
    cache.delete(_failures_key(email))


def _is_locked_out(email: str) -> bool:
    """Превышен ли лимит неудачных попыток."""
    count: int = cache.get(_failures_key(email), 0)
    return count >= settings.LOGIN_MAX_ATTEMPTS


def _user_payload(user: User) -> dict[str, object]:
    """Безопасный frontend-контекст без ПДн оргструктуры и внутренних прав."""
    employee_id = Employee.objects.filter(user_id=user.pk).values_list("id", flat=True).first()
    roles = list(user.roles.order_by("code").values_list("code", flat=True))
    return {
        "email": user.email,
        "name": user.get_full_name(),
        "employee_id": employee_id,
        "roles": roles,
    }


class LoginView(APIView):
    """``POST /api/v1/auth/login/`` — вход по email + пароль (SPEC §10.2)."""

    permission_classes = (AllowAny,)
    authentication_classes: list[Any] = []

    def post(self, request: Request) -> Response:
        """Аутентифицировать пользователя и установить сессию."""
        email = (request.data.get("email") or "").strip()
        password = request.data.get("password") or ""

        if not email or not password:
            return Response(
                {"detail": "Email и пароль обязательны."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if _is_locked_out(email):
            logger.warning("Login locked out: %s", email)
            return Response(
                {"detail": "Слишком много попыток. Попробуйте позже."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        authenticated_user = authenticate(request, username=email, password=password)
        if authenticated_user is None or not authenticated_user.is_active:
            _record_failure(email)
            logger.info("Login failed: %s", email)
            return Response(
                {"detail": "Неверный email или пароль."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Успешный вход: сброс счётчика, старт сессии, аудит.
        user = authenticated_user
        _reset_failures(email)
        login(request, user)
        logger.info("Login success: %s", email)
        return Response(
            {
                "detail": "Вход выполнен.",
                "user": _user_payload(user),
                "csrfToken": get_token(request),
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """``POST /api/v1/auth/logout/`` — завершение сессии."""

    def post(self, request: Request) -> Response:
        """Завершить сессию текущего пользователя."""
        if request.user.is_authenticated:
            logout(request)
        return Response({"detail": "Сессия завершена."}, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    """``GET /api/v1/auth/me/`` — текущий пользователь серверной сессии."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        """Вернуть безопасный минимум данных текущего пользователя."""
        user = cast(User, request.user)
        return Response(
            {**_user_payload(user), "csrfToken": get_token(request)},
            status=status.HTTP_200_OK,
        )
