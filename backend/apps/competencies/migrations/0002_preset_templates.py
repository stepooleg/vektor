"""Data-миграция: предустановленные шаблоны компетенций (SPEC §4.2)."""

from __future__ import annotations

from django.db import migrations

# Шаблоны: группа → список компетенций (SPEC §4.2).
TEMPLATES: dict[str, list[str]] = {
    "Корпоративные ценности": [
        "Ориентация на результат",
        "Ответственность и надёжность",
        "Инновационность и открытость новому",
    ],
    "Лидерство и управление": [
        "Стратегическое мышление",
        "Развитие команды и наставничество",
        "Принятие решений в условиях неопределённости",
    ],
    "Коммуникации и командная работа": [
        "Эффективная коммуникация",
        "Сотрудничество и командная работа",
        "Разрешение конфликтов",
    ],
    "Профессиональная эффективность": [
        "Профессиональная экспертиза",
        "Управление задачами и временем",
        "Непрерывное обучение и развитие",
    ],
}


def load_templates(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    """Создать шкалу, группы и компетенции шаблонов (идемпотентно)."""
    Scale = apps.get_model("competencies", "Scale")  # noqa: N806
    CompetencyGroup = apps.get_model("competencies", "CompetencyGroup")  # noqa: N806
    Competency = apps.get_model("competencies", "Competency")  # noqa: N806

    # Шкала 1–5 (дефолт из SPEC §4.1). upsert по имени.
    scale, _ = Scale.objects.get_or_create(
        name="Шкала 1–5",
        defaults={"min_value": 1, "max_value": 5},
    )

    for group_name, competency_names in TEMPLATES.items():
        group, _ = CompetencyGroup.objects.get_or_create(name=group_name)
        for cname in competency_names:
            Competency.objects.get_or_create(
                name=cname, group=group, defaults={"scale": scale}
            )


def reverse_templates(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    """Обратная операция: удалить шаблонные данные (по именам)."""
    Scale = apps.get_model("competencies", "Scale")  # noqa: N806
    CompetencyGroup = apps.get_model("competencies", "CompetencyGroup")  # noqa: N806
    CompetencyGroup.objects.filter(name__in=TEMPLATES.keys()).delete()
    Scale.objects.filter(name="Шкала 1–5").delete()


class Migration(migrations.Migration):
    """Загрузка предустановленных шаблонов компетенций (SPEC §4.2)."""

    dependencies = [
        ("competencies", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(load_templates, reverse_templates),
    ]
