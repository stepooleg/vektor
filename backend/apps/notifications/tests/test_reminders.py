"""Тесты напоминаний и эскалации просрочек (Test-First, SPEC §5.4, issue #13).

Контракты:
- напоминание оценщику за N дней до дедлайна (по умолчанию 3);
- напоминание в день дедлайна;
- эскалация руководителю при просрочке;
- эскалация HR при критической просрочке;
- anti-spam: повторная отправка не чаще заданного интервала.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.assessment.models import (
    AssessmentCycle,
    Participant,
    ReviewerAssignment,
)
from apps.notifications.reminders import (
    send_deadline_reminders,
    send_escalations,
)
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import Role, User


def _setup_cycle_with_reviewer(
    *, deadline_offset_days: int, completed: bool = False
) -> tuple[AssessmentCycle, ReviewerAssignment, Employee, Employee]:
    """Создать цикл с участником и оценщиком-руководителем.

    deadline_offset_days: дедлайн через N дней от сегодня (отрицательное — просрочка).
    """
    dept = Department.objects.create(code_1c="D1", name="Отдел")
    pos = Position.objects.create(code_1c="P1", name="Должность")
    hr_role = Role.objects.create(code=Role.Code.HR.value, name="HR")
    hr_user = User.objects.create_user(email="hr@corp.local", password="Strong-Pwd-1")
    hr_user.roles.add(hr_role)

    boss_user = User.objects.create_user(email="boss@corp.local", password="Strong-Pwd-1")
    boss = Employee.objects.create(
        code_1c="BOSS",
        user=boss_user,
        last_name="Босс",
        first_name="И",
        department=dept,
        position=pos,
    )
    emp_user = User.objects.create_user(email="emp@corp.local", password="Strong-Pwd-1")
    emp = Employee.objects.create(
        code_1c="E1",
        user=emp_user,
        last_name="Сотр",
        first_name="И",
        department=dept,
        position=pos,
        manager=boss,
    )

    cycle = AssessmentCycle.objects.create(
        name="Цикл",
        status=AssessmentCycle.Status.IN_PROGRESS.value,
        deadline=timezone.now().date() + timedelta(days=deadline_offset_days),
    )
    participant = Participant.objects.create(cycle=cycle, employee=emp)
    assignment = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=boss,
        group=ReviewerAssignment.Group.MANAGER.value,
        completed=completed,
    )
    return cycle, assignment, emp, boss


@pytest.mark.django_db
def test_reminder_sent_3_days_before_deadline() -> None:
    """Напоминание шлётся за N дней до дедлайна (по умолчанию 3, SPEC §5.4)."""
    cycle, assignment, emp, boss = _setup_cycle_with_reviewer(deadline_offset_days=3)

    send_deadline_reminders(days_before=3)

    # Должно быть напоминание оценщику (boss).
    from django.core import mail

    assert any("boss@corp.local" in m.to[0] for m in mail.outbox)


@pytest.mark.django_db
def test_reminder_sent_on_deadline_day() -> None:
    """Напоминание в день дедлайна."""
    _setup_cycle_with_reviewer(deadline_offset_days=0)

    send_deadline_reminders(days_before=0)

    from django.core import mail

    assert len(mail.outbox) >= 1


@pytest.mark.django_db
def test_escalation_to_manager_on_overdue() -> None:
    """Эскалация руководителю при просрочке (SPEC §5.4)."""
    cycle, assignment, emp, boss = _setup_cycle_with_reviewer(
        deadline_offset_days=-2, completed=False
    )

    send_escalations(critical_overdue_days=7)

    from django.core import mail

    recipients = [m.to[0] for m in mail.outbox]
    # Эскалация руководителю просрочившего (boss — руководитель emp).
    assert "boss@corp.local" in recipients


@pytest.mark.django_db
def test_escalation_to_hr_on_critical_overdue() -> None:
    """Эскалация HR при критической просрочке (SPEC §5.4)."""
    _setup_cycle_with_reviewer(deadline_offset_days=-10, completed=False)

    send_escalations(critical_overdue_days=7)

    from django.core import mail

    recipients = [m.to[0] for m in mail.outbox]
    assert "hr@corp.local" in recipients


@pytest.mark.django_db
def test_no_double_reminder_within_interval() -> None:
    """Anti-spam: повторная отправка не чаще заданного интервала."""
    cycle, assignment, emp, boss = _setup_cycle_with_reviewer(deadline_offset_days=3)

    send_deadline_reminders(days_before=3)
    from django.core import mail

    first_count = len(mail.outbox)
    assert first_count >= 1

    # Повторный прогон в тот же день — не должен дублировать.
    send_deadline_reminders(days_before=3)
    assert len(mail.outbox) == first_count
