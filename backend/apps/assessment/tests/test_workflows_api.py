"""Пользовательские API-сценарии оценки (issue #70, SPEC §5, §14.2)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.assessment.models import AssessmentCycle, AssessmentResponse, Participant
from apps.competencies.models import (
    Competency,
    CompetencyFramework,
    CompetencyGroup,
    Scale,
)
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import Role, User


def _employee(code: str, *, manager: Employee | None = None, role: str = "employee") -> Employee:
    """Создать сотрудника с учётной записью и бизнес-ролью."""
    user = User.objects.create_user(email=f"{code.lower()}@corp.local", password="Strong-Pwd-1")
    role_obj, _ = Role.objects.get_or_create(code=role, defaults={"name": role})
    user.roles.add(role_obj)
    department, _ = Department.objects.get_or_create(code_1c="D-WF", defaults={"name": "Отдел"})
    position, _ = Position.objects.get_or_create(code_1c="P-WF", defaults={"name": "Инженер"})
    return Employee.objects.create(
        code_1c=code,
        user=user,
        last_name="Сотрудник",
        first_name=code,
        department=department,
        position=position,
        manager=manager,
    )


def _framework() -> tuple[CompetencyFramework, Competency]:
    """Создать модель с одной компетенцией и шкалой 1–5."""
    scale = Scale.objects.create(name="Шкала workflow", min_value=1, max_value=5)
    group = CompetencyGroup.objects.create(name="Группа workflow")
    competency = Competency.objects.create(
        name="Командная работа", description="Работает в команде", group=group, scale=scale
    )
    framework = CompetencyFramework.objects.create(name="Модель workflow")
    framework.competencies.add(competency)
    return framework, competency


def _client(employee: Employee) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=employee.user)
    return client


@pytest.mark.django_db
def test_manager_setup_options_contain_only_own_eligible_team() -> None:
    """Мастер руководителя не раскрывает чужих сотрудников и исключает неучаствующих."""
    manager = _employee("M-WF", role=Role.Code.MANAGER.value)
    own = _employee("OWN-WF", manager=manager)
    excluded = _employee("LEAVE-WF", manager=manager)
    excluded.assessment_eligible = False
    excluded.save(update_fields=["assessment_eligible"])
    _employee("OTHER-WF")
    framework, _ = _framework()

    response = _client(manager).get("/api/v1/assessment/cycles/setup-options/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["frameworks"] == [{"id": framework.id, "name": framework.name}]
    assert [item["id"] for item in response.data["participants"]] == [own.id]


@pytest.mark.django_db
def test_manager_creates_assigned_cycle_only_for_own_team() -> None:
    """Создание с участниками атомарно формирует назначения по оргструктуре."""
    manager = _employee("M-CREATE", role=Role.Code.MANAGER.value)
    subordinate = _employee("SUB-CREATE", manager=manager)
    outsider_manager = _employee("OTHER-MANAGER")
    outsider = _employee("OUT-CREATE", manager=outsider_manager)
    framework, _ = _framework()
    payload = {
        "name": "Оценка команды",
        "framework": framework.id,
        "participant_ids": [subordinate.id],
        "start_date": str(date.today()),
        "deadline": str(date.today() + timedelta(days=14)),
        "anonymity_threshold": 3,
    }

    response = _client(manager).post("/api/v1/assessment/cycles/", payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    cycle = AssessmentCycle.objects.get(pk=response.data["id"])
    assert cycle.status == AssessmentCycle.Status.ASSIGNED.value
    assert cycle.created_by == manager.user
    participant = Participant.objects.get(cycle=cycle, employee=subordinate)
    assert set(participant.reviewer_assignments.values_list("group", flat=True)) == {
        "manager",
        "self",
    }

    payload["participant_ids"] = [outsider.id]
    forbidden = _client(manager).post("/api/v1/assessment/cycles/", payload, format="json")
    assert forbidden.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_cycle_creator_can_start_assigned_cycle() -> None:
    """Руководитель запускает только созданный им подготовленный цикл."""
    manager = _employee("M-START", role=Role.Code.MANAGER.value)
    framework, _ = _framework()
    cycle = AssessmentCycle.objects.create(
        name="Готовый цикл",
        framework=framework,
        status=AssessmentCycle.Status.ASSIGNED.value,
        created_by=manager.user,
    )

    response = _client(manager).post(f"/api/v1/assessment/cycles/{cycle.id}/start/")

    assert response.status_code == status.HTTP_200_OK
    cycle.refresh_from_db()
    assert cycle.status == AssessmentCycle.Status.IN_PROGRESS.value

    other_manager = _employee("M-START-OTHER", role=Role.Code.MANAGER.value)
    forbidden = _client(other_manager).post(f"/api/v1/assessment/cycles/{cycle.id}/start/")
    assert forbidden.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_reviewer_sees_only_own_assignments_and_submits_once() -> None:
    """Оценщик получает опросник без чужих данных и завершает его одной отправкой."""
    manager = _employee("M-SUBMIT", role=Role.Code.MANAGER.value)
    subordinate = _employee("SUB-SUBMIT", manager=manager)
    outsider = _employee("OUT-SUBMIT")
    framework, competency = _framework()
    cycle = AssessmentCycle.objects.create(
        name="Активный цикл",
        framework=framework,
        status=AssessmentCycle.Status.IN_PROGRESS.value,
        created_by=manager.user,
    )
    participant = Participant.objects.create(cycle=cycle, employee=subordinate)
    manager_assignment = participant.reviewer_assignments.create(
        cycle=cycle, reviewer=manager, group="manager"
    )
    participant.reviewer_assignments.create(cycle=cycle, reviewer=outsider, group="peer")

    list_response = _client(manager).get("/api/v1/assessment/assignments/")

    assert list_response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in list_response.data["results"]] == [manager_assignment.id]
    assignment = list_response.data["results"][0]
    assert assignment["participant_name"] == subordinate.full_name
    assert assignment["competencies"] == [
        {
            "id": competency.id,
            "name": competency.name,
            "description": competency.description,
            "min_value": 1,
            "max_value": 5,
        }
    ]
    assert "responses" not in assignment

    submit_response = _client(manager).post(
        f"/api/v1/assessment/assignments/{manager_assignment.id}/submit/",
        {
            "responses": [
                {"competency_id": competency.id, "score": 4, "comment": "Сильная сторона"}
            ],
            "general_comment": "Продолжать развиваться",
        },
        format="json",
    )

    assert submit_response.status_code == status.HTTP_200_OK
    assert submit_response.data == {"completed": True}
    assert AssessmentResponse.objects.filter(assignment=manager_assignment, score=4).exists()
    assert manager_assignment.comments.count() == 2

    repeated = _client(manager).post(
        f"/api/v1/assessment/assignments/{manager_assignment.id}/submit/",
        {"responses": [{"competency_id": competency.id, "score": 5}]},
        format="json",
    )
    assert repeated.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_employee_cannot_read_cycle_results() -> None:
    """Обычный сотрудник не получает агрегаты всего цикла через прямой URL."""
    employee = _employee("NO-RESULTS")
    cycle = AssessmentCycle.objects.create(name="Результаты")

    response = _client(employee).get(f"/api/v1/assessment/cycles/{cycle.id}/results/")

    assert response.status_code == status.HTTP_403_FORBIDDEN
