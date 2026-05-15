"""SEO v1.1 Phase 2 (2026-05-15) — RU/EN backfill for Category content.

Background
----------
The 2026-05-15 ownership directive lifted the blanket ``noindex`` on
``/ru/`` and ``/en/`` locales (commit ``7021b46c``). For Google to
cluster the variants properly via reciprocal hreflang, every indexable
page needs translated copy. The audit at deploy time showed:

    Category.description     | uk: 100% | ru:   0% | en:   0%
    Category.seo_intro_html  | uk: 100% | ru:   0% | en:   0%

(Other Category fields — ``name``, ``seo_text_title``, ``seo_title``,
``seo_h1``, ``seo_description`` — already had RU/EN copies populated by
the Phase 17c modeltranslation rollout.)

Strategy
--------
Hand-translate the long-form HTML for the three live categories
(``hoodie`` / ``tshirts`` / ``long-sleeve``) into Russian and English.
The copy mirrors the UA structure (intro paragraph + ``<details>`` for
``seo_intro_html``; H2/H3 sections + internal links for
``description``) so the layout stays identical across locales.

The migration is **idempotent**: it skips a category if a target field
is already non-empty in that locale. Editorial staff can therefore
override the seed content via Django admin and re-running the migration
will not clobber their edits.
"""
from __future__ import annotations

from django.db import migrations


# ===================================================================
# Source UA copy lives in 0053_phase10b_seed_category_seo.py. The
# translations below were produced manually with attention to brand
# voice (mil-streetwear, ZSU references kept in EN as is, slang
# avoided). Internal links remain identical — the target URLs are not
# language-prefixed in i18n_patterns, so /ru/ visitors will land on the
# UA URL unless a user explicitly switches locale, which mirrors the
# storefront's existing behaviour.
# ===================================================================

DESCRIPTION_RU = {
    "hoodie": """
<p>В каталоге <strong>худи TwoComms</strong> вы найдёте
<a href="/catalog/hoodie/?color=black">чёрные</a>,
<a href="/catalog/hoodie/?color=coyote">койот</a>,
оливковые и нейтральные модели — оверсайз и классического силуэта.
Все худи отшиваются в Украине, рассчитаны на повседневную носку
и хорошо сочетаются с
<a href="/catalog/long-sleeve/">лонгсливами</a> и
<a href="/catalog/tshirts/">футболками</a> бренда.</p>

<h3>Как выбрать худи</h3>
<p>Размер подбирайте по <a href="/rozmirna-sitka/">размерной сетке</a>:
для слоёв с лонгсливом берите свой обычный размер, для оверсайз-силуэта
— на единицу больше. Уход — на странице
<a href="/doglyad-za-odyagom/">уход за одеждой</a>.</p>

<h3>Доставка и оплата</h3>
<p>Доставляем <a href="/delivery/">Новой Поштой</a> по всей Украине
(отделение / поштомат / адресная). Оплата — Monobank, наложенный
платёж, оплата на карту. <a href="/povernennya-ta-obmin/">Возврат</a>
в течение 14 дней.</p>

<h3>Почему TwoComms</h3>
<p>TwoComms — украинский streetwear с милитарным ДНК: мы делаем одежду
для тех, кто живёт в Украине, поддерживает ВСУ и ценит спокойную, но
сильную эстетику. Подробнее — на странице
<a href="/pro-brand/">о бренде</a>.</p>
""",
    "tshirts": """
<p>Каталог <strong>футболок TwoComms</strong> — это больше десятка
авторских принтов в милитарно-патриотическом ДНК: трезубец, ВСУ,
streetwear-графика. Можно
<a href="/catalog/tshirts/?color=black">купить чёрную футболку</a>,
<a href="/catalog/tshirts/?color=white">белую</a> или
<a href="/catalog/tshirts/?color=olive">оливу</a>, а также собрать
комплект с <a href="/catalog/hoodie/">худи</a> или
<a href="/catalog/long-sleeve/">лонгсливом</a>.</p>

<h3>Силуэты и посадки</h3>
<p>В ассортименте — классический крой (regular fit) и oversize. Для
оверсайз-комплектов смотрите <a href="/catalog/tshirts/?fit=oversize">фильтр
oversize</a>. <a href="/rozmirna-sitka/">Размерная сетка</a> поможет
выбрать точно.</p>

<h3>Принты и символика</h3>
<p>Большинство принтов TwoComms — авторские иллюстрации с милитарным
и streetwear-настроением. Мы не используем «лубочную» символику —
только современные визуальные решения, которые хорошо смотрятся в
городе и комбинируются с нашими <a href="/catalog/hoodie/">худи</a>
и лонгсливами.</p>

<h3>Доставка и оплата</h3>
<p><a href="/delivery/">Доставка Новой Поштой</a> по всей Украине,
оплата — Monobank / наложенный платёж / карта. Подробности на
<a href="/dopomoga/">странице помощи</a>.</p>
""",
    "long-sleeve": """
<p>Каталог <strong>лонгсливов TwoComms</strong> — для тех, кому мало
футболки, но худи пока лишнее. Подберите
<a href="/catalog/long-sleeve/?color=black">чёрный лонгслив</a>,
<a href="/catalog/long-sleeve/?color=coyote">койот</a> или базовые
цвета, которые хорошо садятся под <a href="/catalog/hoodie/">худи</a>
или носятся самостоятельно.</p>

<h3>Как носить лонгслив</h3>
<p>Лонгслив — универсальный базовый слой: можно носить отдельно,
комбинировать с худи или лёгкой курткой. Для прохладной погоды
смотрите раздел <a href="/catalog/hoodie/">худи</a>. Для тёплых дней
— наш каталог <a href="/catalog/tshirts/">футболок</a>.</p>

<h3>Размер и уход</h3>
<p>Ориентируйтесь на <a href="/rozmirna-sitka/">размерную сетку</a>:
классический силуэт = свой размер, oversize = +1. Инструкции по стирке
— в разделе <a href="/doglyad-za-odyagom/">уход за одеждой</a>.</p>

<h3>Почему TwoComms</h3>
<p>Мы — украинский бренд с милитарным ДНК: одежда для патриотов,
сторонников ВСУ и ценителей streetwear-эстетики одновременно.
Подробнее — на странице <a href="/pro-brand/">о бренде</a>.</p>
""",
}


