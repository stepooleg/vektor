"""Модели индивидуального плана развития (ИПР) (SPEC §8).

Домен ``idp`` — планы развития сотрудников. Формируется:
1) автоматически из зон развития (компетенции ниже ожидаемого уровня) с подбором
   курсов по привязке к компетенциям (§8.1);
2) правится вручную HR/руководителем (§8.1).

Структура ИПР (§8.2): цели → действия → сроки → ответственный → статус.
Жизненный цикл (§8.3): draft → approved → in_progress → completed.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.competencies.models import Competency
from apps.orgstructure.models import Employee


class DevelopmentPlan(models.Model):
    """Индивидуальный план развития сотрудника (SPEC §8).

    Один план на сотрудника (на период). Содержит цели и действия.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Черновик")
        APPROVED = "approved", _("Согласован")
        IN_PROGRESS = "in_progress", _("В работе")
        COMPLETED = "completed", _("Завершён")

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="development_plans",
        verbose_name=_("Сотрудник"),
    )
    title = models.CharField(_("Название"), max_length=300, default="ИПР")
    status = models.CharField(
        _("Статус"), max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(_("Создан"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Обновлён"), auto_now=True)

    class Meta:
        verbose_name = _("План развития")
        verbose_name_plural = _("Планы развития")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Название плана и сотрудник."""
        return f"{self.title} — {self.employee}"


class DevGoal(models.Model):
    """Цель развития в ИПР с привязкой к компетенции (SPEC §8.2)."""

    plan = models.ForeignKey(
        DevelopmentPlan,
        on_delete=models.CASCADE,
        related_name="goals",
        verbose_name=_("План"),
    )
    competency = models.ForeignKey(
        Competency,
        on_delete=models.PROTECT,
        related_name="dev_goals",
        verbose_name=_("Компетенция"),
    )
    title = models.CharField(_("Цель"), max_length=300)
    description = models.TextField(_("Описание"), blank=True)
    target_level = models.PositiveSmallIntegerField(_("Целевой уровень"), default=4)

    class Meta:
        verbose_name = _("Цель развития")
        verbose_name_plural = _("Цели развития")
        unique_together = [("plan", "competency")]

    def __str__(self) -> str:
        """Цель и компетенция."""
        return f"{self.title} ({self.competency})"


class DevAction(models.Model):
    """Действие по развитию (SPEC §8.2).

    Типы действий: курс, задание, менторство, чтение, практика.
    Статусы: запланировано / в работе / завершено / просрочено.
    """

    class Type(models.TextChoices):
        COURSE = "course", _("Курс")
        TASK = "task", _("Задание")
        MENTORING = "mentoring", _("Менторство")
        READING = "reading", _("Чтение")
        PRACTICE = "practice", _("Практика")

    class Status(models.TextChoices):
        PLANNED = "planned", _("Запланировано")
        IN_PROGRESS = "in_progress", _("В работе")
        COMPLETED = "completed", _("Завершено")
        OVERDUE = "overdue", _("Просрочено")

    goal = models.ForeignKey(
        DevGoal,
        on_delete=models.CASCADE,
        related_name="actions",
        verbose_name=_("Цель"),
    )
    type = models.CharField(_("Тип"), max_length=16, choices=Type.choices)
    title = models.CharField(_("Название действия"), max_length=300)
    # Связь с курсом (для type=course).
    course = models.ForeignKey(
        "lms.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dev_actions",
        verbose_name=_("Курс"),
    )
    # Ответственный/наставник.
    mentor = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mentored_actions",
        verbose_name=_("Ответственный"),
    )
    due_date = models.DateField(_("Срок"), null=True, blank=True)
    status = models.CharField(
        _("Статус"),
        max_length=16,
        choices=Status.choices,
        default=Status.PLANNED,
    )
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)

    class Meta:
        verbose_name = _("Действие развития")
        verbose_name_plural = _("Действия развития")
        ordering = ["goal", "id"]

    def __str__(self) -> str:
        """Действие и цель."""
        return f"{self.title} → {self.goal.title}"
