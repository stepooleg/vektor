"""Тесты производительности (Test-First, SPEC §11.3, issue #32).

Контракты:
- дашборд компании не создаёт N+1 запросов (ограниченное число запросов);
- агрегаты используют БД (Avg), а не Python-циклы.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.analytics.services import build_company_dashboard
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


def _seed_data(n: int = 10) -> None:
    """Создать N сотрудников с оценками для теста производительности."""
    dept = Department.objects.create(code_1c="D1", name="ИТ")
    pos = Position.objects.create(code_1c="P1", name="Разработчик")
    competency = Competency.objects.create(
        name="К1",
        group=CompetencyGroup.objects.create(name="Г1"),
        scale=Scale.objects.create(name="Ш1", min_value=1, max_value=5),
    )
    cycle = AssessmentCycle.objects.create(
        name="Ц1", status=AssessmentCycle.Status.AGGREGATED.value
    )
    for i in range(n):
        emp = Employee.objects.create(
            code_1c=f"E{i}",
            user=User.objects.create_user(email=f"e{i}@corp.local", password="Strong-Pwd-1"),
            last_name="И",
            first_name=str(i),
            department=dept,
            position=pos,
        )
        participant = Participant.objects.create(cycle=cycle, employee=emp)
        a = ReviewerAssignment.objects.create(
            cycle=cycle,
            participant=participant,
            reviewer=emp,
            group=ReviewerAssignment.Group.SELF.value,
        )
        AssessmentResponse.objects.create(assignment=a, competency=competency, score=4)
        mark_assignment_completed(a)


@pytest.mark.django_db
def test_company_dashboard_query_count_is_bounded() -> None:
    """Дашборд компании выполняет ограниченное число запросов (без N+1, §11.3)."""
    from django.test.utils import CaptureQueriesContext

    _seed_data(n=20)

    # Прогрев кеша ORM.
    _ = build_company_dashboard()

    # Замер числа запросов при повторном вызове.
    with CaptureQueriesContext(connection) as ctx:
        _ = build_company_dashboard()

    # Дашборд должен выполняться за константное число запросов (≤ 6),
    # не зависящее от числа сотрудников (агрегаты через Avg).
    query_count = len(ctx.captured_queries)
    assert query_count <= 6, f"Ожидалось ≤6 запросов, получено {query_count}"
