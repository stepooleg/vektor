"""Модели оргструктуры (SPEC §3, §10.1).

Домен ``orgstructure`` — единый источник правды по составу компании:
дерево подразделений, должности и сотрудники. Данные синхронизируются из 1С:ЗУП
односторонне (см. ``services.py`` и Celery-задачу).

Связь с пользователем: один ``Employee`` ↔ один ``User`` (учётная запись).
Связь «руководитель — подчинённый» реализована через:
- ``Employee.manager`` — прямой руководитель (для оценки 360°, SPEC §3.2);
- ``Department.head`` — руководитель подразделения.

Обработка кадровых изменений (SPEC §3.4):
- увольнение → ``is_active=False`` (архив, история сохраняется);
- перевод → смена department/position с датой;
- отпуск/декрет → ``assessment_eligible=False`` на период.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.users.models import User


class Department(models.Model):
    """Подразделение (дерево отделов, SPEC §3.2).

    Иерархия через ``parent`` (self-FK). ``code_1c`` — стабильный ключ
    синхронизации с 1С:ЗУП (идемпотентность upsert).
    """

    name = models.CharField(_("Название"), max_length=255)
    code_1c = models.CharField(
        _("Код 1С:ЗУП"),
        max_length=64,
        unique=True,
        help_text=_("Стабильный идентификатор для синхронизации с 1С."),
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
        verbose_name=_("Родительское подразделение"),
    )
    head = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        related_name="headed_departments",
        null=True,
        blank=True,
        verbose_name=_("Руководитель подразделения"),
    )
    is_active = models.BooleanField(_("Активно"), default=True)
    source_updated_at = models.DateTimeField(_("Изменено в 1С"), null=True, blank=True)

    class Meta:
        verbose_name = _("Подразделение")
        verbose_name_plural = _("Подразделения")
        ordering = ["name"]

    def __str__(self) -> str:
        """Название подразделения."""
        return self.name


class Position(models.Model):
    """Должность/штатная единица (SPEC §3.2)."""

    name = models.CharField(_("Название должности"), max_length=255)
    code_1c = models.CharField(
        _("Код 1С:ЗУП"),
        max_length=64,
        unique=True,
        help_text=_("Стабильный идентификатор для синхронизации с 1С."),
    )
    source_updated_at = models.DateTimeField(_("Изменено в 1С"), null=True, blank=True)

    class Meta:
        verbose_name = _("Должность")
        verbose_name_plural = _("Должности")
        ordering = ["name"]

    def __str__(self) -> str:
        """Название должности."""
        return self.name


class OneCSyncState(models.Model):
    """Cursor последней успешной pull-синхронизации с 1С:ЗУП."""

    last_successful_at = models.DateTimeField(
        _("Последняя успешная синхронизация"), null=True, blank=True
    )

    def __str__(self) -> str:
        """Текущий cursor синхронизации для диагностики."""
        return self.last_successful_at.isoformat() if self.last_successful_at else "не запускалась"


class Employee(models.Model):
    """Сотрудник (ФИО, табельный, должность, подразделение, руководитель).

    Связан с ``User`` один-к-одному (учётная запись для входа). ПДн сотрудника
    (ФИО, табельный номер) — комплаенс 152-ФЗ, SPEC §12.

    ``code_1c`` (табельный номер) — ключ синхронизации с 1С.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employee",
        verbose_name=_("Учётная запись"),
    )
    code_1c = models.CharField(
        _("Табельный номер (1С)"),
        max_length=64,
        unique=True,
        help_text=_("Стабильный идентификатор сотрудника в 1С:ЗУП."),
    )

    # ФИО храним здесь отдельно от User: 1С — источник правды по сотрудникам.
    last_name = models.CharField(_("Фамилия"), max_length=128)
    first_name = models.CharField(_("Имя"), max_length=128)
    middle_name = models.CharField(_("Отчество"), max_length=128, blank=True)

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name=_("Подразделение"),
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name=_("Должность"),
    )
    manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="subordinates",
        null=True,
        blank=True,
        verbose_name=_("Непосредственный руководитель"),
        help_text=_("Для оценки 360° (SPEC §3.2)."),
    )

    hire_date = models.DateField(_("Дата приёма"), null=True, blank=True)
    is_active = models.BooleanField(_("Работает"), default=True)
    # Отпуск/декрет: временно не участвует в оценке (SPEC §3.4).
    assessment_eligible = models.BooleanField(
        _("Участвует в оценке"),
        default=True,
    )
    source_updated_at = models.DateTimeField(_("Изменено в 1С"), null=True, blank=True)

    class Meta:
        verbose_name = _("Сотрудник")
        verbose_name_plural = _("Сотрудники")
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        """ФИО сотрудника."""
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(p for p in parts if p).strip()

    @property
    def full_name(self) -> str:
        """Полное ФИО сотрудника."""
        return str(self)

    def get_subordinates(self, *, direct_only: bool = False) -> models.QuerySet[Employee]:
        """Подчинённые сотрудника.

        По умолчанию — все подчинённые рекурсивно (по дереву руководителей),
        что нужно для «руководитель видит всю свою команду» (SPEC §2.2).
        При ``direct_only=True`` — только прямые подчинённые.
        """
        qs = Employee.objects.filter(is_active=True)
        if direct_only:
            return qs.filter(manager=self)
        # Рекурсивный обход: собираем всех, чья цепочка руководителей
        # проходит через self. Реализация через итеративное расширение множества
        # (PostgreSQL RECURSIVE CTE добавим при росте дерева — см. TODO).
        ids: set[int] = {self.id}
        changed = True
        while changed:
            new = set(qs.filter(manager_id__in=ids).values_list("id", flat=True)) - ids
            if not new:
                changed = False
            ids |= new
        return qs.filter(id__in=ids).exclude(id=self.id)
