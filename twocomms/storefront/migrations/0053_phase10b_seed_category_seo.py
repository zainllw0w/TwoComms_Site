"""Phase 10b — seed SEO copy + structured blocks for the three live
TwoComms categories (``hoodie`` / ``tshirts`` / ``long-sleeve``).

Idempotent: skips a category if its ``description`` already contains
content (manual edits win) and skips a block type if any active block of
the same type already exists for that category.

Copy targets:
  * H1 — handled by ``Category.name`` in the catalog template.
  * ``seo_intro_html`` — short intro under H1 with a ``<details>``
    "Що таке X?" expandable, mirroring the AAC pattern. 1–3 sentences
    of HF keywords + a brief explainer behind the toggle.
  * ``description`` — long-form HTML below the SEO blocks: H2/H3
    structure, internal links, mid-frequency phrasing.
  * ``seo_text_title`` — H2 above the long-form text.
  * ``CategorySeoBlock`` rows:
      - ``top_menu``     — links to sister categories + brand pages.
      - ``top_filters``  — colour/size/fit pre-filtered listings.
      - ``top_queries``  — long-tail queries (LF), each linked to a
        meaningful internal URL (filtered listing or other category).
      - ``best_prices``  — top published products in the category by
        ``priority`` desc; falls back gracefully when the catalogue is
        empty (e.g. fresh installs / test DBs).

The migration is intentionally wordy so an editor can copy-paste
sections to other categories or to a future Phase 11 admin WYSIWYG.
"""
from __future__ import annotations

from django.db import migrations


# --------------------------------------------------------------------- copy

# H2 over the long-form text. Empty → falls back to category.name.
SEO_TEXT_TITLES = {
    "hoodie":      "Худі TwoComms — патріотичний streetwear з мілітарним характером",
    "tshirts":     "Футболки TwoComms — авторські принти ЗСУ та український streetwear",
    "long-sleeve": "Лонгсліви TwoComms — тактичний streetwear на кожен день",
}

# Short intro shown ABOVE the products grid. HTML is rendered with
# ``|safe`` and styled by ``.catalog-intro-panel`` (glass / neon).
SEO_INTRO_HTML = {
    "hoodie": """
<p><strong>Худі TwoComms</strong> — це український streetwear із мілітарним
ДНК: щільна тканина, посилені шви, авторські принти на тему ЗСУ,
тризуба та свободи. Можна <a href="/catalog/hoodie/?color=black">купити чорне худі</a>,
<a href="/catalog/hoodie/?color=coyote">кайот-кольору</a> або підібрати
<a href="/catalog/tshirts/">футболку</a> чи <a href="/catalog/long-sleeve/">лонгслів</a>
у тон.</p>
<details>
  <summary>Що таке худі TwoComms?</summary>
  <p>Худі — базовий елемент гардероба, який поєднує комфорт спортивного
  одягу з силуетом сучасного streetwear. У TwoComms ми робимо акцент на
  патріотичних принтах, якісному друці DTF та фурнітурі, що витримує
  щоденне носіння. Усі худі шиються в Україні, із власним
  <a href="/pro-brand/">мілітарним наративом бренду</a>.</p>
</details>
""",
    "tshirts": """
<p><strong>Футболки TwoComms</strong> — це лаконічний український streetwear
з мілітарними акцентами та принтами на тему ЗСУ. Можна
<a href="/catalog/tshirts/?color=black">купити чорну футболку</a>,
<a href="/catalog/tshirts/?color=olive">олива</a> або
<a href="/catalog/tshirts/?color=white">білу</a>, а також доповнити її
<a href="/catalog/hoodie/">худі</a> чи <a href="/catalog/long-sleeve/">лонгслівом</a>.</p>
<details>
  <summary>Чому футболка TwoComms — це не просто футболка?</summary>
  <p>Ми використовуємо щільний бавовняний трикотаж 180–220 г/м², авторські
  принти у DTF-друці та власні лекала з оверсайз/класичними силуетами.
  Кожна модель — частина <a href="/pro-brand/">brand DNA TwoComms</a>:
  мілітарна естетика без зайвого пафосу, патріотичні символи без
  «лубочності».</p>
</details>
""",
    "long-sleeve": """
<p><strong>Лонгсліви TwoComms</strong> — універсальний шар streetwear-гардероба:
сильніший за футболку, легший за худі. У наявності
<a href="/catalog/long-sleeve/?color=black">чорний лонгслів</a>,
<a href="/catalog/long-sleeve/?color=coyote">кайот</a> та класичні
кольори, які добре поєднуються з <a href="/catalog/hoodie/">худі</a> і
<a href="/catalog/tshirts/">футболками</a> з нашого каталогу.</p>
<details>
  <summary>Коли носити лонгслів?</summary>
  <p>Лонгслів — ідеальний вибір для прохолодної погоди, шарування під
  худі або як самостійний топ. У TwoComms лонгсліви виконані в
  мілітарному ДНК: акуратні принти, посилені манжети, тканина, що
  тримає форму після прання. Дізнайтеся більше про
  <a href="/pro-brand/">філософію TwoComms</a>.</p>
</details>
""",
}

