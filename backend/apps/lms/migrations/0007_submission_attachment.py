from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lms", "0006_lessonprogress_attempts_used")]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="attachment",
            field=models.FileField(
                blank=True, upload_to="lms/submissions/%Y/%m/", verbose_name="Файл ответа"
            ),
        ),
    ]
