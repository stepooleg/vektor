"""Зона развития сотрудника (SPEC §8.1, используется для автоподбора ИПР).

Зона развития = компетенция, где текущий уровень ниже ожидаемого.
Согласована с apps.assessment.matrix.get_development_zones (Фаза 1, #11).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.competencies.models import Competency


@dataclass(frozen=True)
class DevelopmentZone:
    """Зона развития: компетенция с разрывом текущий vs ожидаемый.

    Атрибуты:
        competency_id: ID компетенции.
        competency: объект Competency (для удобства, опционально).
        current_level: текущий уровень (из оценки).
        expected_level: ожидаемый уровень (по роли/грейду).
    """

    competency_id: int | None = None
    competency: Competency | None = None
    current_level: float = 0.0
    expected_level: int = 0

    def __post_init__(self) -> None:
        """Нормализовать competency_id из competency, если не задан."""
        if self.competency_id is None and self.competency is not None:
            object.__setattr__(self, "competency_id", self.competency.id)
