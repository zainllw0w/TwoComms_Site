"""SEO v1.1 Phase 3 (2026-05-15) — backfill extended SEO fields for two products.

Background
----------
The audit_translations command flagged two recently-added products as
missing all extended fields (target_audience, care_instructions,
main_image_alt, seo_title, seo_description, seo_keywords) across all
three locales:

    #98 ts-not-money — Футболка «Грошей нема, все в обороті»
    #99 ls-not-money — ЛОНГСЛІВ «Грошей нема, все в обороті»

Their core fields (title / short_description / description /
full_description) are already filled in for uk/ru/en, so the remaining
gap is in the SEO support layer that Phase 17 added for richer SERP
snippets and structured data.

Strategy
--------
Compose hand-written, locale-specific copy that mirrors the satirical
business voice of the title ("No Cash, All Reinvested"). Target audience
copy doubles as the "kome pidkhodyt" / "who it suits" sidebar; care
instructions reuse the same wording so the JSON-LD is consistent.

The migration is idempotent: skips fields that already have non-empty
content (so editorial overrides via Django admin survive future
re-runs).
"""
from __future__ import annotations

from django.db import migrations


PRODUCTS_DATA = {
    "ts-not-money": {
        "uk": {
            "target_audience": (
                "Підприємці, фрилансери та засновники малого бізнесу, "
                "яким близькі гумор про cashflow і дисципліна реінвестування. "
                "Підходить тим, хто будує справу з нуля і не боїться сказати про це вголос."
            ),
            "care_instructions": (
                "Прання при 30°C на делікатному режимі, навиворіт. "
                "Не використовуйте відбілювач і агресивну машинну сушку. "
                "Прасуйте з вивороту на середній температурі, не наводьте праску прямо на принт."
            ),
            "main_image_alt": (
                "Чорна футболка TwoComms «Грошей нема все в обороті» — "
                "сатиричний бізнес-принт про реінвестиції, бавовна 95%, кулір пенье"
            ),
            "seo_title": (
                "Футболка «Грошей нема все в обороті» — TwoComms"
            ),
            "seo_description": (
                "Футболка «Грошей нема все в обороті» від TwoComms — сатиричний "
                "бізнес-принт про реінвестиції та оборотний капітал. Преміум "
                "бавовна, DTF-друк, доставка по Україні 1–2 дні."
            ),
            "seo_keywords": (
                "футболка грошей нема, футболка для підприємців, бізнес принт, "
                "TwoComms сатира, футболка реінвестиції, футболка оборотний капітал, "
                "патріотична футболка з принтом, преміум бавовна футболка"
            ),
        },
        "ru": {
            "target_audience": (
                "Предприниматели, фрилансеры и основатели малого бизнеса, "
                "которым близок юмор про cashflow и дисциплина реинвестирования. "
                "Подходит тем, кто строит дело с нуля и не боится сказать об этом вслух."
            ),
            "care_instructions": (
                "Стирка при 30°C на деликатном режиме, наизнанку. "
                "Не используйте отбеливатель и агрессивную машинную сушку. "
                "Гладьте с изнанки на средней температуре, не водите утюгом прямо по принту."
            ),
            "main_image_alt": (
                "Чёрная футболка TwoComms «Денег Нет, Всё В Обороте» — "
                "сатирический бизнес-принт о реинвестициях, хлопок 95%, кулир пенье"
            ),
            "seo_title": (
                "Футболка «Денег Нет, Всё В Обороте» — TwoComms"
            ),
            "seo_description": (
                "Футболка «Денег Нет, Всё В Обороте» от TwoComms — сатирический "
                "бизнес-принт о реинвестициях и оборотном капитале. Премиум "
                "хлопок, DTF-печать, доставка по Украине 1–2 дня."
            ),
            "seo_keywords": (
                "футболка денег нет всё в обороте, футболка для предпринимателей, "
                "бизнес-принт, TwoComms сатира, футболка о реинвестициях, "
                "футболка оборотный капитал, патриотическая футболка с принтом, "
                "премиум хлопок футболка"
            ),
        },
        "en": {
            "target_audience": (
                "Entrepreneurs, freelancers and small-business founders who "
                "appreciate cashflow humour and the discipline of reinvesting. "
                "Made for people building something from scratch and unafraid "
                "to say so out loud."
            ),
            "care_instructions": (
                "Wash at 30°C on a delicate cycle, inside out. "
                "Avoid bleach and aggressive tumble drying. "
                "Iron inside out at medium heat — never run the iron directly over the print."
            ),
            "main_image_alt": (
                "Black TwoComms «No Cash, All Reinvested» t-shirt — satirical "
                "business print about reinvestment, 95% cotton, peignoir jersey"
            ),
            "seo_title": (
                "T-shirt «No Cash, All Reinvested» — TwoComms"
            ),
            "seo_description": (
                "TwoComms «No Cash, All Reinvested» t-shirt — a satirical "
                "business print about reinvestment and working capital. Premium "
                "cotton, DTF printing, 1–2 day delivery across Ukraine."
            ),
            "seo_keywords": (
                "no cash all reinvested t-shirt, founder t-shirt, business print "
                "tee, TwoComms satire, reinvestment t-shirt, working capital tee, "
                "ukrainian streetwear, premium cotton t-shirt"
            ),
        },
    },
    "ls-not-money": {
        "uk": {
            "target_audience": (
                "Підприємці й самозайняті, які тримають темп цілий день: "
                "ранкові дзвінки, операційка, вечірня дисципліна. "
                "Лонгслів для тих, хто перетворює оборот у рух, а мінус на рахунку — у наступний крок."
            ),
            "care_instructions": (
                "Прання при 30°C на делікатному режимі, навиворіт. "
                "Не використовуйте відбілювач і жорстку машинну сушку. "
                "Прасуйте з вивороту на середній температурі, не торкайтеся принта праскою."
            ),
            "main_image_alt": (
                "Чорний лонгслів TwoComms «Грошей нема все в обороті» — "
                "сатиричний бізнес-принт, бамбук 95%, преміум-сегмент"
            ),
            "seo_title": (
                "Лонгслів «Грошей нема все в обороті» — TwoComms"
            ),
            "seo_description": (
                "Лонгслів «Грошей нема все в обороті» від TwoComms — сатиричний "
                "бізнес-принт про реінвестиції та оборотний капітал. Бамбукова "
                "база, DTF-друк, доставка Новою Поштою 1–2 дні."
            ),
            "seo_keywords": (
                "лонгслів грошей нема, лонгслів для підприємців, бізнес принт, "
                "TwoComms сатира, лонгслів реінвестиції, лонгслів оборотний капітал, "
                "патріотичний лонгслів, преміум бамбук лонгслів"
            ),
        },
        "ru": {
            "target_audience": (
                "Предприниматели и самозанятые, которые держат темп весь день: "
                "утренние звонки, операционка, вечерняя дисциплина. "
                "Лонгслив для тех, кто превращает оборот в движение, "
                "а минус на счёте — в следующий шаг."
            ),
            "care_instructions": (
                "Стирка при 30°C на деликатном режиме, наизнанку. "
                "Не используйте отбеливатель и жёсткую машинную сушку. "
                "Гладьте с изнанки на средней температуре, не касайтесь принта утюгом."
            ),
            "main_image_alt": (
                "Чёрный лонгслив TwoComms «Денег Нет, Всё В Обороте» — "
                "сатирический бизнес-принт, бамбук 95%, премиум-сегмент"
            ),
            "seo_title": (
                "Лонгслив «Денег Нет, Всё В Обороте» — TwoComms"
            ),
            "seo_description": (
                "Лонгслив «Денег Нет, Всё В Обороте» от TwoComms — сатирический "
                "бизнес-принт о реинвестициях и оборотном капитале. Бамбуковая "
                "база, DTF-печать, доставка Новой Почтой 1–2 дня."
            ),
            "seo_keywords": (
                "лонгслив денег нет всё в обороте, лонгслив для предпринимателей, "
                "бизнес-принт, TwoComms сатира, лонгслив о реинвестициях, "
                "лонгслив оборотный капитал, патриотический лонгслив, "
                "премиум бамбук лонгслив"
            ),
        },
        "en": {
            "target_audience": (
                "Entrepreneurs and self-employed founders who hold the pace "
                "all day: morning calls, operations, evening discipline. "
                "A longsleeve for those who turn cashflow into motion and a "
                "negative balance into the next move."
            ),
            "care_instructions": (
                "Wash at 30°C on a delicate cycle, inside out. "
                "Avoid bleach and harsh tumble drying. "
                "Iron inside out at medium heat — never let the iron touch the print directly."
            ),
            "main_image_alt": (
                "Black TwoComms «No Cash, All Reinvested» longsleeve — "
                "satirical business print, 95% bamboo, premium segment"
            ),
            "seo_title": (
                "Longsleeve «No Cash, All Reinvested» — TwoComms"
            ),
            "seo_description": (
                "TwoComms «No Cash, All Reinvested» longsleeve — a satirical "
                "business print about reinvestment and working capital. Bamboo "
                "base, DTF printing, 1–2 day Nova Poshta delivery."
            ),
            "seo_keywords": (
                "no cash all reinvested longsleeve, founder longsleeve, business "
                "print longsleeve, TwoComms satire, reinvestment longsleeve, "
                "working capital long sleeve, ukrainian streetwear, "
                "premium bamboo longsleeve"
            ),
        },
    },
}


