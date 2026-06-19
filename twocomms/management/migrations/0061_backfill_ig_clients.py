"""Бекофіл IgClient зі старої історії InstagramBotMessage (за sender_id).

Самодостатня data-міграція (через apps.get_model, без імпорту app-коду, бо
сигнатури можуть змінитись). Логіка дзеркалить
instagram_bot.link_orphan_messages_to_clients(), яка покрита тестами.
"""
from django.db import migrations


def backfill_ig_clients(apps, schema_editor):
    InstagramBotMessage = apps.get_model("management", "InstagramBotMessage")
    IgClient = apps.get_model("management", "IgClient")
    from django.db.models import Max, Min

    sender_ids = list(
        InstagramBotMessage.objects.filter(client__isnull=True)
        .exclude(sender_id="")
        .order_by("sender_id")  # скидаємо Meta.ordering=['id'], інакше distinct ламається
        .values_list("sender_id", flat=True)
        .distinct()
    )
    for sid in sender_ids:
        client, _created = IgClient.objects.get_or_create(igsid=sid)
        agg = InstagramBotMessage.objects.filter(sender_id=sid).aggregate(
            first=Min("created_at"), last=Max("created_at")
        )
        fields = []
        if not client.first_contact_at and agg["first"]:
            client.first_contact_at = agg["first"]
            fields.append("first_contact_at")
        if agg["last"]:
            client.last_message_at = agg["last"]
            fields.append("last_message_at")
        if fields:
            client.save(update_fields=fields)
        InstagramBotMessage.objects.filter(sender_id=sid, client__isnull=True).update(client=client)


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0060_igclient_instagrambotmessage_client"),
    ]

    operations = [
        migrations.RunPython(backfill_ig_clients, migrations.RunPython.noop),
    ]
