from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('management', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='owner',
            field=models.ForeignKey(
                related_name='management_clients',
                null=True,
                blank=True,
                on_delete=models.SET_NULL,
                to=settings.AUTH_USER_MODEL,
                verbose_name='Менеджер',
            ),
        ),
    ]
