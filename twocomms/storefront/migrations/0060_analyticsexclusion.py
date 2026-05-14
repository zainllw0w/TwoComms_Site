# Generated manually for AnalyticsExclusion (admin-managed analytics exclusion list).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0059_phase17c_modeltranslation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AnalyticsExclusion',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'kind',
                    models.CharField(
                        choices=[
                            ('ip', 'IP-адреса'),
                            ('user', 'Користувач (ID)'),
                            ('visitor', 'Visitor cookie (twc_vid)'),
                            ('user_agent', 'User-Agent (substring)'),
                            ('path', 'Шлях (startswith)'),
                        ],
                        db_index=True,
                        default='ip',
                        max_length=16,
                        verbose_name='Тип',
                    ),
                ),
                (
                    'value',
                    models.CharField(
                        help_text=(
                            'IP-адреса (192.168.0.1 або CIDR 10.0.0.0/8), user_id, visitor_id, '
                            'підрядок User-Agent чи префікс шляху.'
                        ),
                        max_length=512,
                        verbose_name='Значення',
                    ),
                ),
                (
                    'note',
                    models.CharField(
                        blank=True,
                        help_text=(
                            'Для чого додано (наприклад: «офіс», «менеджер», '
                            '«перевірка ботів»).'
                        ),
                        max_length=255,
                        verbose_name='Коментар',
                    ),
                ),
                (
                    'is_active',
                    models.BooleanField(default=True, db_index=True, verbose_name='Активне'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Створено')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Оновлено')),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='analytics_exclusions',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Створив',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Аналітичне виключення',
                'verbose_name_plural': 'Аналітичні виключення',
                'ordering': ('-updated_at',),
            },
        ),
        migrations.AddConstraint(
            model_name='analyticsexclusion',
            constraint=models.UniqueConstraint(
                fields=('kind', 'value'),
                name='uq_analytics_exclusion_kind_value',
            ),
        ),
        migrations.AddIndex(
            model_name='analyticsexclusion',
            index=models.Index(
                fields=['kind', 'is_active'],
                name='idx_analytics_excl_kind_act',
            ),
        ),
    ]
