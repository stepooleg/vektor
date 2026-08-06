"""Матрица компетенций (SPEC §5.1.3).

Сетка «компетенция × уровень» с привязкой ожидаемого уровня к должности.
Сравнение текущего (из оценки) vs ожидаемого; выявление зон развития (ниже
ожидаемого) — основа для автоподбора ИПР (SPEC §8.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apps.competencies.models import Competency
from apps.orgstructure.models import Employee

from .models import ExpectedLevel

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class MatrixRow:
    """Строка матрицы: компетенция, текущий и ожидаемый уровни."""

    competency_id: int
    competency_name: str
    current_level: float
    expected_level: int


@dataclass(frozen=True)
class CompetencyMatrix:
    """Матрица компетенций сотрудника (набор строк)."""

    rows: list[MatrixRow]


def build_matrix(
    employee: Employee,
    *,
    current_levels: dict[int, float],
) -> CompetencyMatrix:
    """Построить матрицу: текущий уровень (из оценки) vs ожидаемый по должности.

    ``current_levels`` — словарь {competency_id: средняя оценка}.
    Ожидаемые уровни берутся из ``ExpectedLevel`` для должности сотрудника.
    """
    expected: dict[int, int] = {
        e.competency_id: e.expected_level
        for e in ExpectedLevel.objects.filter(position=employee.position)
    }

    rows: list[MatrixRow] = []
    for competency in Competency.objects.filter(id__in=set(expected) | set(current_levels)):
        rows.append(
            MatrixRow(
                competency_id=competency.id,
                competency_name=competency.name,
                current_level=current_levels.get(competency.id, 0.0),
                expected_level=expected.get(competency.id, 0),
            )
        )
    rows.sort(key=lambda r: r.competency_name)
    return CompetencyMatrix(rows=rows)


def get_development_zones(matrix: CompetencyMatrix) -> Sequence[MatrixRow]:
    """Зоны развития — строки, где текущий уровень ниже ожидаемого (SPEC §8.1)."""
    return tuple(r for r in matrix.rows if r.current_level < r.expected_level)
