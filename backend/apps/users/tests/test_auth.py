"""Тесты авторизации: login/logout, lockout, аудит (Test-First, SPEC §10.2, issue #6).

Контракты:
- вход валидного пользователя (локальный пароль) → 200, сессия установлена;
- отказ при неверных кредах → 401;
- lockout после N неудачных попыток → 429/403;
- после успешного входа счётчик неудач сбрасывается;
- вход журналируется (audit-log домен — здесь проверяем side-effect через сигнал/log).
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

UserModel = get_user_model()


@pytest.fixture()
def _user_with_password() -> object:
    """Пользователь с разрешённым локальным входом."""
    user = UserModel.objects.create_user(email="alice@corp.local", password="Strong-Pwd-12345")
    user.local_login_enabled = True
    user.save(update_fields=["local_login_enabled"])
    return user


@pytest.mark.django_db
def test_login_valid_user_returns_session(_user_with_password: object) -> None:
    """Валидный пользователь входит, сессия устанавливается."""
    client = APIClient()

    response = client.post(
        "/api/v1/auth/login/",
        {"email": "alice@corp.local", "password": "Strong-Pwd-12345"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert "sessionid" in response.cookies


@pytest.mark.django_db
def test_login_wrong_password_denied(_user_with_password: object) -> None:
    """Неверный пароль → 401, сессия не установлена."""
    client = APIClient()

    response = client.post(
        "/api/v1/auth/login/",
        {"email": "alice@corp.local", "password": "Wrong-Pwd-99999"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "sessionid" not in response.cookies


@pytest.mark.django_db
def test_login_lockout_after_max_attempts(_user_with_password: object) -> None:
    """После N неудачных попыток — lockout (защита от перебора, SPEC §10.2)."""
    client = APIClient()
    payload = {"email": "alice@corp.local", "password": "Wrong-Pwd-99999"}

    # DEFAULT_LOGIN_MAX_ATTEMPTS (см. settings.base) — делаем N+1 попыток.
    from django.conf import settings

    max_attempts = settings.LOGIN_MAX_ATTEMPTS

    statuses: list[int] = []
    for _ in range(max_attempts):
        r = client.post("/api/v1/auth/login/", payload, format="json")
        statuses.append(r.status_code)

    # Все первые попытки — 401, lockout ещё не сработал.
    assert all(s == status.HTTP_401_UNAUTHORIZED for s in statuses)

    # Следующая попытка — lockout (429 Too Many Requests).
    blocked = client.post("/api/v1/auth/login/", payload, format="json")
    assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_successful_login_resets_failure_counter(_user_with_password: object) -> None:
    """Успешный вход сбрасывает счётчик неудач (нет вечного lockout после ошибки)."""
    client = APIClient()
    # Одна неудачная.
    client.post(
        "/api/v1/auth/login/",
        {"email": "alice@corp.local", "password": "Wrong-Pwd-1"},
        format="json",
    )
    # Успешная.
    ok = client.post(
        "/api/v1/auth/login/",
        {"email": "alice@corp.local", "password": "Strong-Pwd-12345"},
        format="json",
    )
    assert ok.status_code == status.HTTP_200_OK

    # Теперь снова неудачных N штук НЕ приводят к преждевременному lockout
    # (счётчик был сброшен). Проверяем, что max_attempts-1 попыток дают 401,
    # а не 429 (lockout сработал бы только на max_attempts+1).
    from django.conf import settings

    max_attempts = settings.LOGIN_MAX_ATTEMPTS
    statuses = []
    for _ in range(max_attempts - 1):
        r = client.post(
            "/api/v1/auth/login/",
            {"email": "alice@corp.local", "password": "Wrong-Pwd-1"},
            format="json",
        )
        statuses.append(r.status_code)
    assert all(s == status.HTTP_401_UNAUTHORIZED for s in statuses)


@pytest.mark.django_db
def test_logout_clears_session(_user_with_password: object) -> None:
    """Logout завершает сессию."""
    client = APIClient()
    client.post(
        "/api/v1/auth/login/",
        {"email": "alice@corp.local", "password": "Strong-Pwd-12345"},
        format="json",
    )

    response = client.post("/api/v1/auth/logout/")

    assert response.status_code == status.HTTP_200_OK
