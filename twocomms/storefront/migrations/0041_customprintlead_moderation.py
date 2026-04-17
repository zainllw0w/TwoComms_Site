# Generated manually on 2026-04-16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0040_customprintlead_v2_snapshot_fields"),
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customprintlead",
            name="moderation_status",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("draft", "Чернетка"),
                    ("awaiting_review", "На перевірці менеджера"),
                    ("approved", "Погоджено — оплата доступна"),
                    ("rejected", "Відхилено менеджером"),
                ],
                default="draft",
                verbose_name="Статус модерації кастомного кошика",
            ),
        ),
        migrations.AddField(
            model_name="customprintlead",
            name="approved_price",
            field=models.DecimalField(
                max_digits=10,
                decimal_places=2,
                null=True,
                blank=True,
                verbose_name="Ціна після погодження менеджера",
            ),
        ),
        migrations.AddField(
            model_name="customprintlead",
            name="manager_note",
            field=models.TextField(blank=True, default="", verbose_name="Коментар менеджера"),
        ),
        migrations.AddField(
            model_name="customprintlead",
            name="moderation_token",
            field=models.CharField(max_length=64, blank=True, default="", verbose_name="Токен для дій менеджера"),
        ),
        migrations.AddField(
            model_name="customprintlead",
            name="reviewed_at",
            field=models.DateTimeField(null=True, blank=True, verbose_name="Коли відреаговано"),
        ),
        migrations.AddField(
            model_name="customprintlead",
            name="order",
            field=models.ForeignKey(
                on_delete=models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name="custom_print_leads",
                to="orders.order",
                verbose_name="Замовлення",
            ),
        ),
    ]
