from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0017_management_contracts'),
    ]

    operations = [
        migrations.AddField(
            model_name='managementcontract',
            name='review_status',
            field=models.CharField(
                choices=[('draft', 'Чернетка'), ('pending', 'На перевірці'), ('approved', 'Підтверджено'), ('rejected', 'Відхилено')],
                default='draft',
                max_length=20,
                verbose_name='Статус перевірки',
            ),
        ),
        migrations.AddField(
            model_name='managementcontract',
            name='review_reject_reason',
            field=models.TextField(blank=True, verbose_name='Причина відхилення'),
        ),
        migrations.AddField(
            model_name='managementcontract',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Дата перевірки'),
        ),
        migrations.AddField(
            model_name='managementcontract',
            name='reviewed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviewed_management_contracts',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Перевірив (адмін)',
            ),
        ),
        migrations.AddField(
            model_name='managementcontract',
            name='admin_tg_chat_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='Telegram admin chat id'),
        ),
        migrations.AddField(
            model_name='managementcontract',
            name='admin_tg_message_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='Telegram admin message id'),
        ),
        migrations.AddField(
            model_name='managementcontract',
            name='is_approved',
            field=models.BooleanField(default=False, verbose_name='Підтверджено'),
        ),
        migrations.CreateModel(
            name='ContractRejectionReasonRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_chat_id', models.BigIntegerField(db_index=True, verbose_name='Telegram chat id (адмін)')),
                ('prompt_message_id', models.BigIntegerField(blank=True, null=True, verbose_name='Message id запиту')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Активний запит')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('contract', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rejection_reason_requests', to='management.managementcontract', verbose_name='Договір')),
            ],
            options={
                'verbose_name': 'Запит причини відхилення договору',
                'verbose_name_plural': 'Запити причин відхилення договорів',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['admin_chat_id', 'is_active'], name='mgmt_contractrej_chat_act')],
            },
        ),
    ]
