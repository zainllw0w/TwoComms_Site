"""Перерозмітити playbook-інструкції під тригерну маршрутизацію.

Навіщо окрема команда, а не правка сіду. Сід (`seed_ig_bot_sales_playbooks`)
створює інструкції, якщо їх немає, і свідомо не чіпає тексти, які міг змінити
адміністратор. Тут інша задача: у **вже наявних** записів змінити розмітку тегів,
не торкаючись тексту. Змішувати це в сіді означало б, що повторний запуск сіду
непередбачувано перезаписує роботу людини.

Що змінюється і чому. Виміряно на проді до правки:

- 202 клієнти з 289 (70%) матчили рівно **одну** інструкцію з семи, максимум по
  базі — чотири. Тобто механізм із семи правил для більшості діалогів
  дорівнював одному абзацу;
- «Prepayment Objection» розмічена тегом `payment`, а `objection=prepayment` на
  проді — **0 клієнтів** (F-PAT-002, регекс не матчив живу мову). Інструкція
  доїжджала всім, хто дійшов до оплати, і за призначенням не спрацювала ні разу;
- «Price Objection / Rescue» досяжна через `intent=price`, а `PRICE_RE` матчить
  «скільки», тому playbook відпрацювання заперечення підключався на нейтральне
  питання про ціну.

Після перерозмітки правило спрацьовує тоді, коли клієнт справді про це питає:
`on:size_question`, `on:price_objection`, `on:payment_question` тощо. Плюс
виключення `not:paid` там, де продаж уже відбувся.

Запуск ідемпотентний: якщо розмітка вже така, запис не торкається.
"""
from django.core.management.base import BaseCommand

from management.models import BotInstruction


# title → нова розмітка. Тексти не змінюємо жодного.
RETAG = {
    # Базове правило продажу має бути в кожному діалозі — воно й лишається
    # глобальним. Це єдина інструкція, яку 70% клієнтів бачили й раніше.
    "IG Core Sales": "global,core,sales",
    # Контекст товару потрібен, коли товар уже визначено, або коли клієнт саме
    # зараз питає про наявність/вибір.
    "Product / SKU Context": "product,catalog,product_matched,checkout",
    # Розмірний протокол — рівно на питання про розмір, а не на будь-який хід
    # клієнта з простроченим `objection=size` у картці.
    "Size And Fit": "on:size_question,size,fit",
    # Передоплата — коли про оплату питають зараз, і тільки до факту оплати.
    "Prepayment Objection": "on:payment_question,prepayment,not:paid",
    # Відпрацювання ціни — на заперечення («дорого»), а не на питання
    # «скільки коштує». Після оплати не потрібне.
    "Price Objection / Rescue": "on:price_objection,not:paid",
    # Кастомний принт — на явний запит про свій принт або на відповідний intent.
    "Custom Print Handoff": "on:custom_print,custom_print",
    # Закриття без тиску — коли клієнт відмовився або охолов.
    "Stop / No-buy": "no_buy,stop,cold,spam,opt_out",
}


class Command(BaseCommand):
    help = "Retag Instagram bot playbooks for trigger-based routing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показати, що змінилося б, і нічого не писати.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        changed = 0
        skipped = 0
        missing = []
        for title, tags in RETAG.items():
            obj = BotInstruction.objects.filter(title=title).order_by("id").first()
            if obj is None:
                missing.append(title)
                continue
            if (obj.intent_tags or "") == tags:
                skipped += 1
                continue
            self.stdout.write(f"{title}: {obj.intent_tags!r} -> {tags!r}")
            if not dry_run:
                obj.intent_tags = tags
                obj.save(update_fields=["intent_tags", "updated_at"])
            changed += 1

        if missing:
            self.stdout.write(self.style.WARNING(
                "не знайдено (можливо, перейменовані адміністратором): "
                + ", ".join(missing)
            ))
        verb = "буде змінено" if dry_run else "змінено"
        self.stdout.write(self.style.SUCCESS(
            f"Playbook retag: {verb} {changed}, без змін {skipped}."
        ))
