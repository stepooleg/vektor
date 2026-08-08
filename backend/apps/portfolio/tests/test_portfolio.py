"""Тесты портфолио (Test-First, SPEC §6.2, §7.4, issue #29).

Контракты:
- прохождение курса попадает в портфолио (из Фазы 2 #22);
- благодарность попадает в портфолио;
- ручное добавление достижения;
- руководитель может добавлять для подчинённого.
"""

from __future__ import annotations

import pytest

from apps.feedback.models import Praise
from apps.orgstructure.models import Department, Employee, Position
from apps.portfolio.models import PortfolioEntry
from apps.portfolio.services import add_manual_entry
from apps.users.models import Role, User


def _employee(code: str, email: str, *, role: str | None = None) -> Employee:
    """Создать сотрудника (с возможной ролью)."""
    dept = Department.objects.create(code_1c=f"D{code}", name=f"Отдел {code}")
    pos = Position.objects.create(code_1c=f"P{code}", name=f"Должность {code}")
    user = User.objects.create_user(email=email, password="Strong-Pwd-1")
    if role:
        r, _ = Role.objects.get_or_create(code=role, defaults={"name": role})
        user.roles.add(r)
    return Employee.objects.create(
        code_1c=code,
        user=user,
        last_name="И",
        first_name=code,
        department=dept,
        position=pos,
    )


@pytest.mark.django_db
def test_praise_added_to_portfolio() -> None:
    """Благодарность попадает в портфолио получателя (SPEC §6.2)."""
    from apps.portfolio.services import add_praise_to_portfolio

    alice = _employee("A1", "alice@corp.local")
    bob = _employee("B1", "bob@corp.local")
    praise = Praise.objects.create(recipient=alice, sender=bob, message="Спасибо!")

    add_praise_to_portfolio(praise)

    assert PortfolioEntry.objects.filter(
        employee=alice, type=PortfolioEntry.Type.THANK_YOU.value
    ).exists()


@pytest.mark.django_db
def test_manual_entry_added() -> None:
    """Ручное добавление достижения сотрудником (SPEC §6.2)."""
    emp = _employee("E1", "e1@corp.local")

    entry = add_manual_entry(
        employee=emp,
        entry_type=PortfolioEntry.Type.ACHIEVEMENT.value,
        title="Закрыл проект X досрочно",
        description="Сдал на 2 недели раньше срока",
    )

    assert entry.employee_id == emp.id
    assert entry.title == "Закрыл проект X досрочно"


@pytest.mark.django_db
def test_portfolio_feed_filters_by_type() -> None:
    """Лента портфолио фильтруется по типу (SPEC §6.2)."""
    emp = _employee("E1", "e1@corp.local")
    add_manual_entry(employee=emp, entry_type=PortfolioEntry.Type.ACHIEVEMENT.value, title="A1")
    add_manual_entry(employee=emp, entry_type=PortfolioEntry.Type.PROJECT.value, title="P1")

    from apps.portfolio.services import get_portfolio_feed

    achievements = get_portfolio_feed(employee=emp, entry_type="achievement")
    assert achievements.count() == 1
    first = achievements.first()
    assert first is not None
    assert first.title == "A1"
