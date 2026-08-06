"""Тест предустановленных шаблонов компетенций (SPEC §4.2, issue #9).

Шаблоны загружаются data-миграцией. После применения должны быть:
- 4 группы (ценности, лидерство, коммуникации, проф.эффективность);
- компетенции в каждой;
- шкала 1–5.
"""

from __future__ import annotations

import pytest

from apps.competencies.models import Competency, CompetencyGroup, Scale

EXPECTED_GROUPS = {
    "Корпоративные ценности",
    "Лидерство и управление",
    "Коммуникации и командная работа",
    "Профессиональная эффективность",
}


@pytest.mark.django_db
def test_preset_templates_present_after_migration() -> None:
    """После data-миграции присутствуют 4 шаблонные группы с компетенциями."""
    group_names = set(CompetencyGroup.objects.values_list("name", flat=True))
    assert EXPECTED_GROUPS.issubset(
        group_names
    ), f"Не хватает групп: {EXPECTED_GROUPS - group_names}"

    # В каждой шаблонной группе есть хотя бы одна компетенция.
    for name in EXPECTED_GROUPS:
        group = CompetencyGroup.objects.get(name=name)
        assert group.competencies.exists(), f"Группа «{name}» без компетенций"

    # Должна быть шкала 1–5, привязанная к компетенциям.
    assert Scale.objects.exists()
    assert Competency.objects.exists()


@pytest.mark.django_db
def test_preset_scale_is_1_to_5() -> None:
    """Шаблонная шкала — 1–5 (SPEC §4.1 пример)."""
    scale = Scale.objects.filter(min_value=1, max_value=5).first()
    assert scale is not None
    assert scale.contains(1)
    assert scale.contains(5)
