"""Тесты API компетенций с RBAC (Test-First, SPEC §4, §2.1, issue #9).

Контракты:
- чтение доступно всем аутентифицированным;
- создание/изменение — только HR/Методолог;
- сотрудник получает 403 на запись.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.competencies.models import CompetencyGroup, Scale
from apps.users.models import Role, User

UserModel = get_user_model()


def _user_with_role(email: str, role_code: str) -> User:
    """Создать пользователя с указанной ролью."""
    user = UserModel.objects.create_user(email=email, password="Strong-Pwd-1")
    role = Role.objects.create(code=role_code, name=role_code)
    user.roles.add(role)
    return user


@pytest.fixture()
def _scale() -> Scale:
    """Шкала для тестов API."""
    return Scale.objects.create(name="Тест-шкала", min_value=1, max_value=5)


@pytest.mark.django_db
def test_employee_can_read_competencies(_scale: Scale) -> None:
    """Сотрудник может читать список шкал (чтение — всем)."""
    user = _user_with_role("emp@corp.local", Role.Code.EMPLOYEE.value)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/v1/competencies/scales/")

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_employee_cannot_create_competency(_scale: Scale) -> None:
    """Сотрудник не может создавать компетенции (403)."""
    user = _user_with_role("emp@corp.local", Role.Code.EMPLOYEE.value)
    client = APIClient()
    client.force_authenticate(user=user)
    group = CompetencyGroup.objects.create(name="Группа")

    response = client.post(
        "/api/v1/competencies/competencies/",
        {"name": "Новая", "group": group.id, "scale": _scale.id},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_hr_can_create_competency(_scale: Scale) -> None:
    """HR может создавать компетенции (SPEC §4.1)."""
    user = _user_with_role("hr@corp.local", Role.Code.HR.value)
    client = APIClient()
    client.force_authenticate(user=user)
    group = CompetencyGroup.objects.create(name="Группа")

    response = client.post(
        "/api/v1/competencies/competencies/",
        {"name": "Стратегия", "group": group.id, "scale": _scale.id},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_methodologist_can_create_group(_scale: Scale) -> None:
    """Методолог может создавать группы компетенций (SPEC §2.1)."""
    user = _user_with_role("meth@corp.local", Role.Code.METHODOLOGIST.value)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        "/api/v1/competencies/groups/",
        {"name": "Новая группа"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_anonymous_cannot_read_competencies() -> None:
    """Анонимный пользователь не имеет доступа (требуется аутентификация)."""
    client = APIClient()

    response = client.get("/api/v1/competencies/scales/")

    assert response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}
