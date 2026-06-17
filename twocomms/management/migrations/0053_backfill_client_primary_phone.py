"""Бэкфилл основного ClientPhone з існуючого Client.phone.

Для кожного клієнта з непорожнім номером створюємо один основний (is_primary)
ClientPhone категорії WORK, якщо у клієнта ще немає телефонів. Аддитивно й
ідемпотентно — повторний запуск нічого не дублює.
"""
from __future__ import annotations

from django.db import migrations


def forwards(apps, schema_editor):
    Client = apps.get_model("management", "Client")
    ClientPhone = apps.get_model("management", "ClientPhone")

    # normalize/last7 робимо простими (без імпорту runtime-моделі), бо у клієнта
    # вже збережені phone_normalized / phone_last7.
    batch = []
    qs = Client.objects.exclude(phone="").only(
        "id", "phone", "phone_normalized", "phone_last7"
    )
    existing_client_ids = set(
        ClientPhone.objects.values_list("client_id", flat=True).distinct()
    )
    for client in qs.iterator(chunk_size=500):
        if client.id in existing_client_ids:
            continue
        number = (client.phone or "").strip()
        if not number:
            continue
        batch.append(
            ClientPhone(
                client_id=client.id,
                number=number,
                number_normalized=client.phone_normalized or "",
                number_last7=client.phone_last7 or "",
                category="work",
                is_primary=True,
            )
        )
        if len(batch) >= 500:
            ClientPhone.objects.bulk_create(batch, ignore_conflicts=True)
            batch = []
    if batch:
        ClientPhone.objects.bulk_create(batch, ignore_conflicts=True)


def backwards(apps, schema_editor):
    # Видаляємо лише авто-створені основні номери (безпечно для відкату).
    ClientPhone = apps.get_model("management", "ClientPhone")
    ClientPhone.objects.filter(is_primary=True, category="work", label="").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0052_callaianalysis_discrepancies_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
