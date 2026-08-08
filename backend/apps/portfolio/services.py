"""Сервисы портфолио (SPEC §6.2, issue #29).

- ``add_praise_to_portfolio``: автопополнение из благодарностей;
- ``add_manual_entry``: ручное добавление достижения;
- ``get_portfolio_feed``: лента с фильтром по типу.

Курсы пишутся сюда из lms.services (Фаза 2 #22, type=course_passed).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import PortfolioEntry

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.feedback.models import Praise
    from apps.orgstructure.models import Employee


def add_praise_to_portfolio(praise: Praise) -> PortfolioEntry:
    """Записать благодарность в портфолио получателя (SPEC §6.2)."""
    entry, _ = PortfolioEntry.objects.get_or_create(
        employee=praise.recipient,
        type=PortfolioEntry.Type.THANK_YOU.value,
        title=f"Благодарность: {praise.message[:80]}",
        defaults={"description": praise.message},
    )
    return entry


def add_manual_entry(
    *,
    employee: Employee,
    entry_type: str,
    title: str,
    description: str = "",
) -> PortfolioEntry:
    """Ручное добавление достижения в портфолио (SPEC §6.2)."""
    return PortfolioEntry.objects.create(
        employee=employee,
        type=entry_type,
        title=title,
        description=description,
    )


def get_portfolio_feed(
    *,
    employee: Employee,
    entry_type: str | None = None,
) -> QuerySet[PortfolioEntry]:
    """Лента портфолио сотрудника с фильтром по типу (SPEC §6.2)."""
    qs = PortfolioEntry.objects.filter(employee=employee)
    if entry_type:
        qs = qs.filter(type=entry_type)
    return qs.order_by("-created_at")
