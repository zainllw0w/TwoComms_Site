# Generated for Telegram verification redesign — 2026-05-17

from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0024_telegramverificationsession'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='telegramverificationsession',
            name='purpose',
            field=models.CharField(
                choices=[
                    ('custom_print', 'Контакт у формі кастомного принта'),
                    ('profile_link', 'Привʼязка профілю'),
                    ('login', 'Вхід через Telegram'),
                    ('management_bind', 'Привʼязка менеджмент-бота'),
                    ('dropshipper_link', 'Привʼязка дропшипера'),
                ],
                default='custom_print',
                max_length=32,
                verbose_name='Призначення',
            ),
        ),
        migrations.AddField(
            model_name='telegramverificationsession',
            name='metadata',
            field=models.JSONField(
                blank=True, null=True, default=dict, verbose_name='Метадані сесії'
            ),
        ),
        migrations.AddField(
            model_name='telegramverificationsession',
            name='resolved_user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='telegram_resolved_sessions',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Користувач (визначений після верифікації)',
            ),
        ),
        migrations.AddField(
            model_name='telegramverificationsession',
            name='consumed_at',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Використано (login виконано)'
            ),
        ),
    ]
