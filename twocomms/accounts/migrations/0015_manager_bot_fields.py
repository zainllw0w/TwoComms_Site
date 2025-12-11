from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_userprofile_idx_userprofile_telegram_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='tg_manager_bind_code',
            field=models.CharField(blank=True, max_length=64, verbose_name="Код прив'язки менеджмент-бота"),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='tg_manager_bind_expires_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Діє до'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='tg_manager_chat_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='Telegram Management Chat ID'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='tg_manager_username',
            field=models.CharField(blank=True, max_length=255, verbose_name='Telegram Management Username'),
        ),
    ]
