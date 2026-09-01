"""Послідовний прогон візуальних форматів на власному акаунті.

**Навіщо це існує, якщо є тести.** Django-тести на production запустити
неможливо: у боєвого користувача БД немає права `CREATE` на схему `test_%`
(`08_IMPLEMENTATION_FINDINGS_LOG.md`, B17). Але навіть якби були — тест не
показує, ЯК карточка виглядає в реальному Instagram: чи влазить підпис кнопки, чи
не обрізається subtitle з номером відділення, чи не залишається висіти нижнє меню
після натискання, чи не перетворюється діалог у меню. Це перевіряється тільки
відправкою на власний акаунт і поглядом на екран.

**Чому по одному кроку.** Мета — побачити кожен формат окремо і натиснути кнопку,
а не отримати сім повідомлень підряд. Десять карточок поспіль не покажуть нічого,
крім того, що бот спамить.

**Головний запобіжник: прогон нічого не змінює.** Кнопки прогону несуть action
`wt` у наявному versioned-namespace (`twc:1:wt:...`). Роутер postback не знає
такої дії, а невідома дія за Э1.4 вже дає мʼяку відмову замість помилки — тому
натискання під час прогону НЕ створює proposal, invoice, consent або замовлення.
Це свідомий вибір: показати вигляд, не торкаючись комерційного стану.

**Дані беруться справжні.** Категорії і товари читаються з `build_catalog_graph()`,
а не вигадуються: карточка з неіснуючим товаром нічого не доводить про вигляд
реального каталогу. Ціни й наявність показуються як у каталозі на момент запуску.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from management.services import ig_message_templates as tpl

# Порядок від безпечного до того, що торкається грошей.
STEP_ORDER = (
    "category_carousel",
    "product_carousel",
    "size_quick_replies",
    "payment_card",
)

WALKTHROUGH_ACTION = "wt"

# Ліміт вікна Meta. 24 години — платформна межа; 20 годин — власний safe-deadline
# з `10_VISUAL_MESSAGING.md` §9, щоб не впиратись у край.
META_WINDOW = timedelta(hours=24)
SAFE_WINDOW = timedelta(hours=20)


@dataclass(frozen=True)
class StepPlan:
    step: str
    lang: str
    kind: str          # carousel | quick_replies | button_card | text
    payload: object
    note: str = ""

    def describe(self) -> list:
        lines = [f"формат: {self.kind}", f"крок: {self.step}", f"мова: {self.lang}"]
        if self.note:
            lines.append(f"нотатка: {self.note}")
        payload = self.payload
        cards = getattr(payload, "cards", None)
        if cards:
            lines.append(f"елементів у каруселі: {len(cards)}")
            for card in cards:
                buttons = " / ".join(b.title for b in card.buttons) or "—"
                lines.append(f"  • {card.title} | {card.subtitle or '—'} | [{buttons}]")
        text = getattr(payload, "text", "")
        if text:
            lines.append(f"текст: {text}")
        quick = getattr(payload, "quick_replies", ())
        if quick:
            lines.append("quick replies: " + " / ".join(q.title for q in quick))
        buttons = getattr(payload, "buttons", ())
        if buttons and not cards:
            lines.append("кнопки: " + " / ".join(b.title for b in buttons))
        lines.append(f"fallback: {getattr(payload, 'fallback_text', '')}")
        return lines


def window_state(client, *, now=None) -> dict:
    """Стан вікна Meta для цього клієнта — читанням, без запиту до провайдера."""
    now = now or timezone.now()
    last = getattr(client, "last_user_message_at", None)
    if not last:
        return {
            "state": "немає вхідного",
            "last_inbound_at": None,
            "can_send": False,
            "remaining_human": "—",
        }
    age = now - last
    remaining = SAFE_WINDOW - age
    if age >= META_WINDOW:
        state = "закрите (>24 год)"
    elif age >= SAFE_WINDOW:
        state = "лише reactive (20–24 год)"
    else:
        state = "відкрите"
    total_minutes = int(max(0, remaining.total_seconds()) // 60)
    return {
        "state": state,
        "last_inbound_at": last,
        "can_send": age < META_WINDOW,
        "remaining_human": f"{total_minutes // 60} год {total_minutes % 60} хв",
    }


def _catalog_products(limit: int = 3) -> list:
    from management.services.ig_catalog_graph import build_catalog_graph

    graph = build_catalog_graph()
    products = sorted(
        graph.products,
        key=lambda item: (-int(item.catalog_priority or 0), item.title),
    )
    return list(products[:limit])


def _product_image(product) -> str:
    """Довірений абсолютний URL картинки товару або порожній рядок.

    Порожнє значення — нормальний результат: за `10` §12.8 відсутній ассет
    деградує до карточки без картинки, а не до вигаданого фото.
    """
    try:
        from django.apps import apps

        from management.services.ig_catalog_media import _product_assets

        model = apps.get_model("storefront", "Product")
        row = model.objects.filter(pk=product.product_id).first()
        if row is None:
            return ""
        assets = _product_assets(row)
        return assets[0][0] if assets else ""
    except Exception:
        return ""


def _product_url(product) -> str:
    from management.services.ig_catalog_media import _base_url

    slug = str(getattr(product, "slug", "") or "").strip("/")
    return f"{_base_url()}/product/{slug}/" if slug else _base_url()


def _price_text(product, lang: str) -> str:
    """Ціна для subtitle карточки з `PriceSnapshot`.

    Поля саме такі: `display` (готовий рядок), інакше `minimum`/`maximum` і
    прапорець `exact`. Порожній subtitle — теж валідний результат: карточка без
    ціни краща за карточку з вигаданою ціною, а `10` §6 вимагає перепроверять
    price перед кожним `Обрати` в реальному потоці.
    """
    pricing = getattr(product, "pricing", None)
    if pricing is None:
        return ""
    unit = {"uk": "грн", "ru": "грн", "en": "UAH"}[lang]
    display = str(getattr(pricing, "display", "") or "").strip()
    if display:
        # `display` у каталозі — це «1090», без валюти: у сітці сайту одиниця
        # намальована окремо. У subtitle карточки такої підказки немає, і бачити
        # «1090» без «грн» клієнту доводиться домислювати. Додаємо одиницю лише
        # коли її справді немає, щоб не отримати «1090 грн грн».
        if not any(ch.isalpha() for ch in display) and "₴" not in display:
            return f"{display} {unit}"
        return display
    minimum = getattr(pricing, "minimum", None)
    maximum = getattr(pricing, "maximum", None)
    if minimum and maximum and minimum != maximum and not getattr(pricing, "exact", False):
        return f"{minimum}–{maximum} {unit}"
    amount = minimum or maximum
    return f"{amount} {unit}" if amount else ""


def build_step(step: str, *, client, lang: str = "uk") -> StepPlan:
    if step not in STEP_ORDER:
        raise ValueError(f"unknown walkthrough step: {step}")
    return _BUILDERS[step](client=client, lang=lang)


def _label(key: str, lang: str) -> str:
    return tpl.button_label(key, lang)


def _wt_payload(*args: str) -> str:
    return tpl.build_payload(WALKTHROUGH_ACTION, *args)


def _build_category_carousel(*, client, lang: str) -> StepPlan:
    """Категорії — тільки коли garment реально невідомий (`10` §6)."""
    seen: dict = {}
    for product in _catalog_products(limit=30):
        key = product.category_slug or product.category_label
        if key and key not in seen:
            seen[key] = product
    cards = []
    for product in list(seen.values())[:3]:
        cards.append(
            tpl.TemplateCard(
                title=tpl.display_short(product.category_label or product.title),
                subtitle="",
                image_url=_product_image(product),
                default_url=_product_url(product),
                buttons=(
                    tpl.TemplateButton(
                        tpl.BUTTON_POSTBACK,
                        _label("product_select", lang),
                        payload=_wt_payload("cat", str(product.category_id)),
                    ),
                ),
            )
        )
    fallback = {
        "uk": "Є футболки, худі та лонгсліви — що дивимо?",
        "ru": "Есть футболки, худи и лонгсливы — что смотрим?",
        "en": "We have tees, hoodies and longsleeves — what are we looking at?",
    }[lang]
    return StepPlan(
        step="category_carousel",
        lang=lang,
        kind="carousel",
        payload=tpl.GenericTemplate(cards=tuple(cards), fallback_text=fallback),
        note="категорії допустимі лише при невідомому garment; якщо клієнт уже "
             "назвав «футболки Харкова» — має бути product carousel з фільтром",
    )


def _build_product_carousel(*, client, lang: str) -> StepPlan:
    """2–3 товари — одна сторінка каруселі (`10` §6)."""
    products = _catalog_products(limit=3)
    cards = []
    for product in products:
        subtitle = _price_text(product, lang)
        cards.append(
            tpl.TemplateCard(
                title=tpl.display_short(product.title),
                subtitle=subtitle,
                image_url=_product_image(product),
                default_url=_product_url(product),
                buttons=(
                    tpl.TemplateButton(
                        tpl.BUTTON_POSTBACK,
                        _label("product_select", lang),
                        payload=_wt_payload("pick", str(product.product_id)),
                    ),
                    tpl.TemplateButton(
                        tpl.BUTTON_WEB_URL,
                        _label("product_details", lang),
                        url=_product_url(product),
                    ),
                ),
            )
        )
    fallback = {
        "uk": "Ось що є — обирайте або напишіть, який принт шукаєте.",
        "ru": "Вот что есть — выбирайте или напишите, какой принт ищете.",
        "en": "Here is what we have — pick one or tell me the print you want.",
    }[lang]
    return StepPlan(
        step="product_carousel",
        lang=lang,
        kind="carousel",
        payload=tpl.GenericTemplate(cards=tuple(cards), fallback_text=fallback),
        note="кнопка «Обрати» дає боту однозначний товар замість «давай другу фотографію»",
    )


def _build_size_quick_replies(*, client, lang: str) -> StepPlan:
    """Розміри — quick replies, і ТІЛЬКИ ті, що справді доступні (`10` §6).

    Джерело розмірів — `PriceSnapshot.configurations[*].compatible_sizes`, а не
    `variants`: варіант у цьому графі — це колір, у нього немає розміру. Помилка
    була б тиха і найгіршого роду: кнопки все одно показались би, просто набір
    став би вигаданим, і клієнт обрав би розмір, якого немає.

    Якщо доступний рівно один розмір, кнопок немає взагалі: це факт, а не вибір.
    """
    products = _catalog_products(limit=1)
    sizes: list = []
    source = "compatible_sizes"
    if products:
        pricing = getattr(products[0], "pricing", None)
        for configuration in getattr(pricing, "configurations", ()) or ():
            for size in getattr(configuration, "compatible_sizes", ()) or ():
                value = str(size or "").strip().upper()
                if value and value not in sizes:
                    sizes.append(value)
    if not sizes:
        # Порожній набір — це не привід вигадати сітку. Показуємо текст і кажемо
        # прямо, що наявність треба уточнити.
        text = {
            "uk": "Уточню наявні розміри й повернуся — у каталозі їх зараз не видно.",
            "ru": "Уточню доступные размеры и вернусь — в каталоге их сейчас не видно.",
            "en": "Let me check which sizes are in stock and come back to you.",
        }[lang]
        return StepPlan(
            step="size_quick_replies",
            lang=lang,
            kind="text",
            payload=tpl.ButtonTemplate(
                text=text,
                buttons=(
                    tpl.TemplateButton(
                        tpl.BUTTON_POSTBACK,
                        _label("size_help", lang),
                        payload=_wt_payload("size", "help"),
                    ),
                ),
                fallback_text=text,
            ),
            note="каталог не віддав compatible_sizes — вигаданої сітки не показуємо",
        )

    order = {"XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4, "XXL": 5, "XXXL": 6}
    sizes.sort(key=lambda value: order.get(value, 99))

    if len(sizes) == 1:
        only = sizes[0]
        text = {
            "uk": f"Зараз є тільки розмір {only}.",
            "ru": f"Сейчас есть только размер {only}.",
            "en": f"Only size {only} is in stock right now.",
        }[lang]
        return StepPlan(
            step="size_quick_replies",
            lang=lang,
            kind="text",
            payload=tpl.ButtonTemplate(
                text=text,
                buttons=(
                    tpl.TemplateButton(
                        tpl.BUTTON_POSTBACK,
                        _label("product_select", lang),
                        payload=_wt_payload("size", only),
                    ),
                ),
                fallback_text=text,
            ),
            note="один доступний розмір — це факт, а не вибір, тому набору кнопок немає",
        )

    key_map = {
        "XS": "size_xs", "S": "size_s", "M": "size_m", "L": "size_l",
        "XL": "size_xl", "XXL": "size_xxl", "XXXL": "size_xxxl",
    }
    quick = [
        tpl.QuickReply(
            _label(key_map.get(size, ""), lang) or size, _wt_payload("size", size)
        )
        for size in sizes[: tpl.MAX_QUICK_REPLIES]
    ]
    text = {
        "uk": "Який розмір? Показую тільки ті, що є в наявності.",
        "ru": "Какой размер? Показываю только те, что есть в наличии.",
        "en": "Which size? Only the ones in stock are listed.",
    }[lang]
    return StepPlan(
        step="size_quick_replies",
        lang=lang,
        kind="quick_replies",
        payload=tpl.GenericTemplate(
            cards=(tpl.TemplateCard(title=text, subtitle=""),),
            fallback_text=text,
            quick_replies=tuple(quick),
        ),
        note=(
            f"джерело: {source}; доступних розмірів {len(sizes)} "
            f"({', '.join(sizes)}); кнопок на карточці максимум "
            f"{tpl.MAX_BUTTONS_PER_ELEMENT}, тому це quick replies"
        ),
    )


def _build_payment_card(*, client, lang: str) -> StepPlan:
    """Кнопка замість довгого URL. У прогоні веде на сайт, не на інвойс."""
    from management.services.ig_catalog_media import _base_url

    text = {
        "uk": "Тестова карточка оплати — кнопка замість довгого посилання.",
        "ru": "Тестовая карточка оплаты — кнопка вместо длинной ссылки.",
        "en": "Test payment card — a button instead of a long link.",
    }[lang]
    return StepPlan(
        step="payment_card",
        lang=lang,
        kind="button_card",
        payload=tpl.ButtonTemplate(
            text=text,
            buttons=(
                tpl.TemplateButton(
                    tpl.BUTTON_WEB_URL, _label("pay_online", lang), url=_base_url()
                ),
            ),
            fallback_text=text,
        ),
        note="у прогоні URL веде на сайт, а не на реальний інвойс: показуємо вигляд, "
             "не створюючи платіжного зобов'язання",
    )


_BUILDERS = {
    "category_carousel": _build_category_carousel,
    "product_carousel": _build_product_carousel,
    "size_quick_replies": _build_size_quick_replies,
    "payment_card": _build_payment_card,
}


def deliver(plan: StepPlan, *, settings_row, client) -> str:
    """Відправити один крок. Повертає читабельний результат."""
    recipient = str(client.igsid)
    if plan.kind == "button_card":
        outcome = tpl.send_button_template(settings_row, recipient, plan.payload)
    else:
        outcome = tpl.send_template(settings_row, recipient, plan.payload)
    return (
        f"ok={getattr(outcome, 'ok', None)} kind={getattr(outcome, 'kind', '')} "
        f"hint={getattr(outcome, 'hint', '')}"
    )
