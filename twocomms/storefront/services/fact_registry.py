"""Versioned registry for public facts shared by SEO and commerce surfaces.

Only facts with a concrete runtime owner belong here.  Editorial claims that
do not have an owner are intentionally absent instead of being guessed for
keyword coverage.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings


PUBLIC_FACTS_VERSION = "2026-08-13"


@dataclass(frozen=True)
class PublicFact:
    value: object
    owner: str
    source: str
    locale: str
    effective_date: str


def free_shipping_threshold() -> Decimal:
    """Return the same threshold used by checkout and mini-cart logic."""
    return Decimal(str(getattr(settings, "FREE_SHIPPING_THRESHOLD", "3000")))


PUBLIC_FACTS = {
    "free_shipping_threshold": PublicFact(
        value=free_shipping_threshold,
        owner="checkout_settings",
        source="settings.FREE_SHIPPING_THRESHOLD",
        locale="all",
        effective_date=PUBLIC_FACTS_VERSION,
    ),
}
