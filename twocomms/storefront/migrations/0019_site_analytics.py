from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0018_add_database_indexes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(max_length=40, unique=True, db_index=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('is_bot', models.BooleanField(default=False, db_index=True)),
                ('first_seen', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('last_seen', models.DateTimeField(auto_now=True, db_index=True)),
                ('last_path', models.CharField(blank=True, max_length=512)),
                ('pageviews', models.PositiveIntegerField(default=0)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-last_seen'],
            },
        ),
        migrations.CreateModel(
            name='PageView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.CharField(max_length=512)),
                ('referrer', models.CharField(blank=True, max_length=512)),
                ('when', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('is_bot', models.BooleanField(default=False, db_index=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='views', to='storefront.sitesession')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-when'],
            },
        ),
    ]