SEO_INTRO_HTML_RU = {
    "hoodie": """
<p><strong>Худи TwoComms</strong> — украинский streetwear с милитарным
ДНК: плотная ткань, усиленные швы, авторские принты на тему ВСУ,
трезубца и свободы. Можно <a href="/catalog/hoodie/?color=black">купить чёрное худи</a>,
<a href="/catalog/hoodie/?color=coyote">цвета койот</a> или подобрать
<a href="/catalog/tshirts/">футболку</a> либо <a href="/catalog/long-sleeve/">лонгслив</a>
в тон.</p>
<details>
  <summary>Что такое худи TwoComms?</summary>
  <p>Худи — базовый элемент гардероба, объединяющий комфорт спортивной
  одежды и силуэт современного streetwear. В TwoComms мы делаем акцент
  на патриотических принтах, качественной DTF-печати и фурнитуре,
  выдерживающей повседневную носку. Все худи отшиваются в Украине, в
  рамках собственного <a href="/pro-brand/">милитарного нарратива
  бренда</a>.</p>
</details>
""",
    "tshirts": """
<p><strong>Футболки TwoComms</strong> — лаконичный украинский
streetwear с милитарными акцентами и принтами на тему ВСУ. Можно
<a href="/catalog/tshirts/?color=black">купить чёрную футболку</a>,
<a href="/catalog/tshirts/?color=olive">оливу</a> или
<a href="/catalog/tshirts/?color=white">белую</a>, а также дополнить её
<a href="/catalog/hoodie/">худи</a> или <a href="/catalog/long-sleeve/">лонгсливом</a>.</p>
<details>
  <summary>Почему футболка TwoComms — это не просто футболка?</summary>
  <p>Мы используем плотный хлопковый трикотаж 180–220 г/м², авторские
  принты в DTF-печати и собственные лекала с oversize/классическим
  силуэтами. Каждая модель — часть <a href="/pro-brand/">brand DNA
  TwoComms</a>: милитарная эстетика без лишнего пафоса, патриотические
  символы без «лубочности».</p>
</details>
""",
    "long-sleeve": """
<p><strong>Лонгсливы TwoComms</strong> — универсальный слой
streetwear-гардероба: сильнее футболки, легче худи. В наличии
<a href="/catalog/long-sleeve/?color=black">чёрный лонгслив</a>,
<a href="/catalog/long-sleeve/?color=coyote">койот</a> и классические
цвета, хорошо сочетающиеся с <a href="/catalog/hoodie/">худи</a> и
<a href="/catalog/tshirts/">футболками</a> из нашего каталога.</p>
<details>
  <summary>Когда носить лонгслив?</summary>
  <p>Лонгслив — идеальный выбор для прохладной погоды, слоёв под худи
  или как самостоятельный топ. В TwoComms лонгсливы выполнены в
  милитарном ДНК: аккуратные принты, усиленные манжеты, ткань, держащая
  форму после стирки. Узнайте больше о <a href="/pro-brand/">философии
  TwoComms</a>.</p>
</details>
""",
}


