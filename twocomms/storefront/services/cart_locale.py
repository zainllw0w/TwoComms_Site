"""Locale-owned configuration for the public cart and checkout surfaces."""

from __future__ import annotations

from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext as _
from django.utils.translation import override

from .locale_contract import build_storefront_locale_contract


_URL_NAMES = {
    "home": "home",
    "cart": "cart",
    "items": "cart_items_api",
    "summary": "cart_summary",
    "update": "update_cart",
    "remove": "cart_remove",
    "mini": "cart_mini",
    "clear": "clean_cart",
    "add": "cart_add",
    "promoApply": "apply_promo_code",
    "promoRemove": "remove_promo_code",
    "contact": "contact_manager",
    "citySearch": "cart_np_city_search",
    "warehouseSearch": "cart_np_warehouse_search",
    "invoice": "monobank_create_invoice",
    "quickInvoice": "monobank_quick_invoice",
    "customRemove": "custom_print_remove",
}


_FALLBACK_PATHS = {
    "home": "/",
    "cart": "/cart/",
    "items": "/cart/items/",
    "summary": "/cart/summary/",
    "update": "/cart/update/",
    "remove": "/cart/remove/",
    "mini": "/cart/mini/",
    "clear": "/cart/clean/",
    "add": "/cart/add/",
    "promoApply": "/cart/apply-promo/",
    "promoRemove": "/cart/remove-promo/",
    "contact": "/cart/contact-manager/",
    "citySearch": "/cart/delivery/cities/",
    "warehouseSearch": "/cart/delivery/warehouses/",
    "invoice": "/cart/monobank/create-invoice/",
    "quickInvoice": "/cart/monobank/quick/",
    "customRemove": "/custom-print/remove/",
}


def _reverse_urls(language: str) -> dict[str, str]:
    urls: dict[str, str] = {}
    for key, name in _URL_NAMES.items():
        try:
            urls[key] = reverse(name)
        except NoReverseMatch:
            # Isolated template contexts may not install the full URLConf.
            # Keep every endpoint usable and locale-prefixed rather than
            # allowing fetch(undefined) or a current-document POST.
            path = _FALLBACK_PATHS[key]
            # Default Ukrainian routes are intentionally unprefixed by
            # i18n_patterns(prefix_default_language=False).
            urls[key] = path if language == "uk" else f"/{language}{path}"
    return urls


