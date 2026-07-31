from __future__ import annotations

import secrets

from django.core import signing
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from management.models import IgCheckoutAccessToken, IgCheckoutProposal


GRANT_SALT = "twocomms.instagram-checkout.grant.v1"
GRANT_SESSION_PREFIX = "ig_checkout_grant:"
GRANT_MAX_AGE = 60 * 60 * 12
INSTAGRAM_DIRECT_URL = "https://www.instagram.com/twocomms/"


CHECKOUT_COPY = {
    "uk": {
        "page_title": "Перевірте замовлення",
        "eyebrow": "Персональна пропозиція",
        "lead": "Ми вже зафіксували товари та ціну. Перевірте деталі й додайте дані доставки.",
        "greeting": "Вітаємо",
        "order_for": "Це замовлення сформовано для вас на суму",
        "order_label": "Ваше замовлення",
        "proposal_label": "Пропозиція",
        "expires_label": "Посилання активне ще",
        "expired_short": "Час завершився",
        "color_label": "Колір",
        "fit_label": "Фасон",
        "size_label": "Розмір",
        "quantity_label": "Кількість",
        "catalog_total": "Вартість товарів",
        "discount": "Узгоджена знижка",
        "total": "До сплати",
        "delivery_title": "Дані для доставки",
        "delivery_lead": "Заповнення займає близько двох хвилин.",
        "full_name": "Ім'я та прізвище",
        "full_name_placeholder": "Іван Петренко",
        "phone": "Номер телефону",
        "phone_placeholder": "+380 00 000 00 00",
        "email": "Email для чека",
        "recommended": "Рекомендовано",
        "email_placeholder": "name@example.com",
        "email_hint": "Не обов'язково, але на цю адресу ми надішлемо чек і підтвердження.",
        "city": "Місто Нової пошти",
        "city_placeholder": "Почніть вводити місто",
        "city_hint": "Виберіть підтверджений варіант зі списку Нової пошти.",
        "warehouse": "Відділення або поштомат",
        "warehouse_placeholder": "Номер або адреса пункту",
        "warehouse_hint": "Спочатку виберіть місто, потім пункт отримання.",
        "all_points": "Усі",
        "branches": "Відділення",
        "postomats": "Поштомати",
        "promo": "Промокод",
        "have_promo": "Маєте промокод?",
        "promo_placeholder": "Якщо маєте промокод",
        "promo_hint": "Промокод буде перевірено до створення рахунку.",
        "pay": "Перейти до оплати",
        "pay_loading": "Перевіряємо дані...",
        "secure_payment": "Захищена оплата на сайті TwoComms",
        "share": "Скопіювати посилання",
        "share_done": "Посилання скопійовано",
        "share_error": "Не вдалося скопіювати",
        "share_hint": "Посилання можна передати іншій людині для оплати.",
        "change_order": "Змінити замовлення в Direct",
        "privacy": "Політика приватності",
        "support": "Підтримка в Direct",
        "delivery_locked": "Дані доставки зафіксовані",
        "recipient": "Отримувач",
        "contact": "Контакт",
        "receipt": "Чек",
        "state_ready_title": "Все готово до оформлення",
        "state_ready_body": "Перевірте товари та заповніть дані для доставки.",
        "state_locked_title": "Дані прийнято",
        "state_locked_body": "Ми зафіксували отримувача. Зміни можна узгодити в Instagram Direct.",
        "state_pending_title": "Очікуємо оплату",
        "state_pending_body": "Рахунок уже створено. Не створюйте новий платіж, доки ми перевіряємо поточний.",
        "state_paid_title": "Замовлення оплачено",
        "state_paid_body": "Дякуємо. Після формування ТТН ми продублюємо її в Instagram Direct.",
        "state_failed_title": "Оплата не завершилась",
        "state_failed_body": "Платіж не підтверджено. Напишіть нам у Direct, щоб безпечно повторити оплату.",
        "state_expired_title": "Пропозиція завершилась",
        "state_expired_body": "Напишіть нам у Direct, і бот сформує актуальну пропозицію.",
        "state_unavailable_title": "Пропозиція недоступна",
        "state_unavailable_body": "Це посилання відкликано. Актуальну версію можна отримати в Direct.",
        "state_superseded_title": "Є нова версія замовлення",
        "state_superseded_body": "Цю пропозицію замінено. Відкрийте останнє посилання з Instagram Direct.",
        "state_cancelled_title": "Рахунок скасовано",
        "state_cancelled_body": "Оплата за цим рахунком більше не приймається. Запросіть нову пропозицію в Direct.",
        "state_cancellation_ambiguous_title": "Перевіряємо стан рахунку",
        "state_cancellation_ambiguous_body": "Не повторюйте оплату. Ми спочатку звіримо статус із банком.",
    },
    "ru": {
        "page_title": "Проверьте заказ",
        "eyebrow": "Персональное предложение",
        "lead": "Мы уже зафиксировали товары и цену. Проверьте детали и добавьте данные доставки.",
        "greeting": "Здравствуйте",
        "order_for": "Этот заказ сформирован для вас на сумму",
        "order_label": "Ваш заказ",
        "proposal_label": "Предложение",
        "expires_label": "Ссылка активна еще",
        "expired_short": "Время истекло",
        "color_label": "Цвет",
        "fit_label": "Фасон",
        "size_label": "Размер",
        "quantity_label": "Количество",
        "catalog_total": "Стоимость товаров",
        "discount": "Согласованная скидка",
        "total": "К оплате",
        "delivery_title": "Данные для доставки",
        "delivery_lead": "Заполнение занимает около двух минут.",
        "full_name": "Имя и фамилия",
        "full_name_placeholder": "Иван Петренко",
        "phone": "Номер телефона",
        "phone_placeholder": "+380 00 000 00 00",
        "email": "Email для чека",
        "recommended": "Рекомендуем",
        "email_placeholder": "name@example.com",
        "email_hint": "Не обязательно, но на этот адрес мы отправим чек и подтверждение.",
        "city": "Город Новой почты",
        "city_placeholder": "Начните вводить город",
        "city_hint": "Выберите подтвержденный вариант из списка Новой почты.",
        "warehouse": "Отделение или почтомат",
        "warehouse_placeholder": "Номер или адрес пункта",
        "warehouse_hint": "Сначала выберите город, затем пункт получения.",
        "all_points": "Все",
        "branches": "Отделения",
        "postomats": "Почтоматы",
        "promo": "Промокод",
        "have_promo": "Есть промокод?",
        "promo_placeholder": "Если у вас есть промокод",
        "promo_hint": "Промокод будет проверен до создания счета.",
        "pay": "Перейти к оплате",
        "pay_loading": "Проверяем данные...",
        "secure_payment": "Защищенная оплата на сайте TwoComms",
        "share": "Скопировать ссылку",
        "share_done": "Ссылка скопирована",
        "share_error": "Не удалось скопировать",
        "share_hint": "Ссылку можно передать другому человеку для оплаты.",
        "change_order": "Изменить заказ в Direct",
        "privacy": "Политика конфиденциальности",
        "support": "Поддержка в Direct",
        "delivery_locked": "Данные доставки зафиксированы",
        "recipient": "Получатель",
        "contact": "Контакт",
        "receipt": "Чек",
        "state_ready_title": "Все готово к оформлению",
        "state_ready_body": "Проверьте товары и заполните данные для доставки.",
        "state_locked_title": "Данные приняты",
        "state_locked_body": "Мы зафиксировали получателя. Изменения можно согласовать в Instagram Direct.",
        "state_pending_title": "Ожидаем оплату",
        "state_pending_body": "Счет уже создан. Не создавайте новый платеж, пока мы проверяем текущий.",
        "state_paid_title": "Заказ оплачен",
        "state_paid_body": "Спасибо. После формирования ТТН мы продублируем ее в Instagram Direct.",
        "state_failed_title": "Оплата не завершилась",
        "state_failed_body": "Платеж не подтвержден. Напишите нам в Direct, чтобы безопасно повторить оплату.",
        "state_expired_title": "Предложение завершилось",
        "state_expired_body": "Напишите нам в Direct, и бот сформирует актуальное предложение.",
        "state_unavailable_title": "Предложение недоступно",
        "state_unavailable_body": "Эта ссылка отозвана. Актуальную версию можно получить в Direct.",
        "state_superseded_title": "Есть новая версия заказа",
        "state_superseded_body": "Это предложение заменено. Откройте последнюю ссылку из Instagram Direct.",
        "state_cancelled_title": "Счет отменен",
        "state_cancelled_body": "Оплата по этому счету больше не принимается. Запросите новое предложение в Direct.",
        "state_cancellation_ambiguous_title": "Проверяем состояние счета",
        "state_cancellation_ambiguous_body": "Не повторяйте оплату. Сначала мы сверим статус с банком.",
    },
    "en": {
        "page_title": "Review your order",
        "eyebrow": "Personal offer",
        "lead": "Your items and price are locked in. Review the details and add delivery information.",
        "greeting": "Hello",
        "order_for": "This order was prepared for you with a total of",
        "order_label": "Your order",
        "proposal_label": "Offer",
        "expires_label": "Link available for",
        "expired_short": "Time expired",
        "color_label": "Color",
        "fit_label": "Fit",
        "size_label": "Size",
        "quantity_label": "Quantity",
        "catalog_total": "Items total",
        "discount": "Agreed discount",
        "total": "Total to pay",
        "delivery_title": "Delivery details",
        "delivery_lead": "This usually takes less than two minutes.",
        "full_name": "Full name",
        "full_name_placeholder": "Ivan Petrenko",
        "phone": "Phone number",
        "phone_placeholder": "+380 00 000 00 00",
        "email": "Email for receipt",
        "recommended": "Recommended",
        "email_placeholder": "name@example.com",
        "email_hint": "Optional, but we can send the receipt and order confirmation here.",
        "city": "Nova Poshta city",
        "city_placeholder": "Start typing a city",
        "city_hint": "Choose a verified option from the Nova Poshta list.",
        "warehouse": "Branch or parcel locker",
        "warehouse_placeholder": "Branch number or address",
        "warehouse_hint": "Choose the city first, then your pickup point.",
        "all_points": "All",
        "branches": "Branches",
        "postomats": "Lockers",
        "promo": "Promo code",
        "have_promo": "Have a promo code?",
        "promo_placeholder": "If you have a promo code",
        "promo_hint": "The promo code will be verified before an invoice is created.",
        "pay": "Continue to payment",
        "pay_loading": "Checking details...",
        "secure_payment": "Secure payment on the TwoComms website",
        "share": "Copy link",
        "share_done": "Link copied",
        "share_error": "Could not copy link",
        "share_hint": "You can forward this link to someone else who will pay.",
        "change_order": "Change order in Direct",
        "privacy": "Privacy policy",
        "support": "Support in Direct",
        "delivery_locked": "Delivery details are locked",
        "recipient": "Recipient",
        "contact": "Contact",
        "receipt": "Receipt",
        "state_ready_title": "Ready to check out",
        "state_ready_body": "Review the items and add your delivery details.",
        "state_locked_title": "Details received",
        "state_locked_body": "The recipient is locked. Ask for changes in Instagram Direct.",
        "state_pending_title": "Waiting for payment",
        "state_pending_body": "An invoice already exists. Do not start another payment while we verify it.",
        "state_paid_title": "Order paid",
        "state_paid_body": "Thank you. We will send the tracking number in Instagram Direct.",
        "state_failed_title": "Payment was not completed",
        "state_failed_body": "The payment is not confirmed. Contact us in Direct before trying again.",
        "state_expired_title": "This offer has expired",
        "state_expired_body": "Message us in Direct and the bot will create an up-to-date offer.",
        "state_unavailable_title": "Offer unavailable",
        "state_unavailable_body": "This link was revoked. Request the current version in Direct.",
        "state_superseded_title": "A newer order version exists",
        "state_superseded_body": "This offer was replaced. Open the latest link from Instagram Direct.",
        "state_cancelled_title": "Invoice cancelled",
        "state_cancelled_body": "This invoice can no longer be paid. Request a new offer in Direct.",
        "state_cancellation_ambiguous_title": "Checking invoice status",
        "state_cancellation_ambiguous_body": "Do not pay again. We will first verify the status with the bank.",
    },
}

