"""Тесты подчинённости сотрудников (SPEC §2.2 — руководитель видит подчинённых).

``Employee.get_subordinates()`` рекурсивно обходит дерево руководителей:
это основа для RBAC «руководитель видит только свою команду».
"""

from __future__ import annotations

import pytest

from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import User


def _make_employee(code: str, email: str, *, manager: Employee | None = None) -> Employee:
    """Создать сотрудника с минимумом данных."""
    dept = Department.objects.create(code_1c=f"D{code}", name=f"Отдел {code}")
    pos = Position.objects.create(code_1c=f"P{code}", name=f"Должность {code}")
    user = User.objects.create_user(email=email, password="Strong-Pwd-1")
    return Employee.objects.create(
        code_1c=code,
        user=user,
        last_name="Тестов",
        first_name=f"Сотрудник-{code}",
        department=dept,
        position=pos,
        manager=manager,
    )


@pytest.mark.django_db
def test_direct_subordinates() -> None:
    """Прямые подчинённые руководителя."""
    boss = _make_employee("BOSS", "boss@corp.local")
    _make_employee("E1", "e1@corp.local", manager=boss)
    _make_employee("E2", "e2@corp.local", manager=boss)

    direct = boss.get_subordinates(direct_only=True)
    assert {e.code_1c for e in direct} == {"E1", "E2"}


@pytest.mark.django_db
def test_recursive_subordinates() -> None:
    """Рекурсивные подчинённые: вся команда по дереву руководителей."""
    boss = _make_employee("BOSS", "boss@corp.local")
    mid = _make_employee("MID", "mid@corp.local", manager=boss)
    _make_employee("E1", "e1@corp.local", manager=mid)
    _make_employee("E2", "e2@corp.local", manager=mid)
    # Чужой сотрудник — не должен попасть.
    other = _make_employee("OTHER", "other@corp.local")

    all_subs = boss.get_subordinates()
    assert {e.code_1c for e in all_subs} == {"MID", "E1", "E2"}
    assert other.code_1c not in {e.code_1c for e in all_subs}


@pytest.mark.django_db
def test_subordinates_exclude_inactive() -> None:
    """Неактивные (уволенные) сотрудники не входят в подчинённых."""
    boss = _make_employee("BOSS", "boss@corp.local")
    active = _make_employee("E1", "e1@corp.local", manager=boss)
    fired = _make_employee("E2", "e2@corp.local", manager=boss)
    fired.is_active = False
    fired.save(update_fields=["is_active"])

    subs = boss.get_subordinates()
    codes = {e.code_1c for e in subs}
    assert active.code_1c in codes
    assert fired.code_1c not in codes
