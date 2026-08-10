"""Тесты API циклов оценки (Test-First, SPEC §5, §14.2, issue #17).

Контракты:
- HR может создавать циклы; сотрудник — нет (403);
- аутентифицированный видит список циклов;
- эндпоинт результатов возвращает агрегаты (без сырых данных), с учётом порога.
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


def _user(email: str, role_code: str) -> User:
    """Создать пользователя с ролью."""
    user = User.objects.create_user(email=email, password="Strong-Pwd-1")
    role, _ = Role.objects.get_or_create(code=role_code, defaults={"name": role_code})
    user.roles.add(role)
    return user


def _employee(code: str, email: str) -> Employee:
    """Создать сотрудника."""
    dept = Department.objects.create(code_1c=f"D{code}", name=f"Отдел {code}")
    pos = Position.objects.create(code_1c=f"P{code}", name=f"Должность {code}")
    user = User.objects.create_user(email=email, password="Strong-Pwd-1")
    return Employee.objects.create(
        code_1c=code,
        user=user,
        last_name="И",
        first_name=code,
        department=dept,
        position=pos,
    )


@pytest.mark.django_db
def test_hr_can_create_cycle() -> None:
    """HR создаёт цикл оценки (SPEC §5.2, §2.1)."""
    hr = _user("hr@corp.local", Role.Code.HR.value)
    client = APIClient()
    client.force_authenticate(user=hr)

    response = client.post(
        "/api/v1/assessment/cycles/",
        {"name": "Оценка 2026", "anonymity_threshold": 3},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert AssessmentCycle.objects.filter(name="Оценка 2026").exists()


@pytest.mark.django_db
def test_employee_cannot_create_cycle() -> None:
    """Сотрудник не может создавать циклы (403)."""
    emp_user = _user("emp@corp.local", Role.Code.EMPLOYEE.value)
    client = APIClient()
    client.force_authenticate(user=emp_user)

    response = client.post(
        "/api/v1/assessment/cycles/",
        {"name": "Цикл"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_hr_can_list_all_cycles() -> None:
    """HR видит общий список циклов."""
    AssessmentCycle.objects.create(name="Цикл 1")
    AssessmentCycle.objects.create(name="Цикл 2")
    user = _user("hr-list@corp.local", Role.Code.HR.value)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/v1/assessment/cycles/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] >= 2


@pytest.mark.django_db
def test_employee_cannot_list_management_cycles() -> None:
    """Сотрудник работает через свои задания и не получает управленческий список."""
    AssessmentCycle.objects.create(name="Чужой цикл")
    user = _user("employee-list@corp.local", Role.Code.EMPLOYEE.value)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/v1/assessment/cycles/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 0


@pytest.mark.django_db
def test_results_endpoint_returns_aggregates_no_raw() -> None:
    """Эндпоинт результатов возвращает агрегаты (без сырых оценок, SPEC §6.3)."""
    emp = _employee("E1", "e1@corp.local")
    hr = _user("hr@corp.local", Role.Code.HR.value)
    competency = Competency.objects.create(
        name="К1",
        group=CompetencyGroup.objects.create(name="Г1"),
        scale=Scale.objects.create(name="Ш1", min_value=1, max_value=5),
    )
    cycle = AssessmentCycle.objects.create(
        name="Цикл",
        status=AssessmentCycle.Status.AGGREGATED.value,
        anonymity_threshold=2,
    )
    participant = Participant.objects.create(cycle=cycle, employee=emp)
    # Менеджер (1) + 2 подчинённых (≥ порога 2).
    manager = _employee("M1", "m1@corp.local")
    a_mgr = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=manager,
        group=ReviewerAssignment.Group.MANAGER.value,
    )
    AssessmentResponse.objects.create(assignment=a_mgr, competency=competency, score=4)
    mark_assignment_completed(a_mgr)
    subs = [_employee(f"S{i}", f"s{i}@corp.local") for i in range(2)]
    for s in subs:
        a = ReviewerAssignment.objects.create(
            cycle=cycle,
            participant=participant,
            reviewer=s,
            group=ReviewerAssignment.Group.SUBORDINATE.value,
        )
        AssessmentResponse.objects.create(assignment=a, competency=competency, score=5)
        mark_assignment_completed(a)

    client = APIClient()
    client.force_authenticate(user=hr)
    response = client.get(f"/api/v1/assessment/cycles/{cycle.id}/results/")

    assert response.status_code == status.HTTP_200_OK
    body = response.data
    groups = {g["group"]: g for g in body["groups"]}
    # Группа subordinate видна (2 ≥ порога 2) и содержит среднее.
    assert groups["subordinate"]["hidden_by_threshold"] is False
    assert groups["subordinate"]["mean_score"] == 5.0
    # Нет сырых полей.
    for g in body["groups"]:
        assert "responses" not in g
        assert "scores" not in g
        assert "reviewer_id" not in g


@pytest.mark.django_db
def test_results_endpoint_hides_group_below_threshold() -> None:
    """Группа ниже порога — hidden_by_threshold=True (SPEC §6.3)."""
    emp = _employee("E1", "e1@corp.local")
    hr = _user("hr@corp.local", Role.Code.HR.value)
    competency = Competency.objects.create(
        name="К1",
        group=CompetencyGroup.objects.create(name="Г1"),
        scale=Scale.objects.create(name="Ш1", min_value=1, max_value=5),
    )
    cycle = AssessmentCycle.objects.create(
        name="Цикл", status=AssessmentCycle.Status.AGGREGATED.value, anonymity_threshold=3
    )
    participant = Participant.objects.create(cycle=cycle, employee=emp)
    manager = _employee("M1", "m1@corp.local")
    a_mgr = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=manager,
        group=ReviewerAssignment.Group.MANAGER.value,
    )
    AssessmentResponse.objects.create(assignment=a_mgr, competency=competency, score=5)
    mark_assignment_completed(a_mgr)
    # Только 1 подчинённый (< порога 3) — группа скрыта.
    sub = _employee("S1", "s1@corp.local")
    a = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=sub,
        group=ReviewerAssignment.Group.SUBORDINATE.value,
    )
    AssessmentResponse.objects.create(assignment=a, competency=competency, score=4)
    mark_assignment_completed(a)

    client = APIClient()
    client.force_authenticate(user=hr)
    response = client.get(f"/api/v1/assessment/cycles/{cycle.id}/results/")

    groups = {g["group"]: g for g in response.data["groups"]}
    assert groups["subordinate"]["hidden_by_threshold"] is True
