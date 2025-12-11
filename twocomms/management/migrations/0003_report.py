from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('management', '0002_client_owner'),
    ]

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('points', models.PositiveIntegerField(default=0)),
                ('processed', models.PositiveIntegerField(default=0)),
                ('file', models.FileField(blank=True, null=True, upload_to='reports/')),
                ('owner', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='management_reports', to=settings.AUTH_USER_MODEL, verbose_name='Менеджер')),
            ],
            options={
                'ordering': ['-created_at'],
                'verbose_name': 'Звіт',
                'verbose_name_plural': 'Звіти',
            },
        ),
    ]