def build_cart_locale_config(language: str | None) -> dict[str, object]:
    """Return dynamic cart copy and locale-aware endpoints.

    This payload is deliberately separate from ``storefront-locale-contract``:
    the latter is a stable metadata API consumed by analytics and SEO code.
    """
    contract = build_storefront_locale_contract(language)
    normalized = str(contract["language"])

    with override(normalized):
        strings = {
            "emptyCart": _("Кошик порожній"),
            "emptyCartText": _("Додайте товари до кошика, щоб зробити замовлення"),
            "continueShopping": _("Перейти до покупок"),
            "loading": _("Завантаження…"),
            "loadError": _("Не вдалося завантажити кошик"),
            "itemProductAlt": _("Товар TwoComms"),
            "color": _("Колір"),
            "size": _("Розмір"),
            "quantity": _("Кількість"),
            "fit": _("Посадка"),
            "cut": _("Крій"),
            "price": _("Ціна"),
            "total": _("Разом"),
            "remove": _("Видалити"),
            "decrease": _("Зменшити кількість"),
            "increase": _("Збільшити кількість"),
            "perItem": _("шт"),
            "leadNumber": _("№{number}"),
            "customPrint": _("Кастомний друк"),
            "customProduct": _("Кастомний виріб"),
            "product": _("Виріб"),
            "placement": _("Розміщення"),
            "sizeMode": _("Режим розмірів"),
            "sizes": _("Розміри"),
            "fabric": _("Тканина"),
            "service": _("Послуга"),
            "filePreparation": _("Підготовка файлу"),
            "additional": _("Додатково"),
            "placementComment": _("Коментар до розміщення"),
            "gift": _("Подарунок"),
            "giftText": _("Упаковка + промокод 10%"),
            "b2bDiscount": _("B2B знижка"),
            "managerContact": _("Написати менеджеру"),
            "pendingToManager": _("Передаємо менеджеру на перевірку"),
            "pendingManager": _("На перевірці менеджера"),
            "approved": _("Погоджено — можна оплачувати"),
            "rejected": _("Відхилено менеджером"),
            "managerComment": _("Коментар менеджера"),
            "afterApproval": _("Після погодження"),
            "approximately": _("Орієнтовно"),
            "pointsEarned": _("Заробите {points} балів"),
            "itemsCount": _("Товари ({count}):"),
            "productsCount": _("Товари ({count}):"),
            "discount": _("Знижка"),
            "promoDiscount": _("Знижка промокоду"),
            "payNow": _("До сплати:"),
            "payNowPrepay": _("До сплати зараз:"),
            "paymentCta": _("Перейти до оплати"),
            "prepayCta": _("Внести передплату 200 грн"),
            "orderCta": _("Оформити замовлення"),
            "guestCta": _("Замовити як гість"),
            "consultationSending": _("Відправляємо…"),
            "consultationSuccess": _("Дякуємо! Менеджер зв'яжеться з вами найближчим часом."),
            "genericError": _("Спробуйте ще раз"),
            "connectionError": _("Помилка з'єднання. Спробуйте ще раз."),
            "promoInvalid": _("Невірний промокод. Перевірте код і спробуйте ще раз."),
            "invalidPromo": _("Невірний промокод. Перевірте код і спробуйте ще раз."),
            "promoApplied": _("Промокод застосовано."),
            "promoRemoving": _("Видаляємо промокод…"),
            "promoRemoved": _("Промокод видалено."),
            "promoRequired": _("Введіть промокод, щоб відкрити сейф."),
            "promoChecking": _("Перевіряємо код на сервері…"),
            "promoAccepted": _("Код прийнято. Відкриваємо сейф…"),
            "promoRetryLimit": _("Забагато спроб. Спробуйте через хвилину."),
            "promoNetworkError": _("Не вдалося перевірити промокод. Перевірте з'єднання та спробуйте ще раз."),
            "requiredField": _("Це поле обов'язкове"),
            "invalidPhone": _("Вкажіть коректний український номер. Можна без +380."),
            "invalidDelivery": _("Оберіть місто та пункт доставки зі списку Нової пошти."),
            "paymentError": _("Не вдалося створити платіж. Спробуйте ще раз."),
            "loginForPayment": _("Увійдіть, щоб скористатися онлайн оплатою."),
            "openingPayment": _("Відкриваємо платіжну сторінку…"),
            "openingMonoCheckout": _("Відкриваємо mono checkout…"),
            "productUnavailable": _("Товар недоступний."),
            "addToCartError": _("Не вдалося додати товар до кошика. Спробуйте ще раз."),
            "promoFirstLock": _("Перший замок відкрито…"),
            "promoSecondLock": _("Другий замок відкрито…"),
            "promoAllLocks": _("Усі замки відкрито."),
            "promoOpeningDoor": _("Відкриваємо двері сейфа…"),
            "promoFound": _("Знижку знайдено."),
            "promoClosingDoor": _("Знижку знайдено. Закриваємо сейф…"),
            "promoRemoveError": _("Не вдалося видалити промокод."),
            "promoRemoveNetworkError": _("Не вдалося видалити промокод. Перевірте з'єднання та спробуйте ще раз."),
            "contactSending": _("Відправляємо…"),
            "contactSuccess": _("Дякуємо! Менеджер зв'яжеться з вами найближчим часом."),
            "contactError": _("Помилка: {message}"),
            "contactConnectionError": _("Помилка з'єднання. Спробуйте ще раз."),
            "required": _("Це поле обов'язкове"),
            "confirmClear": _("Ви впевнені, що хочете очистити кошик?"),
            "discountPromo": _("Знижка промокоду"),
        }

        return {
            "language": normalized,
            "intlLocale": contract["intlLocale"],
            "currency": contract["currency"],
            "urls": _reverse_urls(normalized),
            "strings": strings,
        }
