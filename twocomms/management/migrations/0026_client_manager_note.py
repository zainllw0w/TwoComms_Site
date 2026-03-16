from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0025_duplicatereview_resolution_note_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="manager_note",
            field=models.TextField(blank=True, verbose_name="Нотатка менеджера"),
        ),
    ]
