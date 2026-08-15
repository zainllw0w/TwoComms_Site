from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0164_ig_payment_follow_preparation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="igugcevidenceassessment",
            name="decision",
            field=models.CharField(
                choices=[
                    ("pending", _("Очікує оцінки")),
                    ("qualified_auto", _("Автоматично підтверджено")),
                    ("needs_manager_review", _("Потрібен менеджер")),
                    ("manager_approved", _("Підтверджено менеджером")),
                    ("rejected", _("Відхилено")),
                ],
                db_index=True,
                default="pending",
                max_length=24,
            ),
        ),
    ]