def seed_extended_seo_fields(apps, schema_editor):
    Product = apps.get_model("storefront", "Product")
    for slug, locales in PRODUCTS_DATA.items():
        try:
            product = Product.objects.get(slug=slug)
        except Product.DoesNotExist:
            # Editorial may rename or remove a slug; skip gracefully.
            continue
        dirty = False
        for lang, fields in locales.items():
            for field_name, value in fields.items():
                attr = f"{field_name}_{lang}"
                if not hasattr(product, attr):
                    continue  # field doesn't exist yet on this DB schema
                current = (getattr(product, attr) or "").strip()
                if current:
                    continue  # respect editorial overrides
                setattr(product, attr, value)
                dirty = True
        if dirty:
            product.save(update_fields=[
                f"{f}_{l}"
                for l in ("uk", "ru", "en")
                for f in (
                    "target_audience",
                    "care_instructions",
                    "main_image_alt",
                    "seo_title",
                    "seo_description",
                    "seo_keywords",
                )
                if hasattr(product, f"{f}_{l}")
            ])


def reverse_noop(apps, schema_editor):
    """Don't blow away editorial copy on reverse migrations."""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("storefront", "0062_seed_category_translations_ru_en"),
    ]

    operations = [
        migrations.RunPython(seed_extended_seo_fields, reverse_noop),
    ]
