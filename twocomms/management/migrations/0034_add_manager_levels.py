# Generated manually for manager levels system
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('management', '0033_merge_20260326_0327'),
    ]

    operations = [
        migrations.CreateModel(
            name='ManagerLevel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level', models.CharField(
                    choices=[
                        ('candidate', 'Менеджер-кандидат'),
                        ('level_1', 'Менеджер 1-го рівня'),
                        ('level_2', 'Менеджер 2-го рівня'),
                        ('top_manager', 'Топ-менеджер'),
                        ('project_manager', 'Project-менеджер'),
                        ('admin', 'Адміністратор'),
                    ],
                    db_index=True,
                    default='candidate',
                    max_length=20,
                    verbose_name='Рівень',
                )),
                ('assigned_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Дата призначення')),
                ('weekly_salary_uah', models.PositiveIntegerField(
                    default=0,
                    help_text='Базова тижнева ставка, виплачується при виконанні KPI',
                    verbose_name='Тижнева ставка (грн)',
                )),
                ('commission_percent', models.DecimalField(
                    decimal_places=2,
                    default=Decimal('0'),
                    help_text='Відсоток від суми замовлення',
                    max_digits=6,
                    verbose_name='Відсоток від замовлення',
                )),
                ('salary_start_date', models.DateField(
                    blank=True,
                    help_text='З якої дати починаються нарахування ставки',
                    null=True,
                    verbose_name='Дата початку нарахувань',
                )),
                ('assignment_comment', models.TextField(blank=True, verbose_name='Коментар при призначенні')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Активний')),
                ('assigned_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='assigned_manager_levels',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Призначив',
                )),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='manager_level',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Менеджер',
                )),
            ],
            options={
                'verbose_name': 'Рівень менеджера',
                'verbose_name_plural': 'Рівні менеджерів',
            },
        ),
        migrations.CreateModel(
            name='ManagerLevelHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('old_level', models.CharField(
                    blank=True,
                    choices=[
                        ('candidate', 'Менеджер-кандидат'),
                        ('level_1', 'Менеджер 1-го рівня'),
                        ('level_2', 'Менеджер 2-го рівня'),
                        ('top_manager', 'Топ-менеджер'),
                        ('project_manager', 'Project-менеджер'),
                        ('admin', 'Адміністратор'),
                    ],
                    max_length=20,
                    null=True,
                    verbose_name='Попередній рівень',
                )),
                ('new_level', models.CharField(
                    choices=[
                        ('candidate', 'Менеджер-кандидат'),
                        ('level_1', 'Менеджер 1-го рівня'),
                        ('level_2', 'Менеджер 2-го рівня'),
                        ('top_manager', 'Топ-менеджер'),
                        ('project_manager', 'Project-менеджер'),
                        ('admin', 'Адміністратор'),
                    ],
                    max_length=20,
                    verbose_name='Новий рівень',
                )),
                ('changed_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Дата зміни')),
                ('old_weekly_salary', models.PositiveIntegerField(default=0, verbose_name='Попередня ставка')),
                ('new_weekly_salary', models.PositiveIntegerField(default=0, verbose_name='Нова ставка')),
                ('old_commission_percent', models.DecimalField(
                    decimal_places=2,
                    default=Decimal('0'),
                    max_digits=6,
                    verbose_name='Попередній відсоток',
                )),
                ('new_commission_percent', models.DecimalField(
                    decimal_places=2,
                    default=Decimal('0'),
                    max_digits=6,
                    verbose_name='Новий відсоток',
                )),
                ('reason', models.TextField(blank=True, verbose_name='Причина/коментар')),
                ('changed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='manager_level_changes_made',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Змінив',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='manager_level_history',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Менеджер',
                )),
            ],
            options={
                'verbose_name': 'Історія рівня менеджера',
                'verbose_name_plural': 'Історія рівнів менеджерів',
                'ordering': ['-changed_at'],
            },
        ),
        migrations.CreateModel(
            name='WeeklySalaryAccrual',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('week_start', models.DateField(db_index=True, verbose_name='Початок тижня')),
                ('week_end', models.DateField(verbose_name='Кінець тижня')),
                ('conversions_count', models.PositiveIntegerField(
                    default=0,
                    help_text='Кількість конверсій (ORDER або TEST_BATCH) за тиждень',
                    verbose_name='Кількість конверсій',
                )),
                ('processed_clients_count', models.PositiveIntegerField(
                    default=0,
                    help_text='Кількість оброблених клієнтів за тиждень',
                    verbose_name='Оброблено клієнтів',
                )),
                ('base_weekly_salary', models.DecimalField(
                    decimal_places=2,
                    help_text='Базова тижнева ставка з ManagerLevel',
                    max_digits=12,
                    verbose_name='Базова ставка (грн)',
                )),
                ('kpi_multiplier', models.DecimalField(
                    decimal_places=2,
                    help_text='0.0 (0 конверсій), 0.5 (1 конверсія), 1.0 (2+ конверсії)',
                    max_digits=3,
                    verbose_name='KPI множник',
                )),
                ('accrued_amount', models.DecimalField(
                    decimal_places=2,
                    help_text='base_weekly_salary × kpi_multiplier',
                    max_digits=12,
                    verbose_name='Нараховано (грн)',
                )),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Очікує'),
                        ('accrued', 'Нараховано'),
                        ('cancelled', 'Скасовано'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=20,
                    verbose_name='Статус',
                )),
                ('frozen_until', models.DateTimeField(
                    help_text='Дата, до якої нарахування заморожене',
                    verbose_name='Заморожено до',
                )),
                ('note', models.TextField(blank=True, verbose_name='Примітка')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Створено')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='weekly_salary_accruals',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Менеджер',
                )),
            ],
            options={
                'verbose_name': 'Тижневе нарахування ставки',
                'verbose_name_plural': 'Тижневі нарахування ставок',
                'ordering': ['-week_start'],
            },
        ),
        migrations.AddIndex(
            model_name='managerlevel',
            index=models.Index(fields=['level', 'is_active'], name='mgmt_level_level_active'),
        ),
        migrations.AddIndex(
            model_name='managerlevelhistory',
            index=models.Index(fields=['user', '-changed_at'], name='mgmt_lvlhist_user_date'),
        ),
        migrations.AddConstraint(
            model_name='weeklysalaryaccrual',
            constraint=models.UniqueConstraint(
                fields=('user', 'week_start'),
                name='mgmt_weekly_salary_user_week_unique',
            ),
        ),
        migrations.AddIndex(
            model_name='weeklysalaryaccrual',
            index=models.Index(fields=['user', '-week_start'], name='mgmt_wksal_user_week'),
        ),
        migrations.AddIndex(
            model_name='weeklysalaryaccrual',
            index=models.Index(fields=['status', 'frozen_until'], name='mgmt_wksal_status_frozen'),
        ),
    ]
