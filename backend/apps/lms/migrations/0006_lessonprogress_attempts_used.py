from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lms", "0005_certificate"),
    ]

    operations = [
        migrations.AddField(
            model_name="lessonprogress",
            name="attempts_used",
            field=models.PositiveSmallIntegerField(default=0, verbose_name="Использовано попыток"),
        ),
    ]