# Long-form SEO HTML rendered by ``.catalog-description-panel`` BELOW the
# tabbed blocks. H2/H3 hierarchy, internal links to sister categories,
# colour-filtered listings, and brand pages.
SEO_DESCRIPTION_HTML = {
    "hoodie": """
<p>У каталозі <strong>худі TwoComms</strong> ви знайдете
<a href="/catalog/hoodie/?color=black">чорні</a>,
<a href="/catalog/hoodie/?color=coyote">кайот</a>,
оливкові й нейтральні моделі — оверсайз і класичного силуету.
Усі худі шиються в Україні з прицілом на щоденне носіння та
сумісність із <a href="/catalog/long-sleeve/">лонгслівами</a> й
<a href="/catalog/tshirts/">футболками</a> бренду.</p>

<h3>Як обрати худі</h3>
<p>Підбирайте розмір за <a href="/rozmirna-sitka/">розмірною сіткою</a>:
для шарування з лонгслівом беріть свій звичний розмір, для оверсайз-силуету
— на 1 більше. Догляд — на сторінці
<a href="/doglyad-za-odyagom/">догляд за одягом</a>.</p>

<h3>Доставка та оплата</h3>
<p>Доставляємо <a href="/delivery/">Новою Поштою</a> по всій Україні
(відділення / поштомат / адресна доставка). Оплата — Monobank, наложений
платіж, оплата на картку. <a href="/povernennya-ta-obmin/">Повернення</a>
протягом 14 днів.</p>

<h3>Чому TwoComms</h3>
<p>TwoComms — український streetwear з мілітарним ДНК: ми робимо одяг
для тих, хто живе в Україні, підтримує ЗСУ та цінує спокійну, але сильну
естетику. Дізнайтеся більше про
<a href="/pro-brand/">філософію бренду</a>.</p>
""",
    "tshirts": """
<p>Каталог <strong>футболок TwoComms</strong> — це понад десяток
авторських принтів у мілітарно-патріотичному ДНК: тризуб, ЗСУ,
streetwear-графіка. Можна
<a href="/catalog/tshirts/?color=black">купити чорну футболку</a>,
<a href="/catalog/tshirts/?color=white">білу</a> або
<a href="/catalog/tshirts/?color=olive">оливу</a>, а також зібрати
комплект з <a href="/catalog/hoodie/">худі</a> чи
<a href="/catalog/long-sleeve/">лонгслівом</a>.</p>

<h3>Силуети та посадки</h3>
<p>В асортименті — класичний крій (regular fit) і oversize. Для
оверсайз-комплектів дивіться <a href="/catalog/tshirts/?fit=oversize">фільтр
oversize</a>. <a href="/rozmirna-sitka/">Розмірна сітка</a> допоможе
вибрати точно.</p>

<h3>Принти та символіка</h3>
<p>Більшість принтів TwoComms — це авторські ілюстрації з мілітарним і
streetwear-настроєм. Ми не використовуємо «лубочну» символіку — лише
сучасні візуальні рішення, що добре виглядають у місті й комбінуються
з нашими <a href="/catalog/hoodie/">худі</a> та лонгслівами.</p>

<h3>Доставка та оплата</h3>
<p><a href="/delivery/">Доставка Новою Поштою</a> по всій Україні,
оплата — Monobank / накладений платіж / картка. Подробиці на
<a href="/dopomoga/">сторінці допомоги</a>.</p>
""",
    "long-sleeve": """
<p>Каталог <strong>лонгслівів TwoComms</strong> — для тих, кому замало
футболки, але худі поки зайве. Підберіть
<a href="/catalog/long-sleeve/?color=black">чорний лонгслів</a>,
<a href="/catalog/long-sleeve/?color=coyote">кайот</a> або базові кольори,
що добре сидять під <a href="/catalog/hoodie/">худі</a> або самостійно.</p>

<h3>Як носити лонгслів</h3>
<p>Лонгслів — універсальний базовий шар: можна носити окремо, шарувати
під худі або легку куртку. Для холоднішої погоди подивіться розділ
<a href="/catalog/hoodie/">худі</a>. Для теплих днів — наш каталог
<a href="/catalog/tshirts/">футболок</a>.</p>

<h3>Розмір і догляд</h3>
<p>Орієнтуйтеся на <a href="/rozmirna-sitka/">розмірну сітку</a>: класичний
silhouette = свій розмір, oversize = +1. Інструкції з прання — у
<a href="/doglyad-za-odyagom/">догляді за одягом</a>.</p>

<h3>Чому TwoComms</h3>
<p>Ми — український бренд із мілітарним ДНК: одяг для патріотів,
прихильників ЗСУ та streetwear-естетики водночас. Більше — на сторінці
<a href="/pro-brand/">про бренд</a>.</p>
""",
}


