"""QR thank-you landing (`/qr/`).

Scanning the QR printed on clothing/packaging lands here. Everyone gets
a personal -5% promo code:

- Anonymous visitors get a code bound to their device (signed cookie,
  ~13 months + IP/UA/language fingerprint fallback), so the same person
  always sees the same code. Logging in "adopts" that exact code into
  the account (``UserPromoCode``), so nothing is lost.
- Authenticated users get/keep one code per account
  (``UserPromoCode`` unique on ``(user, survey_key)``).

Admins get a Telegram alert per scan session with running counters.
"""

import hashlib
import threading

from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import IntegrityError, close_old_connections, transaction
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache

QR_PROMO_KEY = "qr_thanks_v1"
QR_PROMO_PERCENT = 5
QR_PROMO_DAYS = 7
QR_SESSION_FLAG = "qr_scan_notified"
QR_COOKIE = "twc_qr_promo"
QR_COOKIE_SALT = "twc.qr.promo"
QR_COOKIE_MAX_AGE = 400 * 24 * 3600  # ~13 months


def _notify_admins_about_scan(username, promo_code, returning):
    """Telegram admin alert + running scan counter (owner request)."""
    try:
        close_old_connections()
        from ..models import PageView

        qr_views = PageView.objects.filter(
            path__in=["/qr/", "/qr", "/uk/qr/", "/ru/qr/", "/en/qr/"], is_bot=False
        )
        total = qr_views.count()
        today = qr_views.filter(when__date=timezone.now().date()).count()
        unique = qr_views.values("session").distinct().count()

        from orders.telegram_notifications import telegram_notifier

        who = f"<b>{username}</b>" if username else "анонім (без акаунта)"
        if returning:
            who += " — повторний візит, той самий пристрій"
        promo_line = f"\nПромокод: <code>{promo_code}</code>" if promo_code else ""
        message = (
            "📲 <b>Відскановано QR-код!</b>\n"
            f"Хто: {who}{promo_line}\n"
            f"Сканів сьогодні: <b>{today}</b>\n"
            f"Всього сканів: <b>{total}</b> (унікальних відвідувачів: {unique})"
        )
        telegram_notifier.send_admin_message(message)
    except Exception:
        # The thank-you page must never fail because of notifications.
        pass
    finally:
        close_old_connections()


def _get_promo_group():
    from ..models import PromoCodeGroup

    group, _created = PromoCodeGroup.objects.get_or_create(
        name="QR подяка",
        defaults={
            "description": "Подарунок -5% за скан QR-коду на одязі/пакованні",
            "one_per_account": True,
            "is_active": True,
        },
    )
    return group


def _create_promo():
    from ..models import PromoCode

    now = timezone.now()
    return PromoCode.objects.create(
        code=PromoCode.generate_code(),
        promo_type="regular",
        discount_type="percentage",
        discount_value=QR_PROMO_PERCENT,
        description="QR-подарунок: -5% на наступне замовлення",
        group=_get_promo_group(),
        max_uses=1,
        one_time_per_user=True,
        valid_from=now,
        valid_until=now + timedelta(days=QR_PROMO_DAYS),
        is_active=True,
    )


def _device_hash(request):
    """Stable, privacy-friendly device identifier (hashed, not reversible)."""
    ip = (
        (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
        or request.META.get("REMOTE_ADDR", "")
    )
    ua = request.META.get("HTTP_USER_AGENT", "")[:300]
    lang = request.META.get("HTTP_ACCEPT_LANGUAGE", "")[:60]
    raw = f"{ip}|{ua}|{lang}|{settings.SECRET_KEY[:16]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _promo_from_cookie(request):
    from ..models import PromoCode

    raw = request.COOKIES.get(QR_COOKIE)
    if not raw:
        return None
    try:
        code = signing.loads(raw, salt=QR_COOKIE_SALT, max_age=QR_COOKIE_MAX_AGE)
    except signing.BadSignature:
        return None
    return PromoCode.objects.filter(code=code).first()


def _get_or_create_anon_promo(request):
    """Promo for a visitor without an account, bound to the device.

    Returns (promo, returning) — ``returning`` is True when this device
    has already received a code before.
    """
    from ..models import QrDeviceGrant

    promo = _promo_from_cookie(request)
    if promo is not None:
        return promo, True

    dh = _device_hash(request)
    grant = QrDeviceGrant.objects.select_related("promo_code").filter(
        device_hash=dh
    ).first()
    if grant:
        QrDeviceGrant.objects.filter(pk=grant.pk).update(
            visits=grant.visits + 1, last_seen=timezone.now()
        )
        return grant.promo_code, True

    with transaction.atomic():
        promo = _create_promo()
        try:
            QrDeviceGrant.objects.create(
                device_hash=dh,
                promo_code=promo,
                ip=(request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
                or request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
            )
        except IntegrityError:
            promo.delete()
            grant = QrDeviceGrant.objects.select_related("promo_code").get(
                device_hash=dh
            )
            return grant.promo_code, True
    return promo, False


def _get_or_create_qr_promo(request, user):
    """Account promo. Adopts the visitor's anonymous device code if any."""
    from ..models import UserPromoCode

    existing = (
        UserPromoCode.objects.select_related("promo_code")
        .filter(user=user, survey_key=QR_PROMO_KEY)
        .first()
    )
    if existing and existing.promo_code:
        return existing.promo_code

    # The same person scanned before logging in — keep their code.
    adopted = _promo_from_cookie(request)
    promo = adopted if adopted is not None else _create_promo()

    try:
        UserPromoCode.objects.create(
            user=user,
            promo_code=promo,
            survey_key=QR_PROMO_KEY,
            source="qr",
            expires_at=promo.valid_until,
        )
    except IntegrityError:
        if adopted is None:
            promo.delete()
        existing = (
            UserPromoCode.objects.select_related("promo_code")
            .filter(user=user, survey_key=QR_PROMO_KEY)
            .first()
        )
        return existing.promo_code if existing else None
    return promo


@never_cache
def qr_thanks(request):
    promo = None
    promo_expired = False
    returning = False

    if request.user.is_authenticated:
        promo = _get_or_create_qr_promo(request, request.user)
    else:
        promo, returning = _get_or_create_anon_promo(request)

    if promo is not None and not promo.is_valid_now():
        promo_expired = True

    # Admin Telegram alert — once per visitor session, never blocking.
    if not request.session.get(QR_SESSION_FLAG):
        request.session[QR_SESSION_FLAG] = True
        threading.Thread(
            target=_notify_admins_about_scan,
            args=(
                request.user.username if request.user.is_authenticated else "",
                promo.code if promo else "",
                returning,
            ),
            daemon=True,
        ).start()

    response = render(
        request,
        "pages/qr_thanks.html",
        {
            "promo": promo,
            "promo_expired": promo_expired,
            "promo_percent": QR_PROMO_PERCENT,
            "promo_days": QR_PROMO_DAYS,
        },
    )
    if promo is not None:
        response.set_cookie(
            QR_COOKIE,
            signing.dumps(promo.code, salt=QR_COOKIE_SALT),
            max_age=QR_COOKIE_MAX_AGE,
            secure=True,
            httponly=True,
            samesite="Lax",
        )
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response
