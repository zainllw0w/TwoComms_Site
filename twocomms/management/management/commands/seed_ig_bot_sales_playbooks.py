"""Seed routed Instagram bot sales playbooks."""
from django.core.management.base import BaseCommand

from management.models import BotInstruction


PLAYBOOKS = [
    {
        "title": "IG Core Sales",
        "intent_tags": "global,core,sales",
        "priority": 10,
        "body": (
            "Веди клієнта до наступного кроку без тиску: зрозумій товар, розмір, колір, "
            "кількість, для себе чи на подарунок. Пиши коротко, мовою клієнта. Не вигадуй "
            "ціни/наявність/посилання; якщо не впевнений у товарі, попроси фото поста або "
            "уточнення. Для оплати надсилай лише персональну пропозицію TwoComms, ніколи не "
            "прямий платіжний URL."
        ),
    },
    {
        "title": "Product / SKU Context",
        "intent_tags": "product,catalog,product_matched,checkout",
        "priority": 20,
        "body": (
            "Якщо товар визначений, тримай саме його як основний SKU діалогу. Уточнюй тільки "
            "потрібні для пропозиції речі: фасон, розмір, колір, кількість і тип оплати. Для "
            "футболки з classic/oversize спершу запитай фасон, покажи сітку саме цього фасону, "
            "а потім запитуй розмір. Не збирай доставку та email у Direct: клієнт вводить їх "
            "на персональній сторінці пропозиції."
        ),
    },
    {
        "title": "Size And Fit",
        "intent_tags": "size,fit",
        "priority": 30,
        "body": (
            "На питання про розмір пояснюй різницю classic/oversize і пропонуй відповідну "
            "розмірну сітку або допомогу по замірах. Не гарантуй посадку без даних з "
            "розмірної сітки та не обирай фасон чи розмір замість клієнта."
        ),
    },
    {
        "title": "Prepayment Objection",
        "intent_tags": "prepayment,payment",
        "priority": 40,
        "body": (
            "Передоплата може бути лише на точну суму, яку менеджер або клієнт явно погодили "
            "в поточній переписці. Не називай фіксовані 200 грн і не перенось суму з іншого "
            "клієнта чи попереднього замовлення. Пояснюй спокійно: погоджена частина "
            "вноситься зараз, залишок — за узгодженим сценарієм."
        ),
    },
    {
        "title": "Price Objection / Rescue",
        "intent_tags": "price,discount",
        "priority": 50,
        "body": (
            "Спочатку відпрацьовуй цінність: власне виробництво, якісна тканина, DTF-друк, "
            "відгуки. Не пропонуй знижку самостійно: автоматична система окремо дасть 5%, "
            "а 10% тільки як фінальний або явно узгоджений варіант."
        ),
    },
    {
        "title": "Custom Print Handoff",
        "intent_tags": "custom_print",
        "priority": 60,
        "body": (
            "Для кастомного принта не називай фінальну ціну. Коротко поясни: можемо зробити "
            "майже будь-який DTF-принт, ціна залежить від крою, розміру принта і готовності "
            "файлу. Збери базове ТЗ і переведи в Telegram менеджера з шапки профілю."
        ),
    },
    {
        "title": "Stop / No-buy",
        "intent_tags": "no_buy,stop,cold,spam",
        "priority": 70,
        "body": (
            "Якщо клієнт відмовився, просить не писати або це спам, не тисни. Один раз чемно "
            "закрий діалог і не став follow-up. Можна запросити стежити за майбутніми дропами."
        ),
    },
]

# A matching body means the row was created by an older known seed and may be
# upgraded. Any other body is an administrator's instruction and is untouched.
LEGACY_PLAYBOOK_BODIES = {
    "IG Core Sales": frozenset({
        "Веди клієнта до наступного кроку без тиску: зрозумій товар, розмір, колір, "
        "кількість, для себе чи на подарунок. Пиши коротко, мовою клієнта. Не вигадуй "
        "ціни/наявність/посилання; якщо не впевнений у товарі, попроси посилання на пост "
        "або уточнення.",
    }),
    "Product / SKU Context": frozenset({
        "Якщо товар визначений, тримай саме його як основний SKU діалогу. Уточнюй тільки "
        "потрібні для оформлення речі: розмір, колір, кількість, тип оплати і доставку.",
    }),
    "Size And Fit": frozenset({
        "На питання про розмір пояснюй різницю regular/oversize і пропонуй розмірну сітку "
        "або допомогу по замірах. Не гарантуй посадку без даних з розмірної сітки.",
    }),
}


class Command(BaseCommand):
    help = "Seed routed sales playbooks for the Instagram Direct bot."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        preserved = 0
        for item in PLAYBOOKS:
            obj = BotInstruction.objects.filter(title=item["title"]).order_by("id").first()
            if obj is None:
                BotInstruction.objects.create(
                    title=item["title"],
                    body=item["body"],
                    intent_tags=item["intent_tags"],
                    priority=item["priority"],
                    is_active=True,
                )
                created += 1
                continue

            managed_bodies = set(LEGACY_PLAYBOOK_BODIES.get(item["title"], ()))
            managed_bodies.add(item["body"])
            if obj.body not in managed_bodies:
                preserved += 1
                continue

            changed = []
            for field in ("body", "intent_tags", "priority", "is_active"):
                value = item[field] if field in item else True
                if getattr(obj, field) != value:
                    setattr(obj, field, value)
                    changed.append(field)
            if changed:
                obj.save(update_fields=[*changed, "updated_at"])
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"IG sales playbooks seeded: {created} created, {updated} updated, {preserved} preserved."
        ))
