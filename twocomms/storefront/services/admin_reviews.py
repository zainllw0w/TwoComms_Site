"""Phase 21 (PR-A1) — review moderation context for the custom admin
panel section ``?section=reviews``.

Provides three slices the template renders as tabs:

* ``pending``  — newest-first queue waiting for a moderator
* ``approved`` — recently approved (most recent 20)
* ``rejected`` — recently rejected (most recent 20)

Plus aggregate counters for the nav badge / KPI strip and a per-row
``admin_url`` so each card can link straight to Django-admin for
deep edits (image attachments, raw text, etc.).

Pure functions; no I/O outside ORM queries.
"""

from __future__ import annotations

from typing import Any, Dict

from django.urls import reverse
from django.utils.html import escape


# Limit per "recent" tab — keep the page light. The Pending tab shows
# the FULL queue (since clearing it is the whole point of moderation).
_RECENT_LIMIT = 20


def _augment(reviews):
    """Attach UI-only properties without mutating the model layer.

    Returns a list of dicts so the template stays decoupled from the
    Review model surface.
    """
    out = []
    for r in reviews:
        try:
            admin_url = reverse("admin:reviews_review_change", args=[r.pk])
        except Exception:
            admin_url = ""
        out.append({
            "id": r.pk,
            "rating": int(r.rating),
            "title": r.title or "",
            "body": r.body or "",
            "body_preview": (r.body[:240] + "…") if r.body and len(r.body) > 240 else (r.body or ""),
            "author_name": r.author_name or "",
            "user_id": r.user_id,
            "is_verified_purchase": bool(r.is_verified_purchase),
            "status": r.status,
            "created_at": r.created_at,
            "moderated_at": r.moderated_at,
            "moderation_note": r.moderation_note or "",
            "helpful_count": int(r.helpful_count or 0),
            "unhelpful_count": int(r.unhelpful_count or 0),
            "image_count": r.images.count() if hasattr(r, "images") else 0,
            "product": {
                "id": r.product_id,
                "title": getattr(r.product, "title", "") or "",
                "slug": getattr(r.product, "slug", "") or "",
            },
            "admin_url": admin_url,
            "public_anchor": (
                f"/product/{r.product.slug}/#review-{r.pk}"
                if getattr(r.product, "slug", "")
                else ""
            ),
            "stars_html": (
                "★" * int(r.rating) + "☆" * (5 - int(r.rating))
            ),
        })
    return out


def build_reviews_context() -> Dict[str, Any]:
    """Return the full ``?section=reviews`` payload.

    Heavy ORM hits are kept narrow: each tab does a single
    ``select_related('product')`` + ``prefetch_related('images')``
    plus a ``COUNT`` per status for the KPI strip.
    """
    from reviews.models import Review, ReviewStatus

    pending_qs = (
        Review.objects
        .filter(status=ReviewStatus.PENDING)
        .select_related("product", "user")
        .prefetch_related("images")
        .order_by("created_at")
    )
    approved_qs = (
        Review.objects
        .filter(status=ReviewStatus.APPROVED)
        .select_related("product", "user")
        .prefetch_related("images")
        .order_by("-moderated_at", "-created_at")[: _RECENT_LIMIT]
    )
    rejected_qs = (
        Review.objects
        .filter(status=ReviewStatus.REJECTED)
        .select_related("product", "user")
        .prefetch_related("images")
        .order_by("-moderated_at", "-created_at")[: _RECENT_LIMIT]
    )

    counters = {
        "pending":  Review.objects.filter(status=ReviewStatus.PENDING).count(),
        "approved": Review.objects.filter(status=ReviewStatus.APPROVED).count(),
        "rejected": Review.objects.filter(status=ReviewStatus.REJECTED).count(),
    }
    counters["total"] = sum(counters.values())

    return {
        "reviews_pending":  _augment(pending_qs),
        "reviews_approved": _augment(approved_qs),
        "reviews_rejected": _augment(rejected_qs),
        "reviews_counters": counters,
        "reviews_recent_limit": _RECENT_LIMIT,
    }


__all__ = ["build_reviews_context"]