CHECKOUT_ERROR_COPY = {
    "uk": {
        "expired": "Термін дії пропозиції завершився.",
        "unavailable": "Цю пропозицію більше не можна оплатити.",
        "in_progress": "Платіж уже створюється. Зачекайте кілька секунд.",
        "full_name": "Вкажіть ім'я та прізвище.",
        "phone": "Вкажіть коректний український номер телефону.",
        "email": "Перевірте email для чека.",
        "city": "Оберіть місто зі списку Нової пошти.",
        "np_office": "Оберіть відділення або поштомат зі списку Нової пошти.",
        "promo_unavailable": "Промокод для цієї пропозиції недоступний.",
        "promo_invalid": "Промокод недійсний або вже використаний.",
        "promo_requires_account": "Цей промокод доступний лише в особистому кабінеті.",
        "provider_error": "Не вдалося створити платіж. Спробуйте ще раз.",
        "invalid_amount": "Сума замовлення має бути більшою за нуль.",
        "item_unavailable": "Один із товарів більше недоступний.",
        "empty_items": "У пропозиції немає товарів.",
    },
    "ru": {
        "expired": "Срок действия предложения истек.",
        "unavailable": "Это предложение больше нельзя оплатить.",
        "in_progress": "Платеж уже создается. Подождите несколько секунд.",
        "full_name": "Укажите имя и фамилию.",
        "phone": "Укажите корректный украинский номер телефона.",
        "email": "Проверьте email для чека.",
        "city": "Выберите город из списка Новой почты.",
        "np_office": "Выберите отделение или почтомат из списка Новой почты.",
        "promo_unavailable": "Промокод для этого предложения недоступен.",
        "promo_invalid": "Промокод недействителен или уже использован.",
        "promo_requires_account": "Этот промокод доступен только в личном кабинете.",
        "provider_error": "Не удалось создать платеж. Попробуйте еще раз.",
        "invalid_amount": "Сумма заказа должна быть больше нуля.",
        "item_unavailable": "Один из товаров больше недоступен.",
        "empty_items": "В предложении нет товаров.",
    },
    "en": {
        "expired": "This offer has expired.",
        "unavailable": "This offer can no longer be paid.",
        "in_progress": "A payment is already being created. Please wait a few seconds.",
        "full_name": "Enter your first and last name.",
        "phone": "Enter a valid Ukrainian phone number.",
        "email": "Check the receipt email.",
        "city": "Choose a city from the Nova Poshta list.",
        "np_office": "Choose a branch or locker from the Nova Poshta list.",
        "promo_unavailable": "A promo code is not available for this offer.",
        "promo_invalid": "The promo code is invalid or already used.",
        "promo_requires_account": "This promo code is available only in an account.",
        "provider_error": "We could not create the payment. Please try again.",
        "invalid_amount": "The order total must be greater than zero.",
        "item_unavailable": "One of the items is no longer available.",
        "empty_items": "This offer has no items.",
    },
}


