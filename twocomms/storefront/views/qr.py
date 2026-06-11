"""QR thank-you landing (/qr/).

One QR code is printed on every garment / packaging insert and points
to this page. Marketing goals (owner spec, 2026-06-11):

* warm thank-you moment after unboxing;
* personal -5% promo for the next order, strictly once per account
  (reuses the survey promo infrastructure: ``PromoCode`` +
  ``UserPromoCode`` with a unique ``(user, survey_key)`` pair);
* anonymous visitors are nudged to log in so the gift can be attached
  to their account;
* upsell hooks: Instagram review (+10% promo via DM) and the hidden
  stacking-promos teaser.

The page is deliberately ``noindex`` (it must only be reachable from
the printed QR) and ``never_cache`` (per-user promo content).
"""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache

QR_PROMO_KEY = "qr_thanks_v1"
QR_PROMO_PERCENT = 5
QR_PROMO_DAYS = 7


def _get_or_create_qr_promo(user):
    """Return the user's QR promo, creating it on first visit.

    Idempotent: ``UserPromoCode`` is unique on ``(user, survey_key)``,
    so repeated scans always return the same code.
    """
    from ..models import PromoCode, PromoCodeGroup, UserPromoCode

    existing = (
        UserPromoCode.objects.select_related("promo_code")
        .filter(user=user, survey_key=QR_PROMO_KEY)
        .first()
    )
    if existing and existing.promo_code:
        return existing.promo_code

    group, _created = PromoCodeGroup.objects.get_or_create(
        name="QR подяка",
        defaults={
            "description": "Подарунок -5% за скан QR-коду на одязі/пакованні",
            "one_per_account": True,
            "is_active": True,
        },
    )

    now = timezone.now()
    with transaction.atomic():
        promo = PromoCode.objects.create(
            code=PromoCode.generate_code(),
            promo_type="regular",
            discount_type="percentage",
            discount_value=QR_PROMO_PERCENT,
            description="QR-подарунок: -5% на наступне замовлення",
            group=group,
            max_uses=1,
            one_time_per_user=True,
            valid_from=now,
            valid_until=now + timedelta(days=QR_PROMO_DAYS),
            is_active=True,
        )
        try:
            UserPromoCode.objects.create(
                user=user,
                promo_code=promo,
                survey_key=QR_PROMO_KEY,
                source="qr",
                expires_at=promo.valid_until,
            )
        except IntegrityError:
            # Race: another request already granted the promo. Use it.
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
    if request.user.is_authenticated:
        promo = _get_or_create_qr_promo(request.user)
        if promo is not None and not promo.is_valid_now():
            promo_expired = True

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
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response
