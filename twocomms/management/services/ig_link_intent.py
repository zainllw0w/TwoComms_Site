"""Яке саме посилання просить клієнт — вирішується станом, а не вгадуванням.

**Звідки взялось.** Прогон на власному акаунті: клієнт написав «дай посилання»
після розмови про оплату, а бот надіслав посилання на САЙТ — і надіслав його
голим URL у тексті, без кнопки. Дві різні помилки в одній відповіді:

1. Неправильна ціль. Слово «посилання» саме по собі не називає ціль. У розмові
   про оплату найімовірніша ціль — платіжне посилання, і якщо його немає, чесна
   відповідь «його ще не сформовано» корисніша за посилання на сайт, яке клієнт
   не просив. Підмінити ціль гірше, ніж перепитати.
2. Гола URL замість кнопки. Голе посилання в Instagram виглядає як спам,
   обрізається в прев'ю і не має підпису дії. `10_VISUAL_MESSAGING.md` §6 вимагає
   кнопку.

**Головне правило: URL ніколи не вигадується.** Платіжне посилання віддається
лише те, що справді існує в `IgDeal` і справді живе (`invoice_link_state`).
Мертве посилання не віддається взагалі — саме через це раніше клієнт упирався в
404 (див. IMP-050 у `bot_payments`). Немає живого посилання — немає URL, є
названа причина.

**Неоднозначність не вгадується.** Коли ціль назвати неможливо, а плаузибільних
цілей більше однієї, модуль повертає ОДНЕ питання з кнопками замість ставки на
одну з цілей. Це дешевше за неправильну відповідь: клієнт відповідає одним
дотиком.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from management.services import ig_message_templates as tpl

# Ціль посилання. `""` — клієнт не назвав, і це нормальний, найчастіший випадок.
TARGET_PAYMENT = "payment"
TARGET_SITE = "site"
TARGET_PRODUCT = "product"

# Рішення про відповідь. Розділені саме так, щоб «немає посилання» і «посилання
# протерміноване» не злились в одне: перше веде до оформлення, друге — до
# перевипуску, і плутати їх означає обіцяти клієнту не те.
KIND_PAYMENT = "payment"
KIND_PRODUCT = "product"
KIND_SITE = "site"
KIND_ASK = "ask"
KIND_REISSUE = "reissue"
KIND_ALREADY_PAID = "already_paid"
KIND_NOT_ISSUED = "not_issued"
KIND_NONE = "none"

_REFERENCE_RE = re.compile(
    r"\b(?:посилання|посилань\w*|лінк\w*|ссылк\w*|link)\b", re.IGNORECASE
)
# Відмова («посилання не потрібне») не є запитом. Без цієї перевірки бот
# відповідав би посиланням саме тому, що клієнт попросив його не надсилати.
_REFUSAL_RE = re.compile(
    r"(?:\b(?:посилання|лінк\w*|ссылк\w*|link)\b.{0,24}"
    r"\bне\s+(?:нужн\w*|потрібн\w*|треба|надо)\b|"
    r"\bне\s+(?:нужн\w*|потрібн\w*|треба|надо|хочу|буду)\b.{0,24}"
    r"\b(?:посилання|лінк\w*|ссылк\w*|link)\b|"
    r"\b(?:do\s+not|don't|dont)\s+(?:need|want|send)\b.{0,24}\blink\b|"
    r"\bno\s+(?:payment\s+)?link\b)",
    re.IGNORECASE,
)
_PAYMENT_CONTEXT_RE = re.compile(
    r"\b(?:оплат\w*|сплат\w*|платіж\w*|платеж\w*|передоплат\w*|предоплат\w*|"
    r"рахунок|рахунк\w*|счёт|счет|інвойс|инвойс|invoice|payment|pay|checkout)\b",
    re.IGNORECASE,
)
_SITE_CONTEXT_RE = re.compile(
    r"\b(?:сайт\w*|магазин\w*|каталог\w*|site|shop|store|catalog\w*)\b",
    re.IGNORECASE,
)
_PRODUCT_CONTEXT_RE = re.compile(
    r"\b(?:товар\w*|модел\w*|цю|цей|це|этот|эту|это|product|item)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LinkRequest:
    """Чи просили посилання і чи назвали ціль."""

    asked: bool
    target: str = ""
    reason_codes: tuple = field(default=())


@dataclass(frozen=True)
class LinkResolution:
    """Рішення разом з готовою карточкою — щоб голий URL було нікуди подіти."""

    kind: str
    url: str = ""
    card: object = None
    reason_codes: tuple = field(default=())
    note: str = ""


def classify_request(text: str) -> LinkRequest:
    """Прочитати запит клієнта: чи просили посилання і чи назвали, яке саме."""
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return LinkRequest(False, "", ("empty_text",))
    if not _REFERENCE_RE.search(normalized):
        return LinkRequest(False, "", ("no_link_reference",))
    if _REFUSAL_RE.search(normalized):
        # Клієнт просив НЕ надсилати. Відповісти посиланням тут — найгірший
        # можливий варіант: бот зробив би рівно те, від чого відмовились.
        return LinkRequest(False, "", ("link_refused",))

    codes = ["link_reference"]
    if _PAYMENT_CONTEXT_RE.search(normalized):
        codes.append("payment_context")
        return LinkRequest(True, TARGET_PAYMENT, tuple(codes))
    if _SITE_CONTEXT_RE.search(normalized):
        codes.append("site_context")
        return LinkRequest(True, TARGET_SITE, tuple(codes))
    if _PRODUCT_CONTEXT_RE.search(normalized):
        codes.append("product_context")
        return LinkRequest(True, TARGET_PRODUCT, tuple(codes))
    # Ціль не названа — це не помилка клієнта і не привід вгадувати.
    codes.append("target_unnamed")
    return LinkRequest(True, "", tuple(codes))


_TEXT = {
    "payment": {
        "uk": "Ось посилання на оплату.",
        "ru": "Вот ссылка на оплату.",
        "en": "Here is your payment link.",
    },
    "site": {
        "uk": "Ось наш магазин.",
        "ru": "Вот наш магазин.",
        "en": "Here is our shop.",
    },
    "product": {
        "uk": "Ось сторінка товару.",
        "ru": "Вот страница товара.",
        "en": "Here is the product page.",
    },
    "reissue": {
        "uk": "Попереднє посилання на оплату вже протерміноване. Сформувати нове?",
        "ru": "Предыдущая ссылка на оплату уже просрочена. Сформировать новую?",
        "en": "Your previous payment link has expired. Shall I issue a new one?",
    },
    "already_paid": {
        "uk": "Оплата вже пройшла — нове посилання не потрібне.",
        "ru": "Оплата уже прошла — новая ссылка не нужна.",
        "en": "The payment already went through, so no new link is needed.",
    },
    "not_issued": {
        "uk": "Посилання на оплату ще не сформоване — оформимо замовлення, і я його надішлю.",
        "ru": "Ссылка на оплату ещё не сформирована — оформим заказ, и я её пришлю.",
        "en": "No payment link exists yet - let us finish the order and I will send it.",
    },
    "ask": {
        "uk": "Уточніть, яке саме посилання потрібне:",
        "ru": "Уточните, какая именно ссылка нужна:",
        "en": "Which link do you need?",
    },
}

_ASK_LABELS = {
    TARGET_PAYMENT: {"uk": "На оплату", "ru": "На оплату", "en": "Payment"},
    TARGET_PRODUCT: {"uk": "На товар", "ru": "На товар", "en": "Product"},
    TARGET_SITE: {"uk": "На сайт", "ru": "На сайт", "en": "Shop"},
}

LINK_ACTION = "link"


def _button_card(text: str, label: str, url: str) -> tpl.ButtonTemplate:
    """Кнопка, а не голий URL. Fallback несе URL текстом — на випадок відмови Meta."""
    return tpl.ButtonTemplate(
        text=text,
        buttons=(tpl.TemplateButton(tpl.BUTTON_WEB_URL, label, url=url),),
        fallback_text=f"{text} {url}".strip(),
    )


def _postback_card(text: str, label: str, payload: str) -> tpl.ButtonTemplate:
    return tpl.ButtonTemplate(
        text=text,
        buttons=(tpl.TemplateButton(tpl.BUTTON_POSTBACK, label, payload=payload),),
        fallback_text=text,
    )


def _site_url() -> str:
    from management.services.ig_catalog_media import _base_url

    return _base_url()


def resolve(
    request: LinkRequest,
    *,
    deal=None,
    product_url: str = "",
    lang: str = "uk",
    now=None,
) -> LinkResolution:
    """Перетворити запит у рішення, спираючись лише на перевірені факти.

    `deal` дає єдине джерело істини про платіжне посилання — сам `IgDeal`, через
    `invoice_link_state`. Ні модель, ні текст ходу не можуть тут нічого додати:
    посилання або є в базі і живе, або його немає.
    """
    if not request.asked:
        return LinkResolution(KIND_NONE, reason_codes=request.reason_codes)

    lang = lang if lang in ("uk", "ru", "en") else "uk"
    from management.services.bot_payments import invoice_link_state

    state = invoice_link_state(deal, now=now) if deal is not None else {"status": "none"}
    status = str(state.get("status") or "none")

    if request.target == TARGET_PAYMENT:
        return _resolve_payment(status, deal, lang, request.reason_codes)
    if request.target == TARGET_SITE:
        return _site_resolution(lang, (*request.reason_codes, "site_named"))
    if request.target == TARGET_PRODUCT and product_url:
        return LinkResolution(
            KIND_PRODUCT,
            url=product_url,
            card=_button_card(
                _TEXT["product"][lang],
                tpl.button_label("product_details", lang),
                product_url,
            ),
            reason_codes=(*request.reason_codes, "product_named"),
        )

    # Ціль не названа. Плаузібільні цілі виводяться зі СТАНУ, а не з припущення.
    targets = []
    if status in {"live", "expired"}:
        # Про оплату мова взагалі йде лише тоді, коли посилання колись існувало.
        targets.append(TARGET_PAYMENT)
    if product_url:
        targets.append(TARGET_PRODUCT)
    targets.append(TARGET_SITE)

    if len(targets) == 1:
        # Єдина плаузібільна ціль — перепитувати нема про що.
        return _site_resolution(lang, (*request.reason_codes, "single_plausible_target"))

    quick = tuple(
        tpl.QuickReply(
            _ASK_LABELS[target][lang], tpl.build_payload(LINK_ACTION, target)
        )
        for target in targets
    )
    return LinkResolution(
        KIND_ASK,
        card=tpl.QuickReplyMessage(
            text=_TEXT["ask"][lang],
            quick_replies=quick,
            fallback_text=_TEXT["ask"][lang],
        ),
        reason_codes=(*request.reason_codes, "ambiguous_target"),
        note="цілей більше однієї — одне питання дешевше за неправильну відповідь",
    )


def _site_resolution(lang: str, codes: tuple) -> LinkResolution:
    url = _site_url()
    return LinkResolution(
        KIND_SITE,
        url=url,
        card=_button_card(_TEXT["site"][lang], tpl.button_label("open_site", lang), url),
        reason_codes=codes,
    )


def _resolve_payment(status, deal, lang, codes) -> LinkResolution:
    """Платіжне посилання віддається лише живе. Мертве — не віддається взагалі."""
    if status == "live":
        url = str(getattr(deal, "invoice_url", "") or "")
        return LinkResolution(
            KIND_PAYMENT,
            url=url,
            card=_button_card(
                _TEXT["payment"][lang], tpl.button_label("pay_online", lang), url
            ),
            reason_codes=(*codes, "invoice_live"),
        )
    if status == "expired":
        # Саме тут раніше клієнт отримував 404: посилання віддавали, не перевіривши.
        return LinkResolution(
            KIND_REISSUE,
            card=_postback_card(
                _TEXT["reissue"][lang],
                tpl.button_label("pay_online", lang),
                tpl.build_payload(LINK_ACTION, "reissue"),
            ),
            reason_codes=(*codes, "invoice_expired"),
            note="мертвий URL не віддається — лише перевипуск",
        )
    if status == "paid":
        return LinkResolution(
            KIND_ALREADY_PAID,
            reason_codes=(*codes, "already_paid"),
            note=_TEXT["already_paid"][lang],
        )
    # none | unknown. `unknown` теж не віддається: TTL невідомий, і «живе воно чи
    # ні» — здогадка, а здогадка тут коштує клієнту 404.
    return LinkResolution(
        KIND_NOT_ISSUED,
        reason_codes=(*codes, f"invoice_{status}"),
        note=_TEXT["not_issued"][lang],
    )
