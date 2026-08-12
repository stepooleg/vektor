"""API-сценарии редактирования и прогресса ИПР (SPEC §8, issue #73)."""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.assessment.models import (
    AssessmentCycle,
    AssessmentResponse,
    ExpectedLevel,
    Participant,
    ReviewerAssignment,
)
from apps.audit.models import AuditLogEntry
from apps.competencies.models import Competency, CompetencyGroup, Scale
from apps.idp.models import DevAction, DevelopmentPlan, DevGoal
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import Role, User


def _employee(
    code: str,
    *,
    role_code: str = Role.Code.EMPLOYEE.value,
    manager: Employee | None = None,
) -> tuple[Employee, APIClient]:
    """Создать сотрудника с ролью и аутентифицированным клиентом."""
    department, _ = Department.objects.get_or_create(
        code_1c="IDP-D", defaults={"name": "Разработка"}
    )
    position, _ = Position.objects.get_or_create(code_1c="IDP-P", defaults={"name": "Разработчик"})
    user = User.objects.create_user(email=f"{code.lower()}@corp.local", password="Strong-Pwd-1")
    role, _ = Role.objects.get_or_create(code=role_code, defaults={"name": role_code})
    user.roles.add(role)
    employee = Employee.objects.create(
        code_1c=code,
        user=user,
        last_name="Иванов",
        first_name=code,
        department=department,
        position=position,
        manager=manager,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return employee, client


def _competency(name: str = "Лидерство") -> Competency:
    """Создать компетенцию с пятибалльной шкалой."""
    scale = Scale.objects.create(name=f"Шкала {name}", min_value=1, max_value=5)
    group = CompetencyGroup.objects.create(name=f"Группа {name}")
    return Competency.objects.create(name=name, group=group, scale=scale)


@pytest.mark.django_db
def test_employee_cannot_create_or_edit_idp() -> None:
    """Сотрудник просматривает свой ИПР, но не меняет его (SPEC §2.1)."""
    employee, client = _employee("EMPLOYEE")
    plan = DevelopmentPlan.objects.create(employee=employee)

    created = client.post("/api/v1/idp/plans/", {"employee": employee.id}, format="json")
    updated = client.patch(f"/api/v1/idp/plans/{plan.id}/", {"title": "Подмена"}, format="json")

    assert created.status_code == status.HTTP_403_FORBIDDEN
    assert updated.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_manager_creates_plan_only_for_subordinate_and_audits_change() -> None:
    """Руководитель создаёт ИПР только участнику своей команды."""
    manager, client = _employee("MANAGER", role_code=Role.Code.MANAGER.value)
    subordinate, _ = _employee("SUBORDINATE", manager=manager)
    outsider, _ = _employee("OUTSIDER")

    allowed = client.post(
        "/api/v1/idp/plans/",
        {"employee": subordinate.id, "title": "ИПР на полугодие"},
        format="json",
    )
    forbidden = client.post(
        "/api/v1/idp/plans/", {"employee": outsider.id, "title": "Чужой ИПР"}, format="json"
    )

    assert allowed.status_code == status.HTTP_201_CREATED
    assert forbidden.status_code == status.HTTP_403_FORBIDDEN
    assert AuditLogEntry.objects.filter(
        actor=manager.user,
        action="idp.plan.create",
        target_id=str(allowed.data["id"]),
    ).exists()


@pytest.mark.django_db
def test_manager_options_include_only_subordinates() -> None:
    """Справочник формы не раскрывает руководителю посторонних сотрудников."""
    manager, client = _employee("MANAGER", role_code=Role.Code.MANAGER.value)
    subordinate, _ = _employee("SUBORDINATE", manager=manager)
    outsider, _ = _employee("OUTSIDER")

    response = client.get("/api/v1/idp/plans/options/")

    assert response.status_code == status.HTTP_200_OK
    employee_ids = {item["id"] for item in response.data["employees"]}
    assert subordinate.id in employee_ids
    assert manager.id not in employee_ids
    assert outsider.id not in employee_ids


@pytest.mark.django_db
def test_hr_can_create_plan_for_any_employee() -> None:
    """HR создаёт план для любого сотрудника компании."""
    _, client = _employee("HR", role_code=Role.Code.HR.value)
    target, _ = _employee("TARGET")

    response = client.post(
        "/api/v1/idp/plans/", {"employee": target.id, "title": "ИПР HR"}, format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["employee"] == target.id


@pytest.mark.django_db
def test_manager_adds_goal_action_and_updates_progress() -> None:
    """Ручная правка целей/действий обновляет вычисляемый прогресс плана."""
    manager, client = _employee("MANAGER", role_code=Role.Code.MANAGER.value)
    subordinate, _ = _employee("SUBORDINATE", manager=manager)
    competency = _competency()
    plan = DevelopmentPlan.objects.create(employee=subordinate)

    goal_response = client.post(
        "/api/v1/idp/goals/",
        {
            "plan": plan.id,
            "competency": competency.id,
            "title": "Развить лидерство",
            "target_level": 4,
        },
        format="json",
    )
    action_response = client.post(
        "/api/v1/idp/actions/",
        {
            "goal": goal_response.data["id"],
            "type": DevAction.Type.PRACTICE.value,
            "title": "Провести ретроспективу",
        },
        format="json",
    )
    progress_response = client.patch(
        f"/api/v1/idp/actions/{action_response.data['id']}/",
        {"progress_percent": 60},
        format="json",
    )
    plan_response = client.get(f"/api/v1/idp/plans/{plan.id}/")

    assert goal_response.status_code == status.HTTP_201_CREATED
    assert action_response.status_code == status.HTTP_201_CREATED
    assert progress_response.status_code == status.HTTP_200_OK
    assert progress_response.data["status"] == DevAction.Status.IN_PROGRESS.value
    assert plan_response.data["progress_percent"] == 60
    assert AuditLogEntry.objects.filter(action="idp.action.update").exists()


@pytest.mark.django_db
def test_completed_action_has_full_progress() -> None:
    """Статус «завершено» синхронизируется со 100% прогресса."""
    manager, client = _employee("MANAGER", role_code=Role.Code.MANAGER.value)
    subordinate, _ = _employee("SUBORDINATE", manager=manager)
    competency = _competency()
    plan = DevelopmentPlan.objects.create(employee=subordinate)
    goal = DevGoal.objects.create(plan=plan, competency=competency, title="Цель")
    action = DevAction.objects.create(goal=goal, type=DevAction.Type.TASK, title="Задача")

    response = client.patch(
        f"/api/v1/idp/actions/{action.id}/",
        {"status": DevAction.Status.COMPLETED.value},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["progress_percent"] == 100


@pytest.mark.django_db
def test_plan_status_cannot_skip_lifecycle_stage() -> None:
    """API запрещает пропуск этапов жизненного цикла ИПР."""
    manager, client = _employee("MANAGER", role_code=Role.Code.MANAGER.value)
    subordinate, _ = _employee("SUBORDINATE", manager=manager)
    plan = DevelopmentPlan.objects.create(employee=subordinate)

    response = client.patch(
        f"/api/v1/idp/plans/{plan.id}/",
        {"status": DevelopmentPlan.Status.IN_PROGRESS.value},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    plan.refresh_from_db()
    assert plan.status == DevelopmentPlan.Status.DRAFT.value


@pytest.mark.django_db
def test_manager_cannot_reassign_existing_plan_to_outsider() -> None:
    """Поле владельца ИПР неизменяемо и не позволяет обойти объектные права."""
    manager, client = _employee("MANAGER", role_code=Role.Code.MANAGER.value)
    subordinate, _ = _employee("SUBORDINATE", manager=manager)
    outsider, _ = _employee("OUTSIDER")
    plan = DevelopmentPlan.objects.create(employee=subordinate)

    response = client.patch(
        f"/api/v1/idp/plans/{plan.id}/",
        {"employee": outsider.id, "title": "Обновлённый ИПР"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    plan.refresh_from_db()
    assert plan.employee == subordinate
    assert plan.title == "Обновлённый ИПР"


@pytest.mark.django_db
def test_auto_generate_uses_anonymous_assessment_aggregate_and_explains_source() -> None:
    """Автоподбор показывает цикл и агрегированные уровни без данных оценщиков."""
    manager, client = _employee("MANAGER", role_code=Role.Code.MANAGER.value)
    subordinate, _ = _employee("SUBORDINATE", manager=manager)
    reviewer_one, _ = _employee("REVIEWER-1")
    reviewer_two, _ = _employee("REVIEWER-2")
    competency = _competency()
    ExpectedLevel.objects.create(
        position=subordinate.position, competency=competency, expected_level=4
    )
    cycle = AssessmentCycle.objects.create(
        name="Оценка 2026",
        status=AssessmentCycle.Status.AGGREGATED,
        anonymity_threshold=2,
    )
    participant = Participant.objects.create(cycle=cycle, employee=subordinate)
    for reviewer, score in ((reviewer_one, 2), (reviewer_two, 3)):
        assignment = ReviewerAssignment.objects.create(
            cycle=cycle,
            participant=participant,
            reviewer=reviewer,
            group=ReviewerAssignment.Group.PEER,
            completed=True,
        )
        AssessmentResponse.objects.create(assignment=assignment, competency=competency, score=score)

    response = client.post(
        "/api/v1/idp/plans/auto-generate/",
        {"employee": subordinate.id, "cycle": cycle.id},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    source = response.data["goals"][0]["source"]
    assert source == {
        "type": "assessment",
        "cycle_id": cycle.id,
        "cycle_name": "Оценка 2026",
        "current_level": 2.5,
        "expected_level": 4,
    }
    assert "reviewer" not in str(response.data).lower()
    assert AuditLogEntry.objects.filter(action="idp.plan.auto_generate").exists()


@pytest.mark.django_db
def test_auto_generate_ignores_group_below_anonymity_threshold() -> None:
    """Оценки группы ниже порога не используются в ИПР и не раскрываются."""
    manager, client = _employee("MANAGER", role_code=Role.Code.MANAGER.value)
    subordinate, _ = _employee("SUBORDINATE", manager=manager)
    reviewer, _ = _employee("REVIEWER")
    competency = _competency()
    ExpectedLevel.objects.create(
        position=subordinate.position, competency=competency, expected_level=4
    )
    cycle = AssessmentCycle.objects.create(
        name="Закрытая группа",
        status=AssessmentCycle.Status.AGGREGATED,
        anonymity_threshold=2,
    )
    participant = Participant.objects.create(cycle=cycle, employee=subordinate)
    assignment = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=reviewer,
        group=ReviewerAssignment.Group.PEER,
        completed=True,
    )
    AssessmentResponse.objects.create(assignment=assignment, competency=competency, score=1)

    response = client.post(
        "/api/v1/idp/plans/auto-generate/",
        {"employee": subordinate.id, "cycle": cycle.id},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert DevelopmentPlan.objects.filter(employee=subordinate).count() == 0