def _private_headers(response):
    if response.get("Content-Type", "").startswith("text/html"):
        response["Content-Type"] = "text/html; charset=utf-8"
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Referrer-Policy"] = "no-referrer"
    return response


def _grant_session_key(proposal):
    return f"{GRANT_SESSION_PREFIX}{proposal.public_id}"


def _save_grant(request, proposal, token):
    expires_at = min(proposal.expires_at, token.expires_at)
    payload = {
        "proposal_id": str(proposal.public_id),
        "token_id": token.pk,
        "revision": proposal.revision,
        "grant_id": secrets.token_urlsafe(18),
        "expires_at": int(expires_at.timestamp()),
    }
    request.session[_grant_session_key(proposal)] = signing.dumps(
        payload,
        salt=GRANT_SALT,
        compress=True,
    )
    request.session.modified = True
    return payload


def _load_grant(request, proposal):
    value = request.session.get(_grant_session_key(proposal))
    if not value:
        raise Http404("proposal grant not found")
    try:
        payload = signing.loads(value, salt=GRANT_SALT, max_age=GRANT_MAX_AGE)
    except signing.BadSignature:
        raise Http404("proposal grant invalid")
    if payload.get("proposal_id") != str(proposal.public_id):
        raise Http404("proposal grant invalid")
    if int(payload.get("revision") or 0) != proposal.revision:
        raise Http404("proposal revision changed")
    if int(payload.get("expires_at") or 0) <= int(timezone.now().timestamp()):
        raise Http404("proposal grant expired")
    token = IgCheckoutAccessToken.objects.filter(
        pk=payload.get("token_id"),
        proposal=proposal,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if token is None:
        raise Http404("proposal token unavailable")
    return payload, token


def _locale(value):
    code = str(value or "uk").lower().split("-", 1)[0].split("_", 1)[0]
    return code if code in CHECKOUT_COPY else "uk"


def _localized_error(language, code, fallback):
    return CHECKOUT_ERROR_COPY.get(language, CHECKOUT_ERROR_COPY["uk"]).get(code, fallback)


def _money(value):
    return f"{value:.2f}"


def _mask_phone(value):
    digits = "".join(character for character in str(value or "") if character.isdigit())
    return f"+380 •• ••• •• {digits[-4:]}" if digits else "—"


def _mask_email(value):
    local, separator, domain = str(value or "").partition("@")
    if not separator or not domain:
        return "—"
    visible = local[:1] if local else ""
    return f"{visible}•••@{domain}"


def _mask_name(value):
    parts = [part for part in str(value or "").split() if part]
    return " ".join(f"{part[0]}." for part in parts[:3]) or "—"


def _customer_name(value):
    parts = str(value or "").strip().split(maxsplit=1)
    return parts[0][:50] if parts else ""


def _checkout_state(proposal):
    if proposal.status == proposal.Status.PAID:
        return "paid"
    if proposal.status == proposal.Status.REVOKED:
        return "unavailable"
    if proposal.status == proposal.Status.SUPERSEDED:
        return "superseded"
    if proposal.status == proposal.Status.EXPIRED or proposal.is_expired:
        return "expired"
    attempt = proposal.payment_attempt
    if proposal.status == proposal.Status.CANCELLED:
        return (
            "cancelled"
            if proposal.has_provider_confirmed_cancellation()
            else "cancellation_ambiguous"
        )
    if attempt is not None and attempt.status == attempt.Status.FAILED:
        return "failed"
    if attempt is not None and attempt.status == attempt.Status.EXPIRED:
        return "expired"
    if proposal.status == proposal.Status.INVOICE_CREATED:
        return "pending"
    if proposal.status == proposal.Status.DETAILS_LOCKED:
        return "locked"
    return "ready"


def _item_context(item):
    return {
        "title": item.product_title,
        "image_url": item.image_url,
        "color_code": item.color_code,
        "color_label": item.color_label,
        "fit_label": item.fit_label,
        "size": item.size,
        "quantity": item.quantity,
        "unit_price": _money(item.quoted_unit_price),
        "line_total": _money(item.quoted_line_total),
    }


def _proposal_context(proposal, *, request, form_error="", form_error_field="", form_values=None):
    language = _locale(proposal.locale)
    copy = CHECKOUT_COPY[language]
    state = _checkout_state(proposal)
    attempt = proposal.payment_attempt
    delivery_locked = bool(proposal.details_locked_at) or state in {
        "locked",
        "pending",
        "paid",
    }
    payable = state == "ready" and not delivery_locked
    share_allowed = state in {"ready", "locked", "pending"}
    masked_delivery = None
    if delivery_locked and attempt is not None:
        masked_delivery = {
            "name": _mask_name(attempt.full_name),
            "phone": _mask_phone(attempt.phone),
            "email": _mask_email(attempt.email),
        }
    return {
        "copy": copy,
        "html_lang": language,
        "checkout_state": state,
        "state_title": copy[f"state_{state}_title"],
        "state_body": copy[f"state_{state}_body"],
        "customer_name": _customer_name(proposal.client.display_name),
        "proposal": {
            "public_id": str(proposal.public_id),
            "reference": str(proposal.public_id).split("-", 1)[0].upper(),
            "revision": proposal.revision,
            "currency": proposal.currency,
            "catalog_total": _money(proposal.catalog_total),
            "discount": _money(proposal.negotiated_discount),
            "total": _money(proposal.requested_payment_amount),
            "has_discount": proposal.negotiated_discount > 0,
            "allow_promo": proposal.allow_promo,
            "expires_at": proposal.expires_at,
            "expires_at_iso": proposal.expires_at.isoformat(),
        },
        "items": [_item_context(item) for item in proposal.items.all()],
        "delivery_locked": delivery_locked,
        "masked_delivery": masked_delivery,
        "payable": payable,
        "share_allowed": share_allowed,
        "share_url": reverse(
            "ig_checkout_share_token",
            kwargs={"proposal_id": proposal.public_id},
        ),
        "proposal_url": request.build_absolute_uri(
            reverse(
                "ig_checkout_proposal",
                kwargs={"proposal_id": proposal.public_id},
            )
        ),
        "np_city_search_url": reverse("cart_np_city_search"),
        "np_warehouse_search_url": reverse("cart_np_warehouse_search"),
        "direct_url": INSTAGRAM_DIRECT_URL,
        "privacy_url": reverse("privacy_policy"),
        "form_error": form_error,
        "form_error_field": form_error_field,
        "form_values": form_values or {},
    }


@require_GET
@never_cache
def ig_checkout_token_entry(request, token):
    """Consume a bearer URL once, then redirect before page assets load."""
    digest = IgCheckoutAccessToken.digest(token)
    now = timezone.now()
    with __import__("django.db", fromlist=["transaction"]).transaction.atomic():
        access_token = (
            IgCheckoutAccessToken.objects.select_for_update()
            .select_related("proposal")
            .filter(token_digest=digest, revoked_at__isnull=True)
            .first()
        )
        if access_token is None:
            return _private_headers(HttpResponse("Посилання недійсне.", status=410))
        proposal = access_token.proposal
        if access_token.expires_at <= now or proposal.expires_at <= now:
            return _private_headers(HttpResponse("Термін посилання завершився.", status=410))
        _save_grant(request, proposal, access_token)
        access_token.use_count += 1
        access_token.last_used_at = now
        access_token.save(update_fields=["use_count", "last_used_at"])
        if proposal.status == IgCheckoutProposal.Status.READY:
            proposal.status = IgCheckoutProposal.Status.VIEWED
            proposal.viewed_at = proposal.viewed_at or now
            proposal.save(update_fields=["status", "viewed_at", "updated_at"])
    response = redirect("ig_checkout_proposal", proposal_id=proposal.public_id)
    return _private_headers(response)


@require_http_methods(["GET", "POST"])
@never_cache
def ig_checkout_proposal(request, proposal_id):
    proposal = get_object_or_404(
        IgCheckoutProposal.objects.select_related(
            "client",
            "payment_attempt",
            "provider_cancellation_event",
            "deal",
        ).prefetch_related("items"),
        public_id=proposal_id,
    )
    _grant, _token = _load_grant(request, proposal)
    if request.method == "POST":
        from management.services.ig_checkout_payment import (
            CheckoutPaymentError,
            create_or_reuse_invoice,
        )

        try:
            _attempt, invoice_url, _reused = create_or_reuse_invoice(
                proposal,
                request=request,
                payload=request.POST,
            )
        except CheckoutPaymentError as exc:
            proposal.refresh_from_db()
            language = _locale(proposal.locale)
            context = _proposal_context(
                proposal,
                request=request,
                form_error=_localized_error(language, exc.code, exc.message),
                form_error_field=exc.field,
                form_values=request.POST,
            )
            status = 409 if exc.code == "in_progress" else 400
            return _private_headers(render(request, "pages/ig_checkout.html", context, status=status))
        return _private_headers(redirect(invoice_url))
    context = _proposal_context(proposal, request=request)
    return _private_headers(render(request, "pages/ig_checkout.html", context))


@require_POST
@never_cache
def ig_checkout_share_token(request, proposal_id):
    proposal = get_object_or_404(IgCheckoutProposal, public_id=proposal_id)
    _grant, _token = _load_grant(request, proposal)
    now = timezone.now()
    if proposal.expires_at <= now or proposal.status not in {
        IgCheckoutProposal.Status.READY,
        IgCheckoutProposal.Status.VIEWED,
        IgCheckoutProposal.Status.DETAILS_LOCKED,
        IgCheckoutProposal.Status.INVOICE_CREATED,
    }:
        return _private_headers(JsonResponse({"error": "unavailable"}, status=410))
    raw_token, share_token = IgCheckoutAccessToken.issue(
        proposal=proposal,
        kind=IgCheckoutAccessToken.Kind.SHARE,
        expires_at=proposal.expires_at,
    )
    url = request.build_absolute_uri(
        reverse("ig_checkout_token_entry", kwargs={"token": raw_token})
    )
    response = JsonResponse({"url": url, "expires_at": share_token.expires_at.isoformat()})
    return _private_headers(response)
