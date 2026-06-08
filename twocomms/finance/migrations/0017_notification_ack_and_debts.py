from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0016_alter_notificationlog_notification_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersettings',
            name='push_debts_enabled',
            field=models.BooleanField(default=True, verbose_name='Щоденне зведення по боргах (08:00)'),
        ),
        migrations.AddField(
            model_name='notificationlog',
            name='dedup_key',
            field=models.CharField(blank=True, db_index=True, default='', max_length=64, verbose_name='Ключ дедуплікації'),
        ),
        migrations.AddField(
            model_name='notificationlog',
            name='acknowledged',
            field=models.BooleanField(default=False, verbose_name='Ознайомлено'),
        ),
        migrations.AddField(
            model_name='notificationlog',
            name='acknowledged_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Час ознайомлення'),
        ),
        migrations.AlterField(
            model_name='notificationlog',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('daily', 'Щоденний звіт'),
                    ('weekly', 'Тижневий звіт'),
                    ('debts', 'Зведення по боргах'),
                    ('health', 'Фінансовий ризик'),
                    ('planned', 'Нагадування про платежі'),
                    ('large_txn', 'Велика операція'),
                    ('custom', 'Кастомне повідомлення'),
                ],
                max_length=20,
                verbose_name='Тип повідомлення',
            ),
        ),
    ]
