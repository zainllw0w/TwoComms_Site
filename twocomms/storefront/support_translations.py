"""Phase 17d.7 — per-language overrides for support page meta + hero.

Long-form body paragraphs / cards stay in Ukrainian for now; this
module covers only the high-visibility surface that search engines
and visitors see immediately:

    * page_title  (browser tab + breadcrumb)
    * meta_title  (<title>)
    * meta_description / meta_keywords
    * hero_kicker / hero_title / hero_intro

Six top-priority pages: about, delivery, faq, returns, privacy_policy,
terms_of_service. Other support pages (help_center, size_guide,
care_guide, order_tracking, site_map_page, news) can be added later
as translations are produced.

Usage in views/static_pages.py — after deepcopy of the page dict:

    from .support_translations import apply_language_overrides
    page = apply_language_overrides(page, page_key, request.LANGUAGE_CODE)
"""

from __future__ import annotations

from typing import Any, Dict


_RU_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "about": {
        "page_title": "О бренде — TwoComms",
        "meta_title": "TwoComms — харьковский бренд одежды о характере, стойкости и продолжении",
        "meta_description": "TwoComms — украинский streetwear / military-adjacent бренд из Харькова. Одежда с кодом, смысловыми принтами, реальным происхождением и философией: не точка, а продолжение.",
        "meta_keywords": "TwoComms, харьковский бренд одежды, украинский streetwear бренд, military-adjacent одежда, одежда со смыслом, смысловые принты, две запятые, Харьков",
        "hero_kicker": "Brand",
        "hero_title": "TwoComms — не точка. Продолжение.",
        "hero_intro": "TwoComms — харьковский streetwear / military-adjacent бренд о характере, смысловых принтах, внутренней дисциплине и движении дальше после критической точки.",
    },
    "delivery": {
        "page_title": "Доставка и оплата — TwoComms",
        "meta_title": "Доставка и оплата — TwoComms",
        "meta_description": "Условия доставки и оплаты TwoComms: сроки по Украине, международные отправления, оплата, наложенный платёж и отслеживание заказа.",
        "meta_keywords": "TwoComms доставка, оплата, наложенный платёж, mono checkout, международная доставка",
        "hero_kicker": "Delivery & Payment",
        "hero_title": "Доставка и оплата",
        "hero_intro": "Здесь только то, что нужно для логистики и оплаты: сроки, сценарии по Украине, международные отправления и дальнейший маршрут после checkout.",
    },
    "faq": {
        "page_title": "FAQ — TwoComms",
        "meta_title": "FAQ — оплата, доставка, размеры и сервис | TwoComms",
        "meta_description": "FAQ TwoComms: ответы об оформлении заказа, оплате, доставке, размерах, возврате, баллах, кастомной печати и уходе за одеждой.",
        "meta_keywords": "TwoComms FAQ, вопросы и ответы, оплата, доставка, размеры, возврат",
        "hero_kicker": "FAQ",
        "hero_title": "Частые вопросы о покупке и сервисе",
        "hero_intro": "Это единый полный FAQ-хаб. Если нужны короткие ответы без длинных инструкций — начните отсюда.",
    },
    "returns": {
        "page_title": "Возврат и обмен — TwoComms",
        "meta_title": "Возврат и обмен товаров | TwoComms",
        "meta_description": "Возврат и обмен TwoComms: готовые товары надлежащего качества можно вернуть или обменять в течение 14 дней, кастомная одежда имеет отдельные условия.",
        "meta_keywords": "TwoComms возврат, обмен товара, сервис после покупки",
        "hero_kicker": "After Purchase",
        "hero_title": "Возврат и обмен",
        "hero_intro": "Готовые товары надлежащего качества можно вернуть или обменять в течение 14 дней с момента получения согласно законодательству Украины. Кастомная одежда, изготовленная по индивидуальному заказу, не подлежит возврату или обмену, если выполнена надлежащим образом и соответствует согласованным параметрам.",
    },
    "privacy_policy": {
        "page_title": "Политика конфиденциальности — TwoComms",
        "meta_title": "Политика конфиденциальности | TwoComms",
        "meta_description": "Политика конфиденциальности TwoComms: какие данные используются для заказов, аккаунта, поддержки и технической работы сайта.",
        "meta_keywords": "TwoComms политика конфиденциальности, персональные данные, cookies",
        "hero_kicker": "Privacy",
        "hero_title": "Политика конфиденциальности",
        "hero_intro": "Кратко о том, какие данные нужны для работы заказов, аккаунта, сервисной коммуникации и базовой технической аналитики сайта.",
    },
    "terms_of_service": {
        "page_title": "Условия использования — TwoComms",
        "meta_title": "Условия использования сайта | TwoComms",
        "meta_description": "Условия использования сайта TwoComms: базовые правила оформления заказов, работы аккаунта и сервисного взаимодействия.",
        "meta_keywords": "TwoComms условия использования, правила сайта, оформление заказа",
        "hero_kicker": "Terms",
        "hero_title": "Условия использования сайта",
        "hero_intro": "Краткий набор базовых правил: как работает сайт, аккаунт, оформление заказов и сервисные страницы.",
    },
}


