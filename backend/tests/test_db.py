"""Тест подключения к тестовой БД: запись/чтение проходят.

issue #1 требует, чтобы подключение к тестовой БД работало. Используем
встроенную модель User (contrib.auth) — она есть в каркасе без своих моделей.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_database_can_persist_object() -> None:
    """Создание и чтение записи работает (БД подключена)."""
    user_model = get_user_model()
    user = user_model.objects.create_user(email="alice@corp.local", password="strong-pwd-12345")

    fetched = user_model.objects.get(pk=user.pk)
    assert fetched.email == "alice@corp.local"
    # Пароль захеширован (не хранится в открытом виде).
    assert fetched.password != "strong-pwd-12345"
    assert fetched.check_password("strong-pwd-12345")
