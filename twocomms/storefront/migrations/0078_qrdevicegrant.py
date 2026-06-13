from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0077_product_video_url'),
    ]

    operations = [
        migrations.CreateModel(
            name='QrDeviceGrant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_hash', models.CharField(db_index=True, max_length=64, unique=True)),
                ('ip', models.CharField(blank=True, default='', max_length=45)),
                ('user_agent', models.CharField(blank=True, default='', max_length=300)),
                ('visits', models.PositiveIntegerField(default=1)),
                ('first_seen', models.DateTimeField(auto_now_add=True)),
                ('last_seen', models.DateTimeField(auto_now=True)),
                ('promo_code', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qr_device_grants', to='storefront.promocode')),
            ],
            options={
                'verbose_name': 'QR-видача (пристрій)',
                'verbose_name_plural': 'QR-видачі (пристрої)',
            },
        ),
    ]
