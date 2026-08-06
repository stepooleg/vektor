"""Тесты моделей пользователей и RBAC (Test-First, AGENTS.md §3, SPEC §2).

Контракты:
- User: вход по email, роли, составные права, хеширование пароля (Argon2);
- Role/Permission: роли агрегируют разрешения, пользователь суммирует по ролям;
- has_permission/has_any_role — корректные булевы ответы.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.users.models import Permission, Role

UserModel = get_user_model()


@pytest.mark.django_db
def test_user_email_is_username_field() -> None:
    """Вход по email (SPEC §3.3), username отключён."""
    assert UserModel.USERNAME_FIELD == "email"
    assert UserModel.REQUIRED_FIELDS == []


@pytest.mark.django_db
def test_create_user_hashes_password_never_plaintext() -> None:
    """Пароль НЕ хранится в открытом виде (SPEC §12.2)."""
    user = UserModel.objects.create_user(email="alice@corp.local", password="Strong-Pwd-12345")

    # Пароль захеширован: не равен строке и содержит алгоритм-префикс.
    assert user.password != "Strong-Pwd-12345"
    assert user.check_password("Strong-Pwd-12345")
    # Формат Django-хеша: "<algo>$...". Алгоритм зависит от настроек окружения
    # (base → Argon2; test → MD5 для скорости). Главное — это НЕ открытый текст.
    assert "$" in user.password


def test_base_settings_prefer_argon2_hasher() -> None:
    """В прод-настройках (base) Argon2 — первый хешер паролей (SPEC §12.2).

    Независимо от тестового ускорения (MD5), конфигурация продакшена
    должна предпочитать Argon2.
    """
    from vektor.settings import base

    assert base.PASSWORD_HASHERS[0] == "django.contrib.auth.hashers.Argon2PasswordHasher"


@pytest.mark.django_db
def test_user_permissions_summed_across_composite_roles() -> None:
    """Составные роли: права пользователя — объединение прав всех его ролей (SPEC §2.2)."""
    role_manager = Role.objects.create(code=Role.Code.MANAGER.value, name="Руководитель")
    role_curator = Role.objects.create(code=Role.Code.METHODOLOGIST.value, name="Куратор")
    perm_manage_cycle = Permission.objects.create(code="assessment.cycle.manage", name="...")
    perm_edit_course = Permission.objects.create(code="lms.course.edit", name="...")
    role_manager.permissions.add(perm_manage_cycle)
    role_curator.permissions.add(perm_edit_course)

    user = UserModel.objects.create_user(email="bob@corp.local", password="Strong-Pwd-1")
    user.roles.add(role_manager, role_curator)

    perms = user.get_all_permission_codes()
    assert perms == {"assessment.cycle.manage", "lms.course.edit"}
    assert user.has_permission("assessment.cycle.manage")
    assert user.has_permission("lms.course.edit")
    assert not user.has_permission("assessment.cycle.delete")


@pytest.mark.django_db
def test_has_any_role_reflects_assigned_roles() -> None:
    """has_any_role возвращает True только для назначенных ролей."""
    hr = Role.objects.create(code=Role.Code.HR.value, name="HR")
    user = UserModel.objects.create_user(email="hr@corp.local", password="Strong-Pwd-1")
    user.roles.add(hr)

    assert user.has_any_role(Role.Code.HR.value)
    assert user.is_hr()
    assert not user.is_manager()
    assert not user.has_any_role(Role.Code.EMPLOYEE.value, Role.Code.MANAGER.value)


@pytest.mark.django_db
def test_user_without_roles_has_no_permissions() -> None:
    """Пользователь без ролей не имеет разрешений (минимум привилегий, SPEC §2.2)."""
    user = UserModel.objects.create_user(email="new@corp.local", password="Strong-Pwd-1")

    assert user.get_all_permission_codes() == set()
    assert not user.has_permission("any.thing")
    assert not user.has_any_role(Role.Code.EMPLOYEE.value)


@pytest.mark.django_db
def test_user_ad_account_optional_for_local_login() -> None:
    """Локальный пользователь (консультант) — без AD-учётки."""
    user = UserModel.objects.create_user(email="ext@consult.ru", password="Strong-Pwd-1")

    assert user.ad_account in (None, "")
    assert user.local_login_enabled is False
