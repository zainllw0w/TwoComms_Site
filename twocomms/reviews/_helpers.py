"""Internal helpers shared by services / views.

Kept private (leading underscore) — not part of the public API.
"""

from __future__ import annotations

from django.db.models import Q

from .models import Review


def _build_review_owner_filter(*, user, anon_key: str, product):
    """Return a queryset of Review rows owned by ``user`` (auth) or
    ``anon_key`` (guest) for ``product``. Used to enforce "one review
    per submitter per product" at the form layer.
    """
    qs = Review.objects.filter(product=product)
    if user is not None and getattr(user, "is_authenticated", False):
        return qs.filter(user=user)
    if anon_key:
        return qs.filter(user__isnull=True, anon_key=anon_key)
    # No identity → never matches.
    return qs.none()
