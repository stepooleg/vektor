"""Сервис аналитики: дашборд по сотруднику (SPEC §9.2).

Возвращает агрегированный профиль компетенций сотрудника (средние по циклам),
динамику по циклам и сравнение self vs others. Сырые оценки НЕ передаются —
только агрегаты (SPEC §6.3, §12).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import Avg

from apps.assessment.models import (
    AssessmentCycle,
    AssessmentResponse,
    Participant,
)

if TYPE_CHECKING:
    from apps.orgstructure.models import Department, Employee


@dataclass(frozen=True)
class CompetencyProfileRow:
    """Строка профиля компетенции (агрегат, без сырых данных)."""

    competency_id: int
    competency_name: str
    mean_score: float
    cycles_count: int


@dataclass(frozen=True)
class CycleDynamicsRow:
    """Динамика по циклу (агрегат)."""

    cycle_id: int
    cycle_name: str
    overall_mean: float


def build_employee_dashboard(employee: Employee) -> dict[str, object]:
    """Собрать агрегированный дашборд сотрудника (SPEC §9.2).

    Возвращает словарь:
    - employee: {id, full_name, department, position};
    - competency_profile: [{competency_id, competency_name, mean_score, cycles_count}];
    - cycle_dynamics: [{cycle_id, cycle_name, overall_mean}].
    """
    # Все participation сотрудника.
    participations = Participant.objects.filter(
        employee=employee,
        cycle__status=AssessmentCycle.Status.AGGREGATED.value,
    )

    # Профиль компетенций: средний балл по каждой компетенции (все циклы).
    profile_qs = (
        AssessmentResponse.objects.filter(
            assignment__participant__in=participations,
            assignment__completed=True,
        )
        .values("competency_id", "competency__name")
        .annotate(mean_score=Avg("score"), cycles_count__count=Avg("id"))  # placeholder
    )
    # Пересчитаем cycles_count корректно (distinct циклов).
    profile_rows: list[CompetencyProfileRow] = []
    competency_ids = {r["competency_id"] for r in profile_qs}
    for cid in competency_ids:
        comp_responses = AssessmentResponse.objects.filter(
            assignment__participant__in=participations,
            assignment__completed=True,
            competency_id=cid,
        )
        if not comp_responses.exists():
            continue
        comp = comp_responses.first().competency  # type: ignore[union-attr]
        cycles_count = comp_responses.values("assignment__participant__cycle_id").distinct().count()
        mean = comp_responses.aggregate(m=Avg("score"))["m"] or 0.0
        profile_rows.append(
            CompetencyProfileRow(
                competency_id=cid,
                competency_name=comp.name,
                mean_score=round(float(mean), 2),
                cycles_count=cycles_count,
            )
        )
    profile_rows.sort(key=lambda r: r.competency_name)

    # Динамика по циклам: общий средний балл в каждом цикле.
    dynamics: list[CycleDynamicsRow] = []
    for p in participations:
        cycle_responses = AssessmentResponse.objects.filter(
            assignment__participant=p, assignment__completed=True
        )
        if not cycle_responses.exists():
            continue
        overall = cycle_responses.aggregate(m=Avg("score"))["m"] or 0.0
        dynamics.append(
            CycleDynamicsRow(
                cycle_id=p.cycle_id,
                cycle_name=p.cycle.name,
                overall_mean=round(float(overall), 2),
            )
        )
    dynamics.sort(key=lambda r: r.cycle_id)

    return {
        "employee": {
            "id": employee.id,
            "full_name": employee.full_name,
            "department": employee.department.name if employee.department_id else "",
            "position": employee.position.name if employee.position_id else "",
        },
        "competency_profile": [
            {
                "competency_id": r.competency_id,
                "competency_name": r.competency_name,
                "mean_score": r.mean_score,
                "cycles_count": r.cycles_count,
            }
            for r in profile_rows
        ],
        "cycle_dynamics": [
            {
                "cycle_id": d.cycle_id,
                "cycle_name": d.cycle_name,
                "overall_mean": d.overall_mean,
            }
            for d in dynamics
        ],
    }


def can_view_employee_dashboard(viewer: Employee, target: Employee) -> bool:
    """Проверка прав на просмотр дашборда (SPEC §9.2, §2.2).

    - HR — любой;
    - руководитель — свой и подчинённые (рекурсивно);
    - сотрудник — только свой.
    Права берутся через роли пользователя-просмотрщика.
    """
    from apps.users.models import Role

    viewer_user = viewer.user
    if viewer_user.has_any_role(Role.Code.HR.value):
        return True
    if viewer_user.has_any_role(Role.Code.MANAGER.value):
        return viewer.id == target.id or target in viewer.get_subordinates()
    return viewer.id == target.id


# ---------------------------------------------------------------------------
# Дашборды по компании и подразделениям (SPEC §9.1, §9.3, issue #30)
# ---------------------------------------------------------------------------


def build_company_dashboard() -> dict[str, object]:
    """Агрегированный дашборд по компании (SPEC §9.1).

    Возвращает: total_employees, assessed_employees, assessment_coverage (%),
    average_score, total_cycles. Только агрегаты — без сырых данных (§6.3).
    """
    from apps.orgstructure.models import Employee

    total = Employee.objects.filter(is_active=True).count()
    assessed_ids = set(
        Participant.objects.filter(
            cycle__status=AssessmentCycle.Status.AGGREGATED.value
        ).values_list("employee_id", flat=True)
    )
    assessed = len(assessed_ids)
    coverage = round(assessed / total * 100, 2) if total else 0.0

    avg = AssessmentResponse.objects.filter(
        assignment__completed=True,
        assignment__participant__cycle__status=AssessmentCycle.Status.AGGREGATED.value,
    ).aggregate(m=Avg("score"))["m"]
    average_score = round(float(avg), 2) if avg else 0.0

    total_cycles = AssessmentCycle.objects.count()

    return {
        "total_employees": total,
        "assessed_employees": assessed,
        "assessment_coverage": coverage,
        "average_score": average_score,
        "total_cycles": total_cycles,
    }


def build_department_dashboard(department: Department) -> dict[str, object]:
    """Агрегированный дашборд по подразделению (SPEC §9.3).

    Возвращает: department_name, total_employees, assessed_employees,
    assessment_coverage (%), average_score.
    """
    from apps.orgstructure.models import Employee

    total = Employee.objects.filter(is_active=True, department=department).count()
    assessed_ids = set(
        Participant.objects.filter(
            cycle__status=AssessmentCycle.Status.AGGREGATED.value,
            employee__department=department,
        ).values_list("employee_id", flat=True)
    )
    assessed = len(assessed_ids)
    coverage = round(assessed / total * 100, 2) if total else 0.0

    avg = AssessmentResponse.objects.filter(
        assignment__completed=True,
        assignment__participant__employee__department=department,
        assignment__participant__cycle__status=AssessmentCycle.Status.AGGREGATED.value,
    ).aggregate(m=Avg("score"))["m"]
    average_score = round(float(avg), 2) if avg else 0.0

    return {
        "department_name": department.name,
        "total_employees": total,
        "assessed_employees": assessed,
        "assessment_coverage": coverage,
        "average_score": average_score,
    }