_EN_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "about": {
        "page_title": "About the brand — TwoComms",
        "meta_title": "TwoComms — Kharkiv-based clothing brand about character, resilience and continuation",
        "meta_description": "TwoComms — a Ukrainian streetwear / military-adjacent brand from Kharkiv. Clothing with code, meaningful prints, real origin and a philosophy: not a full stop, a continuation.",
        "meta_keywords": "TwoComms, Kharkiv clothing brand, Ukrainian streetwear brand, military-adjacent clothing, clothing with meaning, meaningful prints, two commas, Kharkiv",
        "hero_kicker": "Brand",
        "hero_title": "TwoComms — not a full stop. A continuation.",
        "hero_intro": "TwoComms is a Kharkiv-based streetwear / military-adjacent brand about character, meaningful prints, inner discipline, and moving forward after the critical point.",
    },
    "delivery": {
        "page_title": "Delivery & payment — TwoComms",
        "meta_title": "Delivery & payment — TwoComms",
        "meta_description": "TwoComms delivery and payment terms: shipping times in Ukraine, international orders, payment options, cash on delivery, and order tracking.",
        "meta_keywords": "TwoComms delivery, payment, cash on delivery, mono checkout, international shipping",
        "hero_kicker": "Delivery & Payment",
        "hero_title": "Delivery & payment",
        "hero_intro": "Only what you need for logistics and payment: timelines, Ukraine scenarios, international shipping, and the route after checkout.",
    },
    "faq": {
        "page_title": "FAQ — TwoComms",
        "meta_title": "FAQ — payment, delivery, sizes and service | TwoComms",
        "meta_description": "TwoComms FAQ: answers about checkout, payment, delivery, sizes, returns, points, custom print, and garment care.",
        "meta_keywords": "TwoComms FAQ, questions and answers, payment, delivery, sizes, returns",
        "hero_kicker": "FAQ",
        "hero_title": "Frequently asked questions about purchase and service",
        "hero_intro": "This is the single comprehensive FAQ hub. If you want short answers without long manuals, start here.",
    },
    "returns": {
        "page_title": "Returns & exchanges — TwoComms",
        "meta_title": "Returns and exchanges | TwoComms",
        "meta_description": "TwoComms returns and exchanges: ready-made items of proper quality can be returned or exchanged within 14 days; custom-made apparel has separate terms.",
        "meta_keywords": "TwoComms returns, exchange, after-sale service",
        "hero_kicker": "After Purchase",
        "hero_title": "Returns & exchanges",
        "hero_intro": "Ready-made items of proper quality can be returned or exchanged within 14 days of receipt under Ukrainian law. Custom apparel made to individual order is not subject to return or exchange when properly executed and matching agreed parameters.",
    },
    "privacy_policy": {
        "page_title": "Privacy policy — TwoComms",
        "meta_title": "Privacy policy | TwoComms",
        "meta_description": "TwoComms privacy policy: what data we use for orders, account, support, and the technical operation of the site.",
        "meta_keywords": "TwoComms privacy policy, personal data, cookies",
        "hero_kicker": "Privacy",
        "hero_title": "Privacy policy",
        "hero_intro": "A brief overview of the data needed for orders, the account, service communication, and basic technical site analytics.",
    },
    "terms_of_service": {
        "page_title": "Terms of service — TwoComms",
        "meta_title": "Site terms of service | TwoComms",
        "meta_description": "TwoComms site terms of service: basic rules for placing orders, the account, and service interactions.",
        "meta_keywords": "TwoComms terms of service, site rules, ordering",
        "hero_kicker": "Terms",
        "hero_title": "Terms of service",
        "hero_intro": "A short set of basic rules: how the site, account, ordering, and service pages work.",
    },
}


_LANG_OVERRIDES = {"ru": _RU_OVERRIDES, "en": _EN_OVERRIDES}


def apply_language_overrides(page: dict, page_key: str, lang_code: str) -> dict:
    """Mutate ``page`` dict with per-language overrides, return it.

    No-op for Ukrainian (default) or unknown languages / pages. Only
    fields explicitly present in the override dict are replaced; the
    long-form ``sections``/``cards``/``faq_items`` payload stays as
    written in the canonical SUPPORT_PAGE_DEFINITIONS.
    """
    overrides = _LANG_OVERRIDES.get(lang_code or "")
    if not overrides:
        return page
    page_overrides = overrides.get(page_key)
    if not page_overrides:
        return page
    for field, value in page_overrides.items():
        page[field] = value
    return page
