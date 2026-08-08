"""Сервисы уведомлений (SPEC §13).

- ``render_notification`` — текст по событию (тон голоса BRANDBOOK §9);
- ``dispatch_notification`` — создать + отправить (с учётом настроек пользователя);
- ``send_manual_broadcast`` — ручная рассылка выбранной аудитории (SPEC §13.3).

Отправка происходит синхронно в тестах; в проде оборачивается Celery-задачей
(см. tasks.py) с retry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .channels import get_email_channel
from .models import Notification, NotificationEvent, UserNotificationPreference

if TYPE_CHECKING:
    from apps.orgstructure.models import Employee
    from apps.users.models import User


class NotificationError(RuntimeError):
    """Ошибка отправки уведомления (для retry на уровне Celery)."""


# Шаблоны текстов по событиям (тон голоса — BRANDBOOK §9: поддерживающий, ясный).
_SUBJECT_TEMPLATES: dict[str, str] = {
    NotificationEvent.ASSESSMENT_ASSIGNED.value: "Вас просят оценить коллег",
    NotificationEvent.ASSESSMENT_REMINDER.value: "Напоминание: дедлайн оценки {deadline}",
    NotificationEvent.ASSESSMENT_OVERDUE.value: "Дедлайн оценки «{cycle_name}» прошёл",
    NotificationEvent.ASSESSMENT_RESULT.value: "Готов итоговый отчёт по циклу «{cycle_name}»",
    NotificationEvent.FEEDBACK_RECEIVED.value: "Вам отправили обратную связь",
    NotificationEvent.COURSE_ASSIGNED.value: "Вам назначен курс",
    NotificationEvent.COURSE_RESULT.value: "Результат проверки задания по курсу «{course_name}»",
    NotificationEvent.MANUAL_BROADCAST.value: "Сообщение от HR",
}

_BODY_TEMPLATES: dict[str, str] = {
    NotificationEvent.ASSESSMENT_ASSIGNED.value: (
        "{name}, коллеги ждут вашей обратной связи по оценке «{cycle_name}». "
        "Пожалуйста, уделите этому время — это поможет развитию команды."
    ),
    NotificationEvent.ASSESSMENT_REMINDER.value: (
        "{name}, напоминаем: дедлайн оценки «{cycle_name}» — {deadline}. "
        "Пожалуйста, завершите — обратная связь важна для коллег."
    ),
    NotificationEvent.ASSESSMENT_OVERDUE.value: (
        "{name}, дедлайн оценки «{cycle_name}» ({deadline}) прошёл. "
        "Пожалуйста, завершите оценку — это поможет коллеге развиваться. "
        "Следующий шаг: откройте раздел «Оценка» и заполните форму."
    ),
    NotificationEvent.ASSESSMENT_RESULT.value: (
        "{name}, готов итоговый отчёт по циклу «{cycle_name}». "
        "Посмотрите результаты в личном кабинете."
    ),
    NotificationEvent.FEEDBACK_RECEIVED.value: (
        "{name}, вам отправили обратную связь. Откройте раздел «Обратная связь»."
    ),
    NotificationEvent.COURSE_ASSIGNED.value: (
        "{name}, вам назначен новый курс. Начните обучение в разделе «Обучение»."
    ),
    NotificationEvent.COURSE_RESULT.value: (
        "{name}, ваше практическое задание по курсу «{course_name}» {result}. "
        "Подробности — в разделе «Обучение»."
    ),
    NotificationEvent.MANUAL_BROADCAST.value: "{name}, {body}",
}


@dataclass(frozen=True)
class RenderedNotification:
    """Результат рендера (тема + тело)."""

    subject: str
    body: str


def render_notification(
    *,
    event: str,
    recipient_email: str,
    recipient_name: str,
    context: dict[str, str],
) -> Notification:
    """Создать ``Notification`` с отрендеренными темой/телом по событию.

    ``context`` подставляется в шаблоны ({name}, {deadline}, {cycle_name}, {body}).
    """
    name = recipient_name or recipient_email.split("@")[0]
    fmt_ctx = {"name": name, "deadline": "—", "cycle_name": "—", "body": "", **context}

    subject_tpl = _SUBJECT_TEMPLATES.get(event, "Уведомление Vektor")
    body_tpl = _BODY_TEMPLATES.get(event, "{name}, проверьте приложение Vektor.")

    return Notification.objects.create(
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        event=event,
        subject=subject_tpl.format(**fmt_ctx),
        body=body_tpl.format(**fmt_ctx),
    )


def _is_enabled_for_user(user: User, event: str) -> bool:
    """Разрешено ли событие по настройкам пользователя (SPEC §13.3)."""
    pref = UserNotificationPreference.objects.filter(user=user, event=event).first()
    if pref is None:
        return True  # по умолчанию включено
    return pref.email_enabled


def dispatch_notification(
    *,
    event: str,
    user: User,
    context: dict[str, str],
    force_simulate_failure: bool = False,
) -> Notification | None:
    """Создать и отправить уведомление пользователю с учётом его настроек.

    Возвращает ``Notification`` (отправленный) или ``None``, если событие
    отфильтровано настройками пользователя.
    """
    if not _is_enabled_for_user(user, event):
        return None

    notif = render_notification(
        event=event,
        recipient_email=user.email,
        recipient_name=user.get_full_name() or user.email,
        context=context,
    )

    if force_simulate_failure:
        notif.mark_failed("Имитация ошибки SMTP (тест)")
        raise NotificationError("Имитация ошибки SMTP")

    channel = get_email_channel()
    channel.send(notif)
    return notif


def send_manual_broadcast(
    *,
    subject: str,
    body: str,
    audience_employee_ids: list[int],
    sender: User | None,
) -> int:
    """Ручная рассылка выбранной аудитории сотрудников (SPEC §13.3).

    Ручные рассылки всегда проходят (игнорируют индивидуальные отключения).
    Возвращает число отправленных уведомлений.
    """
    from apps.orgstructure.models import Employee

    employees: list[Employee] = list(
        Employee.objects.filter(id__in=audience_employee_ids, is_active=True).select_related("user")
    )
    sent_count = 0
    channel = get_email_channel()
    for emp in employees:
        if not emp.user_id:
            continue
        notif = Notification.objects.create(
            recipient_email=emp.user.email,
            recipient_name=emp.full_name,
            event=NotificationEvent.MANUAL_BROADCAST.value,
            subject=subject,
            body=body,
        )
        channel.send(notif)
        sent_count += 1
    return sent_count
