"""Модель компетенций (SPEC §4).

Конструктор: группы → компетенции → шкала оценки → поведенческие индикаторы.
Привязка модели: корпоративная (общая), ролевая (по должности/грейду),
индивидуальная (конкретному сотруднику).

Готовые шаблоны (SPEC §4.2) загружаются data-миграцией:
- Корпоративные ценности;
- Лидерство и управление;
- Коммуникации и командная работа;
- Профессиональная эффективность.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.orgstructure.models import Employee, Position


class Scale(models.Model):
    """Шкала оценки (SPEC §4.1: например, 1–5 или 1–10, настраивается).

    Хранит границы диапазона; конкретные значения описаны индикаторами
    (``Indicator``) по уровням.
    """

    name = models.CharField(_("Название"), max_length=100, unique=True)
    min_value = models.PositiveSmallIntegerField(_("Минимум"), default=1)
    max_value = models.PositiveSmallIntegerField(_("Максимум"), default=5)

    class Meta:
        verbose_name = _("Шкала")
        verbose_name_plural = _("Шкалы")
        ordering = ["name"]

    def __str__(self) -> str:
        """Название и диапазон шкалы."""
        return f"{self.name} ({self.min_value}–{self.max_value})"

    def contains(self, value: int) -> bool:
        """Попадает ли значение в диапазон шкалы (валидация оценки)."""
        return self.min_value <= value <= self.max_value


class CompetencyGroup(models.Model):
    """Группа компетенций (например, «Лидерство», «Корпоративные ценности»)."""

    name = models.CharField(_("Название"), max_length=200, unique=True)
    description = models.TextField(_("Описание"), blank=True)

    class Meta:
        verbose_name = _("Группа компетенций")
        verbose_name_plural = _("Группы компетенций")
        ordering = ["name"]

    def __str__(self) -> str:
        """Название группы."""
        return self.name


class Competency(models.Model):
    """Индивидуальная компетенция с описанием и шкалой (SPEC §4.1)."""

    name = models.CharField(_("Название"), max_length=200)
    description = models.TextField(_("Описание"), blank=True)
    group = models.ForeignKey(
        CompetencyGroup,
        on_delete=models.CASCADE,
        related_name="competencies",
        verbose_name=_("Группа"),
    )
    scale = models.ForeignKey(
        Scale,
        on_delete=models.PROTECT,
        related_name="competencies",
        verbose_name=_("Шкала"),
    )

    class Meta:
        verbose_name = _("Компетенция")
        verbose_name_plural = _("Компетенции")
        ordering = ["group__name", "name"]
        unique_together = [("group", "name")]

    def __str__(self) -> str:
        """Название компетенции."""
        return self.name


class Indicator(models.Model):
    """Поведенческий индикатор по уровню шкалы (для калибровки оценщиков).

    Описывает ожидаемое поведение на конкретном уровне (``level``) шкалы.
    """

    competency = models.ForeignKey(
        Competency,
        on_delete=models.CASCADE,
        related_name="indicators",
        verbose_name=_("Компетенция"),
    )
    level = models.PositiveSmallIntegerField(_("Уровень шкалы"))
    description = models.TextField(_("Описание поведения"))

    class Meta:
        verbose_name = _("Поведенческий индикатор")
        verbose_name_plural = _("Поведенческие индикаторы")
        ordering = ["competency", "level"]
        unique_together = [("competency", "level")]

    def __str__(self) -> str:
        """Компетенция и уровень."""
        return f"{self.competency.name} — уровень {self.level}"


class CompetencyFramework(models.Model):
    """Модель компетенций (framework) с привязкой (SPEC §4.3).

    Тип привязки:
    - ``corporate`` — общая для всех;
    - ``role`` — для конкретной должности (грейда);
    - ``individual`` — для конкретного сотрудника.
    """

    class Scope(models.TextChoices):
        CORPORATE = "corporate", _("Корпоративная")
        ROLE = "role", _("Ролевая")
        INDIVIDUAL = "individual", _("Индивидуальная")

    name = models.CharField(_("Название модели"), max_length=200)
    scope = models.CharField(
        _("Тип привязки"), max_length=16, choices=Scope.choices, default=Scope.CORPORATE
    )
    competencies = models.ManyToManyField(
        Competency, related_name="frameworks", verbose_name=_("Компетенции"), blank=True
    )
    # Ролевая привязка — к должности.
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="frameworks",
        null=True,
        blank=True,
        verbose_name=_("Должность (для ролевой модели)"),
    )
    # Индивидуальная привязка — к сотруднику.
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="frameworks",
        null=True,
        blank=True,
        verbose_name=_("Сотрудник (для индивидуальной модели)"),
    )

    class Meta:
        verbose_name = _("Модель компетенций")
        verbose_name_plural = _("Модели компетенций")
        ordering = ["name"]

    def __str__(self) -> str:
        """Название модели компетенций."""
        return self.name
