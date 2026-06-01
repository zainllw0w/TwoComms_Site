# Generated for estimated/exact planned amount support.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0012_recurrence_planned_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='recurrencerule',
            name='amount_is_estimated',
            field=models.BooleanField(
                default=False,
                help_text='Сума орієнтовна — уточнюється при оплаті',
            ),
        ),
        migrations.AddField(
            model_name='transaction',
            name='amount_is_estimated',
            field=models.BooleanField(default=False),
        ),
    ]