# Structured tab blocks (top_menu / top_filters / top_queries) per category.
# Each list entry: (label, url). ``best_prices`` is built dynamically from
# real Product rows further below.

TOP_MENU = {
    "hoodie": [
        ("Усі худі",            "/catalog/hoodie/"),
        ("Футболки",            "/catalog/tshirts/"),
        ("Лонгсліви",           "/catalog/long-sleeve/"),
        ("Про бренд",           "/pro-brand/"),
        ("Розмірна сітка",      "/rozmirna-sitka/"),
        ("Догляд за одягом",    "/doglyad-za-odyagom/"),
    ],
    "tshirts": [
        ("Усі футболки",        "/catalog/tshirts/"),
        ("Худі",                "/catalog/hoodie/"),
        ("Лонгсліви",           "/catalog/long-sleeve/"),
        ("Про бренд",           "/pro-brand/"),
        ("Розмірна сітка",      "/rozmirna-sitka/"),
        ("Догляд за одягом",    "/doglyad-za-odyagom/"),
    ],
    "long-sleeve": [
        ("Усі лонгсліви",       "/catalog/long-sleeve/"),
        ("Худі",                "/catalog/hoodie/"),
        ("Футболки",            "/catalog/tshirts/"),
        ("Про бренд",           "/pro-brand/"),
        ("Розмірна сітка",      "/rozmirna-sitka/"),
        ("Догляд за одягом",    "/doglyad-za-odyagom/"),
    ],
}

TOP_FILTERS = {
    "hoodie": [
        ("Чорне худі",            "/catalog/hoodie/?color=black"),
        ("Худі кайот",            "/catalog/hoodie/?color=coyote"),
        ("Олива",                 "/catalog/hoodie/?color=olive"),
        ("Сіре худі",             "/catalog/hoodie/?color=grey"),
        ("Худі oversize",         "/catalog/hoodie/?fit=oversize"),
        ("Худі classic",          "/catalog/hoodie/?fit=classic"),
        ("Розмір M",              "/catalog/hoodie/?size=M"),
        ("Розмір L",              "/catalog/hoodie/?size=L"),
        ("Розмір XL",             "/catalog/hoodie/?size=XL"),
        ("Розмір XXL",            "/catalog/hoodie/?size=XXL"),
    ],
    "tshirts": [
        ("Чорна футболка",        "/catalog/tshirts/?color=black"),
        ("Біла футболка",         "/catalog/tshirts/?color=white"),
        ("Олива",                 "/catalog/tshirts/?color=olive"),
        ("Кайот",                 "/catalog/tshirts/?color=coyote"),
        ("Футболка oversize",     "/catalog/tshirts/?fit=oversize"),
        ("Футболка classic",      "/catalog/tshirts/?fit=classic"),
        ("Розмір S",              "/catalog/tshirts/?size=S"),
        ("Розмір M",              "/catalog/tshirts/?size=M"),
        ("Розмір L",              "/catalog/tshirts/?size=L"),
        ("Розмір XL",             "/catalog/tshirts/?size=XL"),
    ],
    "long-sleeve": [
        ("Чорний лонгслів",       "/catalog/long-sleeve/?color=black"),
        ("Кайот",                 "/catalog/long-sleeve/?color=coyote"),
        ("Олива",                 "/catalog/long-sleeve/?color=olive"),
        ("Білий лонгслів",        "/catalog/long-sleeve/?color=white"),
        ("Лонгслів oversize",     "/catalog/long-sleeve/?fit=oversize"),
        ("Лонгслів classic",      "/catalog/long-sleeve/?fit=classic"),
        ("Розмір M",              "/catalog/long-sleeve/?size=M"),
        ("Розмір L",              "/catalog/long-sleeve/?size=L"),
        ("Розмір XL",             "/catalog/long-sleeve/?size=XL"),
    ],
}

