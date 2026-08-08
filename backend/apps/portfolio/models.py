"""Модели портфолио сотрудника (SPEC §6.2, §7.4).

Журнал достижений: пройденные курсы, результаты, благодарности, завершённые
проекты. Пройденные курсы записываются сюда автоматически (SPEC §7.4).

Минимальная модель для Фазы 2 (#22); полный портфолио — Фаза 3 (#29).
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class PortfolioEntry(models.Model):
    """Запись в журнале достижений сотрудника (SPEC §6.2).

    Тип ``course_passed`` создаётся автоматически при завершении курса (§7.4).
    """

    class Type(models.TextChoices):
        COURSE_PASSED = "course_passed", _("Курс пройдён")
        ACHIEVEMENT = "achievement", _("Достижение")
        PROJECT = "project", _("Проект/кейс")
        THANK_YOU = "thank_you", _("Благодарность")

    employee = models.ForeignKey(
        "orgstructure.Employee",
        on_delete=models.CASCADE,
        related_name="portfolio_entries",
        verbose_name=_("Сотрудник"),
    )
    type = models.CharField(_("Тип"), max_length=16, choices=Type.choices)
    title = models.CharField(_("Заголовок"), max_length=300)
    description = models.TextField(_("Описание"), blank=True)
    created_at = models.DateTimeField(_("Добавлено"), auto_now_add=True)

    class Meta:
        verbose_name = _("Запись портфолио")
        verbose_name_plural = _("Записи портфолио")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Заголовок записи."""
        return self.title
