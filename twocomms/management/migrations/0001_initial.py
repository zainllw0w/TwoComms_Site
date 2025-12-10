from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shop_name', models.CharField(max_length=255, verbose_name='Название магазина/Instagram')),
                ('phone', models.CharField(max_length=50, verbose_name='Номер телефона')),
                ('full_name', models.CharField(max_length=255, verbose_name='ПІБ')),
                ('role', models.CharField(choices=[('manager', 'Управляющий'), ('realizer', 'Реализатор'), ('other', 'Другое')], default='manager', max_length=50, verbose_name='Статус')),
                ('source', models.CharField(blank=True, max_length=255, verbose_name='Источник контакта')),
                ('call_result', models.CharField(choices=[('order', 'Оформил заказ'), ('sent_email', 'Отправили КП на емейл'), ('sent_messenger', 'Отправили КП на мессенджеры'), ('wrote_ig', 'Написали в инстаграм'), ('no_answer', 'Не отвечает'), ('not_interested', 'Не интересует'), ('invalid_number', 'Номер недоступен'), ('xml_connected', 'Подключил выгрузку XML'), ('thinking', 'Подумает'), ('expensive', 'Дорого'), ('other', 'Другое')], default='no_answer', max_length=50, verbose_name='Итог разговора')),
                ('call_result_details', models.TextField(blank=True, help_text="Если выбрано 'Другое'", verbose_name='Детали итога')),
                ('next_call_at', models.DateTimeField(blank=True, null=True, verbose_name='Следующий звонок')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Клиент',
                'verbose_name_plural': 'Клиенты',
                'ordering': ['-created_at'],
            },
        ),
    ]
