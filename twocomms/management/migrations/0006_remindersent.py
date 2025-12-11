from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0005_reminderread'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReminderSent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(db_index=True, max_length=255)),
                ('chat_id', models.BigIntegerField()),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'unique_together': {('key', 'chat_id')},
            },
        ),
    ]