# Long-tail / mid-tail queries. Each query routes to a meaningful internal
# URL (filtered listing or sister category). NEVER points to a search page
# that returns "0 results" — that hurts user trust and crawl quality.
TOP_QUERIES = {
    "hoodie": [
        ("Купити худі ЗСУ",                 "/catalog/hoodie/"),
        ("Худі з тризубом",                 "/catalog/hoodie/"),
        ("Патріотичне худі чоловіче",       "/catalog/hoodie/"),
        ("Худі з принтом Україна",          "/catalog/hoodie/"),
        ("Тактичне худі",                   "/catalog/hoodie/?color=coyote"),
        ("Чорне худі чоловіче",             "/catalog/hoodie/?color=black"),
        ("Військове худі купити",           "/catalog/hoodie/"),
        ("Худі oversize Україна",           "/catalog/hoodie/?fit=oversize"),
        ("Худі Київ",                       "/catalog/hoodie/"),
        ("Худі Львів",                      "/catalog/hoodie/"),
        ("Стрітвір худі",                   "/catalog/hoodie/"),
        ("Худі унісекс",                    "/catalog/hoodie/"),
        ("Українське худі",                 "/catalog/hoodie/"),
        ("Худі для ЗСУ подарунок",          "/catalog/hoodie/"),
        ("Худі бавовна",                    "/catalog/hoodie/"),
        ("Купити худі чоловіче",            "/catalog/hoodie/"),
    ],
    "tshirts": [
        ("Футболка ЗСУ",                    "/catalog/tshirts/"),
        ("Футболка тризуб",                 "/catalog/tshirts/"),
        ("Патріотична футболка",            "/catalog/tshirts/"),
        ("Футболка Україна",                "/catalog/tshirts/"),
        ("Чорна футболка чоловіча",         "/catalog/tshirts/?color=black"),
        ("Біла футболка з принтом",         "/catalog/tshirts/?color=white"),
        ("Футболка олива",                  "/catalog/tshirts/?color=olive"),
        ("Тактична футболка",               "/catalog/tshirts/?color=coyote"),
        ("Військова футболка",              "/catalog/tshirts/"),
        ("Стрітвір футболка",               "/catalog/tshirts/"),
        ("Футболка oversize",               "/catalog/tshirts/?fit=oversize"),
        ("Футболка унісекс",                "/catalog/tshirts/"),
        ("Українська футболка купити",      "/catalog/tshirts/"),
        ("Футболка бавовна",                "/catalog/tshirts/"),
        ("Футболка з принтом ЗСУ",          "/catalog/tshirts/"),
        ("Футболка для ЗСУ подарунок",      "/catalog/tshirts/"),
    ],
    "long-sleeve": [
        ("Лонгслів чоловічий",              "/catalog/long-sleeve/"),
        ("Лонгслів ЗСУ",                    "/catalog/long-sleeve/"),
        ("Тактичний лонгслів",              "/catalog/long-sleeve/?color=coyote"),
        ("Чорний лонгслів",                 "/catalog/long-sleeve/?color=black"),
        ("Лонгслів олива",                  "/catalog/long-sleeve/?color=olive"),
        ("Український лонгслів",            "/catalog/long-sleeve/"),
        ("Патріотичний лонгслів",           "/catalog/long-sleeve/"),
        ("Лонгслів з принтом",              "/catalog/long-sleeve/"),
        ("Стрітвір лонгслів",               "/catalog/long-sleeve/"),
        ("Лонгслів oversize",               "/catalog/long-sleeve/?fit=oversize"),
        ("Лонгслів унісекс",                "/catalog/long-sleeve/"),
        ("Лонгслів бавовна",                "/catalog/long-sleeve/"),
        ("Лонгслів подарунок ЗСУ",          "/catalog/long-sleeve/"),
        ("Купити лонгслів Україна",         "/catalog/long-sleeve/"),
    ],
}


