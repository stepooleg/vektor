"""Тесты audit-log (Test-First, SPEC §12.3, §12.2, issue #33).

Контракты:
- чувствительные действия журналируются (кто/когда/что/target);
- ПДн маскируются в details (нет email в открытом виде);
- доступ к сырым оценкам фиксируется;
- удаление по истечении срока хранения.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLogEntry
from apps.audit.services import log_action, mask_pii, purge_expired_entries
from apps.users.models import User


def _user(email: str) -> User:
    """Создать пользователя."""
    return User.objects.create_user(email=email, password="Strong-Pwd-1")


@pytest.mark.django_db
def test_log_action_creates_entry() -> None:
    """Чувствительное действие журналируется (кто/когда/что/target)."""
    actor = _user("hr@corp.local")

    entry = log_action(
        actor=actor,
        action="assessment.result.view",
        target_type="assessment.cycle",
        target_id="42",
        details={"cycle_name": "Оценка 2026"},
    )

    assert entry.actor_id == actor.id
    assert entry.action == "assessment.result.view"
    assert entry.target_type == "assessment.cycle"
    assert entry.target_id == "42"


@pytest.mark.django_db
def test_mask_pii_redacts_email() -> None:
    """ПДн (email) маскируются в details (SPEC §12.2)."""
    actor = _user("hr@corp.local")

    entry = log_action(
        actor=actor,
        action="export.report",
        target_type="analytics.dashboard",
        target_id="1",
        details={"recipient_email": "alice@corp.local", "note": "выгрузка"},
    )

    # Email маскирован в сохранённых details.
    masked = entry.details
    assert "alice@corp.local" not in str(masked)
    assert masked["recipient_email"] != "alice@corp.local"


@pytest.mark.django_db
def test_raw_score_access_is_logged() -> None:
    """Доступ к сырым оценкам фиксируется в audit (SPEC §6.3, §12.3)."""
    actor = _user("admin@corp.local")

    log_action(
        actor=actor,
        action="assessment.raw.access",
        target_type="assessment.response",
        target_id="100",
        details={"reason": "diagnostic"},
    )

    assert AuditLogEntry.objects.filter(action="assessment.raw.access").exists()


@pytest.mark.django_db
def test_purge_expired_entries() -> None:
    """Удаление записей по истечении срока хранения (SPEC §17 п.3)."""
    actor = _user("u@corp.local")
    # Старая запись (прошло > retention).
    old = log_action(
        actor=actor,
        action="export.report",
        target_type="report",
        target_id="1",
        details={},
    )
    AuditLogEntry.objects.filter(id=old.id).update(created_at=timezone.now() - timedelta(days=2000))
    # Свежая запись.
    log_action(
        actor=actor,
        action="export.report",
        target_type="report",
        target_id="2",
        details={},
    )

    purged = purge_expired_entries(retention_months=60)

    assert purged == 1  # удалена только старая
    assert AuditLogEntry.objects.filter(action="export.report").count() == 1


def test_mask_pii_function() -> None:
    """Функция маскирования redagирует email и телефоны."""
    data = {
        "email": "alice@corp.local",
        "phone": "+7 (999) 123-45-67",
        "safe": "обычный текст",
    }
    masked = mask_pii(data)

    assert masked["email"] != "alice@corp.local"
    assert "alice" not in masked["email"]
    assert masked["phone"] != "+7 (999) 123-45-67"
    assert masked["safe"] == "обычный текст"
