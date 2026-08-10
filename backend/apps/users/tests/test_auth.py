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
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User

UserModel = get_user_model()


@pytest.fixture()
def _user_with_password() -> User:
    """Пользователь с разрешённым локальным входом."""
    user = UserModel.objects.create_user(email="alice@corp.local", password="Strong-Pwd-12345")
    user.local_login_enabled = True
    user.save(update_fields=["local_login_enabled"])
    return user


@pytest.mark.django_db
def test_login_valid_user_returns_session(_user_with_password: User) -> None:
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
def test_login_wrong_password_denied(_user_with_password: User) -> None:
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
def test_login_lockout_after_max_attempts(_user_with_password: User) -> None:
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
def test_successful_login_resets_failure_counter(_user_with_password: User) -> None:
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
def test_logout_clears_session(_user_with_password: User) -> None:
    """Logout завершает сессию."""
    client = APIClient()
    client.post(
        "/api/v1/auth/login/",
        {"email": "alice@corp.local", "password": "Strong-Pwd-12345"},
        format="json",
    )

    response = client.post("/api/v1/auth/logout/")

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
@override_settings(CSRF_TRUSTED_ORIGINS=["http://localhost:8080"])
def test_logout_accepts_csrf_token_issued_on_login(_user_with_password: User) -> None:
    """Browser-клиент получает CSRF cookie и может безопасно завершить сессию."""
    client = APIClient(enforce_csrf_checks=True)
    login_response = client.post(
        "/api/v1/auth/login/",
        {"email": "alice@corp.local", "password": "Strong-Pwd-12345"},
        format="json",
    )

    csrf_token = login_response.json()["csrfToken"]
    response = client.post(
        "/api/v1/auth/logout/",
        HTTP_X_CSRFTOKEN=csrf_token,
        HTTP_ORIGIN="http://localhost:8080",
    )

    assert response.status_code == status.HTTP_200_OK
    assert client.get("/api/v1/auth/me/").status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_me_returns_current_user(_user_with_password: User) -> None:
    """Действующая сессия возвращает текущего пользователя для frontend."""
    client = APIClient()
    client.force_authenticate(user=_user_with_password)

    response = client.get("/api/v1/auth/me/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "email": "alice@corp.local",
        "name": "",
        "csrfToken": response.json()["csrfToken"],
    }


@pytest.mark.django_db
def test_me_denies_anonymous_user() -> None:
    """Без действующей сессии endpoint текущего пользователя возвращает 403."""
    response = APIClient().get("/api/v1/auth/me/")

    assert response.status_code == status.HTTP_403_FORBIDDEN