# --------------------------------------------------------------------- ops

CATEGORY_SLUGS = ("hoodie", "tshirts", "long-sleeve")


def _seed_blocks_for_category(apps, category, slug):
    CategorySeoBlock = apps.get_model("storefront", "CategorySeoBlock")
    CategorySeoBlockItem = apps.get_model("storefront", "CategorySeoBlockItem")
    Product = apps.get_model("storefront", "Product")

    def _ensure_block(block_type, title, items, order):
        # Idempotent: skip if any active block of that type already exists.
        if CategorySeoBlock.objects.filter(
            category=category, block_type=block_type, is_active=True,
        ).exists():
            return
        block = CategorySeoBlock.objects.create(
            category=category,
            block_type=block_type,
            title=title,
            is_active=True,
            order=order,
        )
        for idx, payload in enumerate(items):
            CategorySeoBlockItem.objects.create(
                block=block,
                label=payload["label"],
                url=payload.get("url", ""),
                extra=payload.get("extra") or {},
                order=idx,
            )

    # --- top_menu / top_filters / top_queries ---
    _ensure_block(
        "top_menu", "ТОП меню",
        [{"label": l, "url": u} for l, u in TOP_MENU.get(slug, [])],
        order=1,
    )
    _ensure_block(
        "top_filters", "ТОП фільтри",
        [{"label": l, "url": u} for l, u in TOP_FILTERS.get(slug, [])],
        order=2,
    )
    _ensure_block(
        "top_queries", "ТОП запити",
        [{"label": l, "url": u} for l, u in TOP_QUERIES.get(slug, [])],
        order=3,
    )

    # --- best_prices: from real Product rows (top 8 by priority, published) ---
    if not CategorySeoBlock.objects.filter(
        category=category, block_type="best_prices", is_active=True,
    ).exists():
        # Historical migrations get the model without @property accessors,
        # so we can't use ``final_price``. Fall back to ``price`` minus
        # ``discount_percent`` if any.
        products = list(
            Product.objects.filter(category=category, status="published")
            .only("id", "title", "price", "discount_percent", "priority")
            .order_by("-priority", "-id")[:8]
        )
        if products:
            block = CategorySeoBlock.objects.create(
                category=category,
                block_type="best_prices",
                title=f"Найкращі ціни на {category.name.lower()} в TwoComms",
                is_active=True,
                order=4,
            )
            for idx, p in enumerate(products):
                discount = int(p.discount_percent or 0)
                final_price = (
                    int(p.price * (100 - discount) / 100) if discount else int(p.price)
                )
                CategorySeoBlockItem.objects.create(
                    block=block,
                    label=p.title,
                    url=f"/product/{p.id}/",  # historical routing — view will
                    # rewrite to slug-based URL on render via Product.product
                    # hydration in the service (we store product_id below).
                    extra={"product_id": p.id, "price": final_price},
                    order=idx,
                )


def seed_seo_copy(apps, schema_editor):
    Category = apps.get_model("storefront", "Category")
    for slug in CATEGORY_SLUGS:
        category = Category.objects.filter(slug=slug).first()
        if not category:
            # Empty / fresh DB (e.g. test) — nothing to seed for this slug.
            continue

        update_fields = []
        # ``description`` — only seed if empty (preserve manual edits).
        if not (category.description or "").strip():
            category.description = SEO_DESCRIPTION_HTML.get(slug, "").strip()
            update_fields.append("description")
        # ``seo_text_title`` — same.
        if not (category.seo_text_title or "").strip():
            category.seo_text_title = SEO_TEXT_TITLES.get(slug, "")
            update_fields.append("seo_text_title")
        # ``seo_intro_html`` — same.
        if not (category.seo_intro_html or "").strip():
            category.seo_intro_html = SEO_INTRO_HTML.get(slug, "").strip()
            update_fields.append("seo_intro_html")

        if update_fields:
            category.save(update_fields=update_fields)

        _seed_blocks_for_category(apps, category, slug)


def reverse_noop(apps, schema_editor):
    """Reverse is a no-op: data migrations should not destroy editorial
    content on rollback. To wipe seeded content, do it explicitly via
    the admin or a separate migration."""
    return


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0052_phase10b_category_seo_intro"),
    ]

    operations = [
        migrations.RunPython(seed_seo_copy, reverse_noop),
    ]
