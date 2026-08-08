"""Тесты непрерывной обратной связи (Test-First, SPEC §6.1, §6.3, issue #28).

Контракты:
- отправка благодарности (публично/приватно);
- анонимная ОС не раскрывает отправителя;
- запрос ОС создаёт задачу получателю (pending);
- права на просмотр публичной/приватной благодарности.
"""

from __future__ import annotations

import pytest

from apps.feedback.models import FeedbackRequest, Praise
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


@pytest.mark.django_db
def test_send_public_praise() -> None:
    """Отправка публичной благодарности (SPEC §6.1)."""
    alice = _employee("A1", "alice@corp.local")
    bob = _employee("B1", "bob@corp.local")

    praise = Praise.objects.create(
        recipient=alice,
        sender=bob,
        message="Спасибо за помощь!",
        is_public=True,
        is_anonymous=False,
    )

    assert praise.is_public is True
    assert praise.sender_id == bob.id


@pytest.mark.django_db
def test_send_private_praise() -> None:
    """Приватная благодарность видна только получателю и отправителю."""
    alice = _employee("A1", "alice@corp.local")
    bob = _employee("B1", "bob@corp.local")

    praise = Praise.objects.create(
        recipient=alice,
        sender=bob,
        message="Личное спасибо",
        is_public=False,
        is_anonymous=False,
    )

    assert praise.is_public is False


@pytest.mark.django_db
def test_anonymous_praise_hides_sender() -> None:
    """Анонимная благодарность не раскрывает отправителя (SPEC §6.3)."""
    alice = _employee("A1", "alice@corp.local")
    bob = _employee("B1", "bob@corp.local")

    praise = Praise.objects.create(
        recipient=alice,
        sender=bob,
        message="Анонимная благодарность",
        is_anonymous=True,
    )

    assert praise.is_anonymous is True
    # Сервис-функция для безопасного отображения скрывает отправителя.
    from apps.feedback.services import safe_praise_sender

    assert safe_praise_sender(praise) is None  # аноним → None


@pytest.mark.django_db
def test_feedback_request_creates_pending_task() -> None:
    """Запрос ОС создаёт задачу получателю со статусом pending (SPEC §6.1)."""
    alice = _employee("A1", "alice@corp.local")
    bob = _employee("B1", "bob@corp.local")

    req = FeedbackRequest.objects.create(
        requester=alice,
        recipient=bob,
        message="Дай ОС по проекту X",
    )

    assert req.status == FeedbackRequest.Status.PENDING.value
    # Получатель видит запрос у себя.
    assert FeedbackRequest.objects.filter(recipient=bob).count() == 1


@pytest.mark.django_db
def test_feedback_request_answered() -> None:
    """Запрос ОС можно перевести в answered."""
    alice = _employee("A1", "alice@corp.local")
    bob = _employee("B1", "bob@corp.local")
    req = FeedbackRequest.objects.create(requester=alice, recipient=bob)

    from apps.feedback.services import mark_request_answered

    mark_request_answered(req)

    req.refresh_from_db()
    assert req.status == FeedbackRequest.Status.ANSWERED.value
    assert req.answered_at is not None


@pytest.mark.django_db
def test_visible_praises_filter() -> None:
    """Лента: только публичные благодарности (SPEC §6.1)."""
    alice = _employee("A1", "alice@corp.local")
    bob = _employee("B1", "bob@corp.local")
    carol = _employee("C1", "carol@corp.local")
    Praise.objects.create(recipient=alice, sender=bob, message="public", is_public=True)
    Praise.objects.create(recipient=alice, sender=carol, message="private", is_public=False)

    from apps.feedback.services import get_public_feed

    feed = get_public_feed()
    assert feed.count() == 1
    first = feed.first()
    assert first is not None
    assert first.message == "public"
