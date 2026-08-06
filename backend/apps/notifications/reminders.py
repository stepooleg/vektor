"""Напоминания и эскалация просрочек оценки (SPEC §5.4).

- ``send_deadline_reminders``: напоминание оценщикам за N дней до дедлайна
  и в день дедлайна;
- ``send_escalations``: цепочка эскалации — сотрудник → руководитель → HR
  при критической просрочке.

Anti-spam: повторная отправка в течение одного дня не дублируется (по событию
и получателю). Запускается по расписанию Celery beat (nightly).
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

from apps.assessment.models import AssessmentCycle, ReviewerAssignment
from apps.users.models import Role, User

from .models import Notification, NotificationEvent
from .services import dispatch_notification

if TYPE_CHECKING:
    from apps.orgstructure.models import Employee


def _already_sent_today(event: str, recipient_email: str) -> bool:
    """Отправлено ли уже уведомление по событию получателю сегодня (anti-spam)."""
    start = timezone.now() - timedelta(hours=24)
    return Notification.objects.filter(
        event=event,
        recipient_email=recipient_email,
        sent_at__gte=start,
    ).exists()


def send_deadline_reminders(*, days_before: int = 3) -> int:
    """Отправить напоминания оценщикам с дедлайном через ``days_before`` дней.

    SPEC §5.4: за N дней до дедлайна (по умолчанию 3) и в день дедлайна.
    Возвращает число отправленных напоминаний.
    """
    target_date = timezone.now().date() + timedelta(days=days_before)
    sent = 0

    # Активные циклы в статусе приёма оценок.
    cycles = AssessmentCycle.objects.filter(
        deadline=target_date,
        status__in=[
            AssessmentCycle.Status.IN_PROGRESS.value,
            AssessmentCycle.Status.COLLECTING.value,
        ],
    )

    for cycle in cycles:
        # Незавершённые назначения оценщиков.
        assignments = ReviewerAssignment.objects.filter(
            cycle=cycle, completed=False
        ).select_related("reviewer__user", "participant")
        for assignment in assignments:
            reviewer: Employee = assignment.reviewer
            if not reviewer.user_id:
                continue
            if _already_sent_today(
                NotificationEvent.ASSESSMENT_REMINDER.value, reviewer.user.email
            ):
                continue
            dispatch_notification(
                event=NotificationEvent.ASSESSMENT_REMINDER.value,
                user=reviewer.user,
                context={
                    "deadline": cycle.deadline.strftime("%d.%m.%Y") if cycle.deadline else "—",
                    "cycle_name": cycle.name,
                },
            )
            sent += 1
    return sent


def send_escalations(*, critical_overdue_days: int = 7) -> int:
    """Эскалация просрочек (SPEC §5.4): сотрудник → руководитель → HR.

    - просрочка (> дедлайна): напоминание оценщику + руководителю;
    - критическая просрочка (> critical_overdue_days): дополнительно HR.
    Возвращает число отправленных эскалаций.
    """
    today = timezone.now().date()
    critical_threshold = today - timedelta(days=critical_overdue_days)
    sent = 0

    # HR-пользователи (получатели критических эскалаций).
    hr_users = list(User.objects.filter(roles__code=Role.Code.HR.value, is_active=True))

    cycles = AssessmentCycle.objects.filter(
        deadline__lt=today,  # дедлайн прошёл
        status__in=[
            AssessmentCycle.Status.IN_PROGRESS.value,
            AssessmentCycle.Status.COLLECTING.value,
        ],
    )

    for cycle in cycles:
        assignments = ReviewerAssignment.objects.filter(
            cycle=cycle, completed=False
        ).select_related("reviewer__user", "reviewer__manager__user", "participant__employee__user")
        for assignment in assignments:
            reviewer: Employee = assignment.reviewer
            if not reviewer.user_id:
                continue

            # 1) Снова оценщику (просрочка).
            sent += _escalate_to_user(
                reviewer.user, cycle, NotificationEvent.ASSESSMENT_OVERDUE.value
            )

            # 2) Руководителю оценщика.
            manager = reviewer.manager
            if manager and manager.user_id:
                sent += _escalate_to_user(
                    manager.user, cycle, NotificationEvent.ASSESSMENT_OVERDUE.value
                )

            # 3) HR при критической просрочке.
            if cycle.deadline and cycle.deadline <= critical_threshold:
                for hr in hr_users:
                    sent += _escalate_to_user(hr, cycle, NotificationEvent.ASSESSMENT_OVERDUE.value)
    return sent


def _escalate_to_user(user: User, cycle: AssessmentCycle, event: str) -> int:
    """Отправить эскалацию пользователю (с anti-spam). Возвращает 0 или 1."""
    if _already_sent_today(event, user.email):
        return 0
    dispatch_notification(
        event=event,
        user=user,
        context={
            "deadline": cycle.deadline.strftime("%d.%m.%Y") if cycle.deadline else "—",
            "cycle_name": cycle.name,
        },
    )
    return 1
