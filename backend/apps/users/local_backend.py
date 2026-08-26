"""Запасной локальный backend авторизации (SPEC §10.2)."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest

from .models import User


class LocalModelBackend(ModelBackend):
    """Разрешает пароль только пользователям с явным local fallback."""

    def user_can_authenticate(
        self,
        user: AbstractBaseUser | AnonymousUser | None,
    ) -> bool:
        """Проверить активность и явное разрешение локального входа."""
        return (
            isinstance(user, User)
            and settings.LOCAL_LOGIN_ENABLED
            and user.local_login_enabled
            and super().user_can_authenticate(user)
        )

    def authenticate(
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> User | None:
        """Аутентифицировать локальный пароль через стандартный Django backend."""
        user = super().authenticate(
            request,
            username=username,
            password=password,
            **kwargs,
        )
        return user if isinstance(user, User) else None
