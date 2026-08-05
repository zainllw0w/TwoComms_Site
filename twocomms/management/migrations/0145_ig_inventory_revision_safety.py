from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0144_ig_inventory_allocation_lifecycle"),
    ]

    operations = [
        migrations.AlterField(
            model_name="igcheckoutinventoryreservation",
            name="item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="inventory_reservations",
                to="management.igcheckoutproposalitem",
            ),
        ),
        migrations.AlterField(
            model_name="igcheckoutproposal",
            name="status",
            field=models.CharField(
                choices=[
                    ("ready", "Готова"),
                    ("viewed", "Переглянута"),
                    ("details_locked", "Дані зафіксовані"),
                    ("invoice_created", "Рахунок створено"),
                    ("manager_review", "Потрібна перевірка менеджера"),
                    ("paid", "Оплачено"),
                    ("cancelled", "Рахунок скасовано"),
                    ("expired", "Протерміновано"),
                    ("revoked", "Відкликано"),
                    ("superseded", "Замінено"),
                ],
                db_index=True,
                default="ready",
                max_length=24,
            ),
        ),
    ]
