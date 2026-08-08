"""Тесты push-канала и подписок (Test-First, SPEC §10.4, issue #24).

Контракты:
- подписка создаётся/деактивируется;
- push отправляется активным подпискам пользователя;
- dispatch_notification использует push-канал при активной подписке.
"""

from __future__ import annotations

from unittest import mock

import pytest

from apps.notifications.channels import PushChannel
from apps.notifications.models import NotificationEvent, PushSubscription
from apps.notifications.services import dispatch_notification
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import User


def _user(email: str) -> User:
    """Создать пользователя."""
    return User.objects.create_user(email=email, password="Strong-Pwd-1")


def _sub(user: User, *, endpoint: str = "https://push.example/sub/1") -> PushSubscription:
    """Создать push-подписку."""
    return PushSubscription.objects.create(
        user=user,
        endpoint=endpoint,
        p256dh="p256dh-key",
        auth="auth-key",
    )


@pytest.mark.django_db
def test_subscription_created() -> None:
    """Подписка создаётся со статусом active."""
    user = _user("u@corp.local")
    sub = _sub(user)

    assert sub.is_active is True
    assert user.push_subscriptions.count() == 1


@pytest.mark.django_db
def test_subscription_deactivated() -> None:
    """Подписку можно деактивировать (отписка)."""
    user = _user("u@corp.local")
    sub = _sub(user)

    sub.is_active = False
    sub.save(update_fields=["is_active"])

    assert user.push_subscriptions.filter(is_active=True).count() == 0


@pytest.mark.django_db
def test_push_sent_to_active_subscriptions() -> None:
    """Push отправляется активным подпискам пользователя (pywebpush мокается)."""
    user = _user("u@corp.local")
    _sub(user, endpoint="https://push.example/sub/1")
    _sub(user, endpoint="https://push.example/sub/2")
    # Неактивная — не должна получить.
    inactive = _sub(user, endpoint="https://push.example/sub/3")
    inactive.is_active = False
    inactive.save(update_fields=["is_active"])

    channel = PushChannel()
    payload = {"title": "Тест", "body": "Push-уведомление"}

    with mock.patch("apps.notifications.channels.webpush") as mocked:
        channel.send_to_user(user, payload)

    # webpush вызван дважды (две активные подписки).
    assert mocked.call_count == 2


@pytest.mark.django_db
def test_dispatch_uses_push_channel_when_subscribed() -> None:
    """dispatch_notification отправляет push при активной подписке (§13.1)."""
    dept = Department.objects.create(code_1c="D1", name="Отдел")
    pos = Position.objects.create(code_1c="P1", name="Должность")
    user = User.objects.create_user(email="u@corp.local", password="Strong-Pwd-1")
    Employee.objects.create(
        code_1c="E1",
        user=user,
        last_name="И",
        first_name="А",
        department=dept,
        position=pos,
    )
    _sub(user)

    with (
        mock.patch("apps.notifications.channels.webpush") as mocked_push,
        mock.patch("apps.notifications.channels.send_mail") as mocked_mail,
    ):
        dispatch_notification(
            event=NotificationEvent.ASSESSMENT_ASSIGNED.value,
            user=user,
            context={"cycle_name": "Оценка 2026", "deadline": "20.08"},
        )

    # Push отправлен активной подписке.
    assert mocked_push.call_count >= 1
    # Email тоже отправлен (оба канала, §13.1).
    assert mocked_mail.call_count >= 1
