# Generated manually for finance app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finance', '0001_initial'),  # Замініть на останню міграцію
    ]

    operations = [
        migrations.CreateModel(
            name='UserSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('push_enabled', models.BooleanField(default=False, verbose_name='Push увімкнено')),
                ('push_daily_enabled', models.BooleanField(default=False, verbose_name='Щоденний звіт')),
                ('push_daily_time', models.TimeField(default='20:00', verbose_name='Час щоденного звіту')),
                ('push_weekly_enabled', models.BooleanField(default=False, verbose_name='Тижневий звіт')),
                ('push_weekly_day', models.IntegerField(
                    choices=[(0, 'Неділя'), (1, 'Понеділок'), (2, 'Вівторок'), (3, 'Середа'),
                             (4, 'Четвер'), (5, "П'ятниця"), (6, 'Субота')],
                    default=1,
                    verbose_name='День тижневого звіту'
                )),
                ('telegram_notifications', models.BooleanField(default=False, verbose_name='Дублювати в Telegram')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Створено')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Оновлено')),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='finance_settings',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Користувач'
                )),
            ],
            options={
                'verbose_name': 'Налаштування користувача',
                'verbose_name_plural': 'Налаштування користувачів',
                'db_table': 'finance_user_settings',
            },
        ),
        migrations.CreateModel(
            name='PushSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.URLField(max_length=500, verbose_name='Endpoint')),
                ('p256dh', models.CharField(max_length=255, verbose_name='P256DH ключ')),
                ('auth', models.CharField(max_length=255, verbose_name='Auth ключ')),
                ('user_agent', models.CharField(blank=True, max_length=500, verbose_name='User Agent')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Створено')),
                ('last_used', models.DateTimeField(auto_now=True, verbose_name='Останнє використання')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активна')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='push_subscriptions',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Користувач'
                )),
            ],
            options={
                'verbose_name': 'Push-підписка',
                'verbose_name_plural': 'Push-підписки',
                'db_table': 'finance_push_subscriptions',
            },
        ),
        migrations.CreateModel(
            name='NotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(
                    choices=[('daily', 'Щоденний звіт'), ('weekly', 'Тижневий звіт'), ('custom', 'Кастомне повідомлення')],
                    max_length=20,
                    verbose_name='Тип повідомлення'
                )),
                ('title', models.CharField(max_length=255, verbose_name='Заголовок')),
                ('body', models.TextField(verbose_name='Текст')),
                ('sent_at', models.DateTimeField(auto_now_add=True, verbose_name='Відправлено')),
                ('success', models.BooleanField(default=True, verbose_name='Успішно')),
                ('error_message', models.TextField(blank=True, verbose_name='Помилка')),
                ('report_data', models.JSONField(blank=True, null=True, verbose_name='Дані звіту')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notification_logs',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Користувач'
                )),
            ],
            options={
                'verbose_name': 'Лог повідомлень',
                'verbose_name_plural': 'Логи повідомлень',
                'db_table': 'finance_notification_logs',
                'ordering': ['-sent_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='pushsubscription',
            constraint=models.UniqueConstraint(fields=['user', 'endpoint'], name='unique_user_endpoint'),
        ),
    ]
