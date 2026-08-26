from __future__ import annotations

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assessment", "0002_expectedlevel"),
        ("idp", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="devgoal",
            name="source_cycle",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="generated_dev_goals",
                to="assessment.assessmentcycle",
                verbose_name="Источник: цикл оценки",
            ),
        ),
        migrations.AddField(
            model_name="devgoal",
            name="source_current_level",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=4,
                null=True,
                verbose_name="Источник: текущий уровень",
            ),
        ),
        migrations.AddField(
            model_name="devaction",
            name="progress_percent",
            field=models.PositiveSmallIntegerField(
                default=0,
                validators=[django.core.validators.MaxValueValidator(100)],
                verbose_name="Прогресс, %",
            ),
        ),
    ]