DESCRIPTION_EN = {
    "hoodie": """
<p>The <strong>TwoComms hoodie</strong> catalogue features
<a href="/catalog/hoodie/?color=black">black</a>,
<a href="/catalog/hoodie/?color=coyote">coyote</a>,
olive and neutral colour-ways in both oversize and classic cuts.
Every hoodie is sewn in Ukraine for daily wear and pairs with our
<a href="/catalog/long-sleeve/">long sleeves</a> and
<a href="/catalog/tshirts/">tees</a>.</p>

<h3>How to choose a hoodie</h3>
<p>Use the <a href="/rozmirna-sitka/">size chart</a>: take your usual
size for layering with a long sleeve, size up for oversize cuts. Care
instructions are on the <a href="/doglyad-za-odyagom/">garment care</a>
page.</p>

<h3>Delivery and payment</h3>
<p>We ship via <a href="/delivery/">Nova Poshta</a> across Ukraine
(branch / poshtomat / address). Payments — Monobank, cash on delivery,
card. <a href="/povernennya-ta-obmin/">Returns</a> within 14 days.</p>

<h3>Why TwoComms</h3>
<p>TwoComms is a Ukrainian streetwear brand with a military-adjacent
DNA: we make clothing for people living in Ukraine, supporting the AFU,
and valuing a quiet but confident aesthetic. Read more on the
<a href="/pro-brand/">about the brand</a> page.</p>
""",
    "tshirts": """
<p>The <strong>TwoComms t-shirt</strong> catalogue ships more than a
dozen original prints rooted in our military-patriotic DNA: tryzub,
AFU, streetwear graphics. You can
<a href="/catalog/tshirts/?color=black">grab a black tee</a>,
<a href="/catalog/tshirts/?color=white">white</a> or
<a href="/catalog/tshirts/?color=olive">olive</a>, and round it out
with one of our <a href="/catalog/hoodie/">hoodies</a> or
<a href="/catalog/long-sleeve/">long sleeves</a>.</p>

<h3>Cuts and fits</h3>
<p>Both regular and oversize cuts are available. For full oversize sets
check the <a href="/catalog/tshirts/?fit=oversize">oversize filter</a>.
The <a href="/rozmirna-sitka/">size chart</a> helps you nail it.</p>

<h3>Prints and symbolism</h3>
<p>Most TwoComms prints are original illustrations in a
military-streetwear mood. We don't use kitsch — only modern visual
solutions that carry well in the city and combine with our
<a href="/catalog/hoodie/">hoodies</a> and long sleeves.</p>

<h3>Delivery and payment</h3>
<p><a href="/delivery/">Nova Poshta delivery</a> across Ukraine.
Payment via Monobank / cash on delivery / card. Details on the
<a href="/dopomoga/">help page</a>.</p>
""",
    "long-sleeve": """
<p>The <strong>TwoComms long sleeve</strong> catalogue is for those
who outgrew the t-shirt but aren't ready for a hoodie yet. Pick a
<a href="/catalog/long-sleeve/?color=black">black long sleeve</a>,
<a href="/catalog/long-sleeve/?color=coyote">coyote</a>, or a base
colour that layers well under our <a href="/catalog/hoodie/">hoodies</a>
or wears on its own.</p>

<h3>How to wear a long sleeve</h3>
<p>The long sleeve is a universal base layer: wear it solo, layer it
under a hoodie or a light jacket. Cooler weather → check our
<a href="/catalog/hoodie/">hoodies</a>. Warmer days →
<a href="/catalog/tshirts/">t-shirts</a>.</p>

<h3>Size and care</h3>
<p>Reference the <a href="/rozmirna-sitka/">size chart</a>: classic
silhouette = your size, oversize = +1. Wash instructions are on the
<a href="/doglyad-za-odyagom/">garment care</a> page.</p>

<h3>Why TwoComms</h3>
<p>We're a Ukrainian brand with a military DNA — clothing for patriots,
AFU supporters and streetwear lovers at the same time. More on the
<a href="/pro-brand/">about</a> page.</p>
""",
}


