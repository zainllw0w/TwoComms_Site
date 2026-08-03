from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0129_ig_outgoing_message_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="igfollowuptask",
            name="kind",
            field=models.CharField(
                choices=[
                    ("qualification", "Уточнення"),
                    ("payment", "Нагадування про оплату"),
                    ("thinking", "Клієнт думає"),
                    ("rescue", "Rescue offer"),
                    ("final", "Фінальний офер"),
                    ("fulfillment", "Дані для виконання замовлення"),
                    ("manager_task", "Завдання менеджеру"),
                ],
                db_index=True,
                default="qualification",
                max_length=24,
            ),
        ),
    ]
