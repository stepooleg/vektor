"""Тесты генерации и редактирования ИПР (Test-First, SPEC §8, issue #23).

Контракты:
- зоны развития определяются (компетенции ниже ожидаемого);
- автоподбор предлагает релевантные курсы по привязке к компетенциям;
- ручная правка: добавление/удаление пунктов;
- статусы ИПР проходят жизненный цикл.
"""

from __future__ import annotations

import pytest

from apps.competencies.models import Competency, CompetencyGroup, Scale
from apps.idp.matrix import DevelopmentZone
from apps.idp.models import DevAction, DevelopmentPlan
from apps.idp.services import (
    add_manual_action,
    generate_idp_from_zones,
    transition_plan,
)
from apps.lms.models import Course, CourseCompetencyLink
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import User


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


def _competency(name: str) -> Competency:
    """Создать компетенцию."""
    scale = Scale.objects.create(name=f"Ш-{name}", min_value=1, max_value=5)
    group = CompetencyGroup.objects.create(name=f"Г-{name}")
    return Competency.objects.create(name=name, group=group, scale=scale)


@pytest.mark.django_db
def test_generate_idp_creates_goals_for_development_zones() -> None:
    """Для каждой зоны развития создаётся цель в ИПР (SPEC §8.1)."""
    emp = _employee("E1", "e1@corp.local")
    c1 = _competency("Лидерство")
    c2 = _competency("Коммуникации")
    zones = [
        DevelopmentZone(competency=c1, current_level=2, expected_level=4),
        DevelopmentZone(competency=c2, current_level=3, expected_level=4),
    ]

    plan = generate_idp_from_zones(employee=emp, zones=zones)

    assert plan.status == DevelopmentPlan.Status.DRAFT.value
    assert plan.goals.count() == 2
    goal_competencies = {g.competency_id for g in plan.goals.all()}
    assert goal_competencies == {c1.id, c2.id}


@pytest.mark.django_db
def test_generate_idp_links_courses_by_competency() -> None:
    """Автоподбор предлагает курсы по привязке к компетенциям (SPEC §8.1)."""
    emp = _employee("E1", "e1@corp.local")
    c1 = _competency("Лидерство")
    course = Course.objects.create(title="Курс по лидерству")
    CourseCompetencyLink.objects.create(course=course, competency=c1)
    zones = [DevelopmentZone(competency=c1, current_level=2, expected_level=4)]

    plan = generate_idp_from_zones(employee=emp, zones=zones)

    goal = plan.goals.get(competency=c1)
    course_actions = goal.actions.filter(type=DevAction.Type.COURSE.value)
    assert course_actions.count() == 1
    first_action = course_actions.first()
    assert first_action is not None
    assert first_action.course_id == course.id


@pytest.mark.django_db
def test_manual_action_added_to_plan() -> None:
    """Ручная правка: добавление пункта в ИПР (SPEC §8.1)."""
    emp = _employee("E1", "e1@corp.local")
    c1 = _competency("К1")
    zones = [DevelopmentZone(competency=c1, current_level=2, expected_level=4)]
    plan = generate_idp_from_zones(employee=emp, zones=zones)
    goal = plan.goals.get()

    add_manual_action(
        goal=goal,
        action_type=DevAction.Type.MENTORING.value,
        title="Менторство с руководителем",
        mentor=emp,
    )

    assert goal.actions.filter(type=DevAction.Type.MENTORING.value).count() == 1


@pytest.mark.django_db
def test_plan_lifecycle_transitions() -> None:
    """Статусы ИПР проходят жизненный цикл (SPEC §8.3)."""
    emp = _employee("E1", "e1@corp.local")
    plan = DevelopmentPlan.objects.create(employee=emp, title="ИПР")

    transition_plan(plan, DevelopmentPlan.Status.APPROVED)
    assert plan.status == DevelopmentPlan.Status.APPROVED.value

    transition_plan(plan, DevelopmentPlan.Status.IN_PROGRESS)
    assert plan.status == DevelopmentPlan.Status.IN_PROGRESS.value

    transition_plan(plan, DevelopmentPlan.Status.COMPLETED)
    assert plan.status == DevelopmentPlan.Status.COMPLETED.value


@pytest.mark.django_db
def test_plan_transition_rejects_skip() -> None:
    """Нельзя перепрыгнуть этап (draft → in_progress запрещён)."""
    emp = _employee("E1", "e1@corp.local")
    plan = DevelopmentPlan.objects.create(employee=emp)

    with pytest.raises(ValueError):
        transition_plan(plan, DevelopmentPlan.Status.IN_PROGRESS)


@pytest.mark.django_db
def test_devaction_status_lifecycle() -> None:
    """Действие можно перевести из planned в completed (SPEC §8.2)."""
    emp = _employee("E1", "e1@corp.local")
    c1 = _competency("К1")
    zones = [DevelopmentZone(competency=c1, current_level=2, expected_level=4)]
    plan = generate_idp_from_zones(employee=emp, zones=zones)
    goal = plan.goals.get()
    # Добавим действие вручную (курсов с привязкой нет).
    action = add_manual_action(
        goal=goal,
        action_type=DevAction.Type.READING.value,
        title="Прочитать книгу",
    )

    action.status = DevAction.Status.COMPLETED.value
    action.save(update_fields=["status"])

    action.refresh_from_db()
    assert action.status == DevAction.Status.COMPLETED.value
