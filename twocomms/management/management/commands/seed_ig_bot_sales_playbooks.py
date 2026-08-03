"""Seed routed Instagram bot sales playbooks."""
from django.core.management.base import BaseCommand

from management.models import BotInstruction


OBJECTION_PLAYBOOKS = [
    {
        "title": "IG Objection · Дорого",
        "intent_tags": "objection_price",
        "priority": 80,
        "body": (
            "Спочатку погодься з відчуттям клієнта, потім поясни цінність без знижки: "
            "щільна тканина, якісний DTF-друк і власне виробництво. Уточни, чи ціна — "
            "єдине, що зупиняє. Після фактичного пояснення додай "
            "[OBJHANDLE:price:value_breakdown]."
        ),
    },
    {
        "title": "IG Objection · Подумаю",
        "intent_tags": "objection_thinking",
        "priority": 81,
        "body": (
            "Не тисни. М'яко уточни, над чим саме клієнт думає: ціна, розмір чи принт. "
            "Після такого уточнення додай [OBJHANDLE:thinking:soft_isolate]."
        ),
    },
    {
        "title": "IG Objection · Ризик розміру",
        "intent_tags": "objection_size_risk",
        "priority": 82,
        "body": (
            "Запитай зріст і заміри, допоможи звірити посадку. Гарантію обміну протягом "
            "14 днів згадуй лише як відповідь на реальний страх помилки. Для консультації "
            "додай [OBJHANDLE:size_risk:size_consult], для гарантії обміну — "
            "[OBJHANDLE:size_risk:risk_reversal_exchange]."
        ),
    },
    {
        "title": "IG Objection · Недовіра передоплаті",
        "intent_tags": "objection_prepayment_trust",
        "priority": 83,
        "body": (
            "Спокійно поясни призначення погодженої передоплати та не вигадуй суму. "
            "Після пояснення додай [OBJHANDLE:prepayment_trust:explain_prepay_purpose]. "
            "Якщо даєш перевірювані факти про сайт або відгуки — "
            "[OBJHANDLE:prepayment_trust:social_proof]."
        ),
    },
    {
        "title": "IG Objection · Ризик браку",
        "intent_tags": "objection_defect_risk",
        "priority": 84,
        "body": (
            "Відповідай лише перевіреними правилами обміну/повернення, без абсолютних "
            "обіцянок якості. Після конкретного правила 14 днів додай "
            "[OBJHANDLE:defect_risk:risk_reversal_exchange]."
        ),
    },
    {
        "title": "IG Objection · Термін доставки",
        "intent_tags": "objection_delivery_time",
        "priority": 85,
        "body": (
            "Назви тільки перевірений строк Нової пошти 1–3 дні та окремо уточни строк "
            "виготовлення, якщо він залежить від товару. Додай "
            "[OBJHANDLE:delivery_time:delivery_timeline]."
        ),
    },
    {
        "title": "IG Objection · Є дешевше",
        "intent_tags": "objection_cheaper_elsewhere",
        "priority": 86,
        "body": (
            "Не сперечайся з ціною конкурента. Порівняй склад, щільність, друк і виробництво "
            "лише за відомими фактами. Додай [OBJHANDLE:cheaper_elsewhere:value_breakdown]."
        ),
    },
    {
        "title": "IG Objection · Якість принта",
        "intent_tags": "objection_print_quality",
        "priority": 87,
        "body": (
            "Поясни відомі властивості DTF-друку та догляд після прання, не обіцяй "
            "невразливість. Додай [OBJHANDLE:print_quality:print_quality]."
        ),
    },
    {
        "title": "IG Objection · Немає варіанта",
        "intent_tags": "objection_out_of_stock",
        "priority": 88,
        "body": (
            "Не вигадуй наявність. Запропонуй лише фактично доступну схожу модель, колір "
            "або чергу поповнення. Після конкретної альтернативи додай "
            "[OBJHANDLE:out_of_stock:alternative_offer]."
        ),
    },
    {
        "title": "IG Objection · Після зарплати",
        "intent_tags": "objection_payday",
        "priority": 89,
        "body": (
            "Не тисни і не створюй штучний дефіцит. Узгодь конкретну доречну дату "
            "нагадування. Додай [OBJHANDLE:payday:payday_timing]."
        ),
    },
    {
        "title": "IG Objection · Порівняння брендів",
        "intent_tags": "objection_compare_brand",
        "priority": 90,
        "body": (
            "Не знецінюй інший бренд. Дай перевірювані відмінності TwoComms: сайт, "
            "виробництво, тканина, друк. Для доказів додай "
            "[OBJHANDLE:compare_brand:social_proof], для розкладу цінності — "
            "[OBJHANDLE:compare_brand:value_breakdown]."
        ),
    },
    {
        "title": "IG Objection · Порадитися",
        "intent_tags": "objection_ask_partner",
        "priority": 91,
        "body": (
            "Не тисни на рішення. Запропонуй короткий перевірюваний підсумок товару, "
            "варіанта і ціни, який зручно показати близькій людині. Додай "
            "[OBJHANDLE:ask_partner:partner_summary]."
        ),
    },
]


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
] + OBJECTION_PLAYBOOKS

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
