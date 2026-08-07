"""Тесты канала уведомлений и шаблонов (Test-First, SPEC §13, issue #14).

Контракты:
- EmailChannel рендерит сообщение из шаблона;
- отправка через Celery с retry при ошибке SMTP;
- пользовательские настройки фильтруют события (SPEC §13.3);
- ручная рассылка идёт только выбранной аудитории (SPEC §13.3).
"""

from __future__ import annotations

import pytest
from django.core import mail

from apps.notifications.channels import EmailChannel
from apps.notifications.models import (
    Notification,
    NotificationEvent,
    UserNotificationPreference,
)
from apps.notifications.services import (
    NotificationError,
    dispatch_notification,
    render_notification,
    send_manual_broadcast,
)
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import User


def _make_employee(code: str, email: str) -> tuple[Employee, User]:
    """Создать сотрудника с пользователем."""
    dept = Department.objects.create(code_1c=f"D{code}", name=f"Отдел {code}")
    pos = Position.objects.create(code_1c=f"P{code}", name=f"Должность {code}")
    user = User.objects.create_user(email=email, password="Strong-Pwd-1")
    emp = Employee.objects.create(
        code_1c=code,
        user=user,
        last_name="И",
        first_name=code,
        department=dept,
        position=pos,
    )
    return emp, user


@pytest.mark.django_db
def test_email_channel_renders_and_sends() -> None:
    """EmailChannel рендерит письмо и отправляет через SMTP (locmem в тестах)."""
    channel = EmailChannel()
    notif = Notification.objects.create(
        recipient_email="alice@corp.local",
        recipient_name="Анна",
        event=NotificationEvent.ASSESSMENT_ASSIGNED.value,
        subject="Оценка 360°",
        body="Коллеги ждут вашей обратной связи до 20 августа.",
    )

    channel.send(notif)

    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.to == ["alice@corp.local"]
    assert sent.subject == "Оценка 360°"
    assert "Коллеги ждут" in sent.body
    assert notif.sent_at is not None


@pytest.mark.django_db
def test_render_notification_uses_tone_of_voice() -> None:
    """Рендер сообщения следует тону голоса (BRANDBOOK §9 — поддерживающий)."""
    notif = render_notification(
        event=NotificationEvent.ASSESSMENT_OVERDUE.value,
        recipient_email="bob@corp.local",
        recipient_name="Борис",
        context={"deadline": "20 августа", "cycle_name": "Оценка 2026"},
    )

    # Тон голоса: поддерживающий, с конкретным шагом, без давления.
    assert "20 августа" in notif.body
    assert "разви" in notif.body.lower() or "обратной связи" in notif.body.lower()


@pytest.mark.django_db
def test_dispatch_filters_by_user_preference() -> None:
    """Пользовательские настройки фильтруют события (SPEC §13.3)."""
    _, user = _make_employee("E1", "e1@corp.local")
    # Пользователь отключил напоминания о дедлайне.
    UserNotificationPreference.objects.create(
        user=user,
        event=NotificationEvent.ASSESSMENT_REMINDER.value,
        email_enabled=False,
    )

    dispatch_notification(
        event=NotificationEvent.ASSESSMENT_REMINDER.value,
        user=user,
        context={"deadline": "завтра", "cycle_name": "Оценка"},
    )

    # Отправки не было — событие отфильтровано настройками.
    assert len(mail.outbox) == 0
    # Notification не создан (или создан со статусом skipped).
    assert (
        not Notification.objects.filter(
            recipient_email="e1@corp.local",
            event=NotificationEvent.ASSESSMENT_REMINDER.value,
        )
        .filter(sent_at__isnull=False)
        .exists()
    )


@pytest.mark.django_db
def test_send_manual_broadcast_to_audience() -> None:
    """Ручная рассылка идёт только выбранной аудитории (SPEC §13.3)."""
    emp1, _ = _make_employee("E1", "e1@corp.local")
    emp2, _ = _make_employee("E2", "e2@corp.local")
    _ = _make_employee("E3", "e3@corp.local")  # не входит в аудиторию

    sent = send_manual_broadcast(
        subject="Важное сообщение",
        body="Тест рассылки",
        audience_employee_ids=[emp1.id, emp2.id],
        sender=None,
    )

    assert sent == 2
    recipients = {m.to[0] for m in mail.outbox}
    assert recipients == {"e1@corp.local", "e2@corp.local"}


@pytest.mark.django_db
def test_dispatch_raises_on_smtp_failure() -> None:
    """При ошибке отправки — NotificationError (retry будет на уровне Celery)."""
    _, user = _make_employee("E1", "bad@corp.local")

    with pytest.raises(NotificationError):
        dispatch_notification(
            event=NotificationEvent.ASSESSMENT_ASSIGNED.value,
            user=user,
            context={},
            force_simulate_failure=True,
        )
