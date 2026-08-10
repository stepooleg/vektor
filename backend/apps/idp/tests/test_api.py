"""API-тесты ИПР (Test-First, SPEC §8, issue #63)."""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.competencies.models import Competency, CompetencyGroup, Scale
from apps.idp.models import DevAction, DevelopmentPlan, DevGoal
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import User


def _employee(code: str, email: str) -> Employee:
    department = Department.objects.create(code_1c=f"D-{code}", name=f"Отдел {code}")
    position = Position.objects.create(code_1c=f"P-{code}", name=f"Должность {code}")
    user = User.objects.create_user(email=email, password="Strong-Pwd-1")
    return Employee.objects.create(
        code_1c=code,
        user=user,
        last_name="Иванов",
        first_name=code,
        department=department,
        position=position,
    )


@pytest.mark.django_db
def test_employee_sees_only_own_plans_with_nested_goals() -> None:
    """Сотрудник получает только свой ИПР с целями и действиями."""
    employee = _employee("E1", "employee@corp.local")
    another = _employee("E2", "another@corp.local")
    scale = Scale.objects.create(name="Шкала", min_value=1, max_value=5)
    group = CompetencyGroup.objects.create(name="Группа")
    competency = Competency.objects.create(name="Лидерство", group=group, scale=scale)
    plan = DevelopmentPlan.objects.create(employee=employee, title="ИПР сотрудника")
    goal = DevGoal.objects.create(
        plan=plan,
        competency=competency,
        title="Развить лидерство",
        target_level=4,
    )
    DevAction.objects.create(
        goal=goal,
        type=DevAction.Type.READING,
        title="Прочитать книгу",
    )
    DevelopmentPlan.objects.create(employee=another, title="Чужой ИПР")
    client = APIClient()
    client.force_authenticate(user=employee.user)

    response = client.get("/api/v1/idp/plans/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["count"] == 1
    result = response.json()["results"][0]
    assert result["title"] == "ИПР сотрудника"
    assert result["goals"][0]["title"] == "Развить лидерство"
    assert result["goals"][0]["actions"][0]["title"] == "Прочитать книгу"


@pytest.mark.django_db
def test_idp_api_denies_anonymous_user() -> None:
    """ИПР недоступен без действующей сессии."""
    response = APIClient().get("/api/v1/idp/plans/")

    assert response.status_code == status.HTTP_403_FORBIDDEN
