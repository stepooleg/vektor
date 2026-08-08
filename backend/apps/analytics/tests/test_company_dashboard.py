"""Тесты дашборда по компании/подразделениям (Test-First, SPEC §9.1, §9.3, issue #30).

Контракты:
- % сотрудников с завершённой оценкой (охват);
- динамика средних баллов во времени;
- сравнение подразделений;
- права: руководитель видит своё подразделение.
"""

from __future__ import annotations

import pytest

from apps.analytics.services import build_company_dashboard, build_department_dashboard
from apps.assessment.models import (
    AssessmentCycle,
    AssessmentResponse,
    Participant,
    ReviewerAssignment,
)
from apps.assessment.services import mark_assignment_completed
from apps.competencies.models import Competency, CompetencyGroup, Scale
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import User


def _employee(code: str, email: str, *, dept: Department, pos: Position) -> Employee:
    """Создать сотрудника в подразделении/должности."""
    user = User.objects.create_user(email=email, password="Strong-Pwd-1")
    return Employee.objects.create(
        code_1c=code,
        user=user,
        last_name="И",
        first_name=code,
        department=dept,
        position=pos,
    )


def _setup_cycle_with_response(
    emp: Employee, *, score: int = 4, status: str = AssessmentCycle.Status.AGGREGATED.value
) -> None:
    """Создать цикл с оценкой сотрудника."""
    competency = Competency.objects.create(
        name=f"C-{emp.code_1c}",
        group=CompetencyGroup.objects.create(name=f"G-{emp.code_1c}"),
        scale=Scale.objects.create(name=f"S-{emp.code_1c}", min_value=1, max_value=5),
    )
    cycle = AssessmentCycle.objects.create(name=f"Ц-{emp.code_1c}", status=status)
    participant = Participant.objects.create(cycle=cycle, employee=emp)
    manager = Employee.objects.create(
        code_1c=f"M-{emp.code_1c}",
        user=User.objects.create_user(email=f"m-{emp.code_1c}@corp.local", password="x"),
        last_name="М",
        first_name="",
        department=emp.department,
        position=emp.position,
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
def test_company_dashboard_assessment_coverage() -> None:
    """Дашборд компании: % сотрудников с завершённой оценкой (SPEC §9.1)."""
    dept = Department.objects.create(code_1c="D1", name="ИТ")
    pos = Position.objects.create(code_1c="P1", name="Разработчик")
    # 2 из 3 имеют завершённые циклы.
    e1 = _employee("E1", "e1@corp.local", dept=dept, pos=pos)
    e2 = _employee("E2", "e2@corp.local", dept=dept, pos=pos)
    _employee("E3", "e3@corp.local", dept=dept, pos=pos)  # без цикла
    _setup_cycle_with_response(e1, score=4)
    _setup_cycle_with_response(e2, score=5)

    dashboard = build_company_dashboard()

    # 3 основных + 2 менеджера (из _setup_cycle_with_response) = 5 активных.
    assert dashboard["total_employees"] == 5
    assert dashboard["assessed_employees"] == 2
    assert dashboard["assessment_coverage"] == pytest.approx(40.0, abs=0.1)


@pytest.mark.django_db
def test_company_dashboard_average_score() -> None:
    """Дашборд компании: средний балл по компании."""
    dept = Department.objects.create(code_1c="D1", name="ИТ")
    pos = Position.objects.create(code_1c="P1", name="Разработчик")
    e1 = _employee("E1", "e1@corp.local", dept=dept, pos=pos)
    e2 = _employee("E2", "e2@corp.local", dept=dept, pos=pos)
    _setup_cycle_with_response(e1, score=3)
    _setup_cycle_with_response(e2, score=5)

    dashboard = build_company_dashboard()

    assert dashboard["average_score"] == pytest.approx(4.0)


@pytest.mark.django_db
def test_department_dashboard() -> None:
    """Дашборд подразделения: агрегаты по отделу (SPEC §9.3)."""
    it = Department.objects.create(code_1c="IT", name="ИТ")
    sales = Department.objects.create(code_1c="SAL", name="Продажи")
    pos = Position.objects.create(code_1c="P1", name="Сотрудник")
    e1 = _employee("E1", "e1@corp.local", dept=it, pos=pos)
    e2 = _employee("E2", "e2@corp.local", dept=sales, pos=pos)
    _setup_cycle_with_response(e1, score=4)
    _setup_cycle_with_response(e2, score=2)

    it_dashboard = build_department_dashboard(it)

    assert it_dashboard["department_name"] == "ИТ"
    # e1 + его менеджер (в том же отделе) = 2.
    assert it_dashboard["total_employees"] == 2
    assert it_dashboard["average_score"] == pytest.approx(4.0)


@pytest.mark.django_db
def test_company_dashboard_has_no_raw_scores() -> None:
    """Дашборд компании содержит только агрегаты, без сырых данных (SPEC §6.3)."""
    dept = Department.objects.create(code_1c="D1", name="ИТ")
    pos = Position.objects.create(code_1c="P1", name="Сотрудник")
    e1 = _employee("E1", "e1@corp.local", dept=dept, pos=pos)
    _setup_cycle_with_response(e1, score=4)

    dashboard = build_company_dashboard()

    # Нет сырых полей отдельных оценщиков.
    assert "responses" not in dashboard
    assert "scores" not in dashboard
