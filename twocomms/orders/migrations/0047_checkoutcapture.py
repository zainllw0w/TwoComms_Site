from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('orders', '0046_wholesaleinvoice_monobank_reference_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CheckoutCapture',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(db_index=True, max_length=64, unique=True)),
                ('full_name', models.CharField(blank=True, default='', max_length=255)),
                ('phone', models.CharField(blank=True, default='', max_length=32)),
                ('email', models.EmailField(blank=True, default='', max_length=254)),
                ('cart_snapshot', models.JSONField(blank=True, default=dict)),
                ('cart_total', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('converted', models.BooleanField(default=False)),
                ('admin_notified_at', models.DateTimeField(blank=True, null=True)),
                ('recovery_sent_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='checkout_captures', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Незавершене оформлення',
                'verbose_name_plural': 'Незавершені оформлення',
            },
        ),
    ]
