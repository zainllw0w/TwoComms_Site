"""Відпечаток нашого вихідного повідомлення від провайдера.

Потрібен, щоб упізнати власне echo. У медіа-echo немає тексту, тому колишній
відпечаток по тексту (`_bot_sent_key`) там не працював у принципі: карусель бота
02.08.2026 була прийнята за повідомлення менеджера, увімкнула `manager_takeover`
і бот замовк для клієнта.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0128_ig_ugc_reward"),
    ]

    operations = [
        migrations.AddField(
            model_name="instagrambotmessage",
            name="provider_message_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=255),
        ),
    ]
