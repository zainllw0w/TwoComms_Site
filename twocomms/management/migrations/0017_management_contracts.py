from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0016_managercommissionaccrual_note'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContractSequence',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.PositiveIntegerField(unique=True)),
                ('last_number', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Нумерація договорів (рік)',
                'verbose_name_plural': 'Нумерація договорів (рік)',
            },
        ),
        migrations.CreateModel(
            name='ManagementContract',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contract_number', models.CharField(max_length=50, unique=True, verbose_name='Номер договору')),
                ('contract_date', models.DateField(verbose_name='Дата договору')),
                ('realizer_name', models.CharField(max_length=255, verbose_name='Реалізатор')),
                ('file_path', models.CharField(max_length=500, verbose_name='Шлях до файлу')),
                ('payload', models.JSONField(blank=True, default=dict, verbose_name='Дані договору')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='management_contracts', to=settings.AUTH_USER_MODEL, verbose_name='Менеджер')),
            ],
            options={
                'verbose_name': 'Договір (менеджмент)',
                'verbose_name_plural': 'Договори (менеджмент)',
                'ordering': ['-created_at'],
            },
        ),
    ]
