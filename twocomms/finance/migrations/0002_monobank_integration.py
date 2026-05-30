from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0001_initial'),
    ]

    operations = [
        # --- IntegrationConnection: токен-доступ, вебхук, мета ---
        migrations.AddField(
            model_name='integrationconnection',
            name='connection_method',
            field=models.CharField(choices=[('qr', 'QR-код'), ('token', 'API-токен'), ('manual', 'Ручний імпорт')], default='qr', max_length=12),
        ),
        migrations.AddField(
            model_name='integrationconnection',
            name='encrypted_token',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='integrationconnection',
            name='token_fingerprint',
            field=models.CharField(blank=True, db_index=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='integrationconnection',
            name='token_mask',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='integrationconnection',
            name='webhook_secret',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='integrationconnection',
            name='webhook_url',
            field=models.URLField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='integrationconnection',
            name='auto_sync',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='integrationconnection',
            name='client_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='integrationconnection',
            name='external_client_id',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
        migrations.AddField(
            model_name='integrationconnection',
            name='meta',
            field=models.JSONField(blank=True, default=dict),
        ),
        # --- Account: прив'язка до зовнішнього рахунку + бізнес-прапор ---
        migrations.AddField(
            model_name='account',
            name='external_account_id',
            field=models.CharField(blank=True, db_index=True, default='', max_length=128),
        ),
        migrations.AddField(
            model_name='account',
            name='external_kind',
            field=models.CharField(blank=True, default='', max_length=16),
        ),
        migrations.AddField(
            model_name='account',
            name='iban',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='account',
            name='masked_pan',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='account',
            name='is_business',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='account',
            name='auto_sync',
            field=models.BooleanField(default=True),
        ),
        # --- Transaction: бізнес/особисте + багаті дані провайдера ---
        migrations.AddField(
            model_name='transaction',
            name='is_business',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='transaction',
            name='external_data',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='transaction',
            name='mcc',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
    ]
