"""Тесты дашборда по сотруднику (Test-First, SPEC §9.2, issue #15).

Контракты:
- API соблюдает права: сотрудник видит себя, руководитель — подчинённых,
  HR — всех; чужого — 403;
- данные агрегированы (без сырых оценок);
- динамика корректна по нескольким циклам;
- учитывается порог анонимности (группы ниже порога скрыты).
"""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.assessment.models import (
    AssessmentCycle,
    AssessmentResponse,
    Participant,
    ReviewerAssignment,
)
from apps.assessment.services import mark_assignment_completed
from apps.competencies.models import Competency, CompetencyGroup, Scale
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import Role, User


def _user_with_role_and_employee(
    code: str, email: str, role_code: str, *, manager: Employee | None = None
) -> tuple[User, Employee]:
    """Создать пользователя с ролью и сотрудником (роль get_or_create — code unique)."""
    user = User.objects.create_user(email=email, password="Strong-Pwd-1")
    if role_code:
        role, _ = Role.objects.get_or_create(code=role_code, defaults={"name": role_code})
        user.roles.add(role)
    dept = Department.objects.create(code_1c=f"D{code}", name=f"Отдел {code}")
    pos = Position.objects.create(code_1c=f"P{code}", name=f"Должность {code}")
    emp = Employee.objects.create(
        code_1c=code,
        user=user,
        last_name="И",
        first_name=code,
        department=dept,
        position=pos,
        manager=manager,
    )
    return user, emp


def _add_reviewer_scores(
    cycle: AssessmentCycle, participant: Participant, competency: Competency, score: int
) -> None:
    """Добавить оценку от руководителя и отметить завершённой."""
    manager = Employee.objects.create(
        code_1c=f"M-{participant.id}-{competency.id}",
        user=User.objects.create_user(
            email=f"m-{participant.id}-{competency.id}@corp.local", password="Strong-Pwd-1"
        ),
        last_name="М",
        first_name="",
        department=participant.employee.department,
        position=participant.employee.position,
    )
    a = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=manager,
        group=ReviewerAssignment.Group.MANAGER.value,
    )
    AssessmentResponse.objects.create(assignment=a, competency=competency, score=score)
    mark_assignment_completed(a)


@pytest.mark.django_db
def test_employee_can_view_own_dashboard() -> None:
    """Сотрудник видит свой дашборд."""
    user, emp = _user_with_role_and_employee("E1", "e1@corp.local", Role.Code.EMPLOYEE.value)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(f"/api/v1/analytics/employees/{emp.id}/dashboard/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["employee"]["id"] == emp.id


@pytest.mark.django_db
def test_employee_cannot_view_others_dashboard() -> None:
    """Сотрудник не видит чужой дашборд (403)."""
    _, emp_self = _user_with_role_and_employee("E1", "e1@corp.local", Role.Code.EMPLOYEE.value)
    _, emp_other = _user_with_role_and_employee("E2", "e2@corp.local", Role.Code.EMPLOYEE.value)
    client = APIClient()
    client.force_authenticate(user=emp_self.user)

    response = client.get(f"/api/v1/analytics/employees/{emp_other.id}/dashboard/")

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_manager_can_view_subordinate_dashboard() -> None:
    """Руководитель видит дашборд подчинённого."""
    _, boss = _user_with_role_and_employee("B1", "boss@corp.local", Role.Code.MANAGER.value)
    _, sub = _user_with_role_and_employee(
        "S1", "sub@corp.local", Role.Code.EMPLOYEE.value, manager=boss
    )
    client = APIClient()
    client.force_authenticate(user=boss.user)

    response = client.get(f"/api/v1/analytics/employees/{sub.id}/dashboard/")

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_hr_can_view_any_dashboard() -> None:
    """HR видит дашборд любого сотрудника."""
    _, hr = _user_with_role_and_employee("H1", "hr@corp.local", Role.Code.HR.value)
    _, emp = _user_with_role_and_employee("E1", "e1@corp.local", Role.Code.EMPLOYEE.value)
    client = APIClient()
    client.force_authenticate(user=hr.user)

    response = client.get(f"/api/v1/analytics/employees/{emp.id}/dashboard/")

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_dashboard_has_no_raw_scores() -> None:
    """Дашборд содержит только агрегаты, без сырых оценок."""
    user, emp = _user_with_role_and_employee("E1", "e1@corp.local", Role.Code.EMPLOYEE.value)
    competency = Competency.objects.create(
        name="К1",
        group=CompetencyGroup.objects.create(name="Г1"),
        scale=Scale.objects.create(name="Ш1", min_value=1, max_value=5),
    )
    cycle = AssessmentCycle.objects.create(
        name="Цикл", status=AssessmentCycle.Status.AGGREGATED.value
    )
    participant = Participant.objects.create(cycle=cycle, employee=emp)
    _add_reviewer_scores(cycle, participant, competency, 4)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(f"/api/v1/analytics/employees/{emp.id}/dashboard/")

    body = response.data
    # Профиль компетенций — агрегаты (по компетенции средний балл).
    profile = body["competency_profile"]
    assert any(p["competency_name"] == "К1" for p in profile)
    row = next(p for p in profile if p["competency_name"] == "К1")
    assert row["mean_score"] == 4.0
    # Нет сырых полей оценщиков.
    assert "reviewer" not in row
    assert "assignment_id" not in row
    assert "responses" not in row
