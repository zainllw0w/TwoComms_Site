# Generated manually for Telegram ID field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_userprofile_instagram_userprofile_telegram'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='telegram_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='Telegram ID'),
        ),
    ]