SEO_INTRO_HTML_EN = {
    "hoodie": """
<p><strong>TwoComms hoodies</strong> are Ukrainian streetwear with a
military DNA: dense fabric, reinforced seams, original prints rooted in
the AFU, tryzub and freedom themes. You can
<a href="/catalog/hoodie/?color=black">grab a black hoodie</a>,
<a href="/catalog/hoodie/?color=coyote">a coyote one</a>, or pick a
matching <a href="/catalog/tshirts/">t-shirt</a> or
<a href="/catalog/long-sleeve/">long sleeve</a>.</p>
<details>
  <summary>What makes a TwoComms hoodie?</summary>
  <p>The hoodie is a wardrobe staple that blends sport-grade comfort
  with a modern streetwear silhouette. At TwoComms we focus on patriotic
  prints, premium DTF printing and hardware that survives daily wear.
  Every hoodie is made in Ukraine, telling the
  <a href="/pro-brand/">brand's military narrative</a>.</p>
</details>
""",
    "tshirts": """
<p><strong>TwoComms t-shirts</strong> are clean Ukrainian streetwear
with military accents and AFU-themed prints. You can
<a href="/catalog/tshirts/?color=black">grab a black tee</a>,
<a href="/catalog/tshirts/?color=olive">olive</a>, or
<a href="/catalog/tshirts/?color=white">white</a>, and complete the
look with a <a href="/catalog/hoodie/">hoodie</a> or
<a href="/catalog/long-sleeve/">long sleeve</a>.</p>
<details>
  <summary>Why a TwoComms t-shirt isn't just a t-shirt?</summary>
  <p>We use 180–220 g/m² cotton jersey, original DTF prints and our own
  patterns in oversize and classic cuts. Every model is part of the
  <a href="/pro-brand/">TwoComms brand DNA</a>: military aesthetic
  without the bravado, patriotic symbols without the kitsch.</p>
</details>
""",
    "long-sleeve": """
<p><strong>TwoComms long sleeves</strong> are the streetwear-wardrobe
mid-layer — heavier than a t-shirt, lighter than a hoodie. We stock
<a href="/catalog/long-sleeve/?color=black">a black long sleeve</a>,
<a href="/catalog/long-sleeve/?color=coyote">coyote</a>, and base
colours that pair with our <a href="/catalog/hoodie/">hoodies</a> and
<a href="/catalog/tshirts/">t-shirts</a>.</p>
<details>
  <summary>When to wear a long sleeve?</summary>
  <p>The long sleeve fits cool weather, layering under a hoodie, or
  works as a standalone top. TwoComms long sleeves carry our military
  DNA: clean prints, reinforced cuffs, fabric that holds shape after
  washing. Read more about the
  <a href="/pro-brand/">TwoComms philosophy</a>.</p>
</details>
""",
}


def seed_translations(apps, schema_editor):
    Category = apps.get_model("storefront", "Category")
    for slug, ru_text in DESCRIPTION_RU.items():
        en_text = DESCRIPTION_EN.get(slug, "")
        intro_ru = SEO_INTRO_HTML_RU.get(slug, "")
        intro_en = SEO_INTRO_HTML_EN.get(slug, "")
        try:
            cat = Category.objects.get(slug=slug)
        except Category.DoesNotExist:
            continue

        updated = False

        if not (cat.description_ru or "").strip():
            cat.description_ru = ru_text.strip()
            updated = True
        if not (cat.description_en or "").strip():
            cat.description_en = en_text.strip()
            updated = True
        if not (cat.seo_intro_html_ru or "").strip():
            cat.seo_intro_html_ru = intro_ru.strip()
            updated = True
        if not (cat.seo_intro_html_en or "").strip():
            cat.seo_intro_html_en = intro_en.strip()
            updated = True

        if updated:
            cat.save(update_fields=[
                "description_ru", "description_en",
                "seo_intro_html_ru", "seo_intro_html_en",
            ])


def reverse_noop(apps, schema_editor):
    """Translations are additive — keep them on rollback to avoid
    re-translating manually if the migration is re-run."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0061_categorycolorlanding"),
    ]

    operations = [
        migrations.RunPython(seed_translations, reverse_noop),
    ]
