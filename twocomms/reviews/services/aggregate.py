"""Phase 21 (2026-05-10) — review aggregation.

The single source of truth for "what does the PDP / Product schema
``aggregateRating`` show?". Every other layer (template tags, schema
generator, admin dashboards) MUST go through this module so the
business rule "AggregateRating only at ≥3 approved reviews" is
enforced exactly once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.db.models import Avg, Count

from reviews.models import Review, ReviewStatus


# Threshold below which we deliberately HIDE the rating block and
# do NOT emit ``aggregateRating`` JSON-LD. Two reasons:
#
# 1. Google ignores or warns about AggregateRating with very few
#    reviews — they suspect manipulation.
# 2. UX: showing "1 review, 5★" looks sketchier than showing nothing
#    and a friendly "Будь першим, хто залишить відгук" CTA.
MIN_APPROVED_REVIEWS_FOR_RATING = 3


@dataclass(frozen=True)
class ProductReviewSummary:
    """Plain data the template / schema layer consumes."""

    count: int                      # always the real approved count
    avg: Optional[float]            # 1.0–5.0, rounded to 1dp; None when empty
    histogram: dict[int, int]       # {5: n5, 4: n4, ..., 1: n1} — zero-filled
    show_rating: bool               # count >= MIN_APPROVED_REVIEWS_FOR_RATING

    @property
    def has_any_approved(self) -> bool:
        return self.count > 0

    # Templates predating this datastore were hardcoded to access
    # ``.average`` (see ``pages/product_detail.html`` line ~197). Keep
    # the alias to avoid forking copy across templates.
    @property
    def average(self) -> Optional[float]:
        return self.avg


def aggregate_rating_for_product(product) -> ProductReviewSummary:
    """Compute the public review summary for a single product.

    Cheap query: one ``COUNT`` + one ``AVG`` plus a histogram via
    ``values('rating').annotate(Count('id'))`` — all hitting the
    ``rev_status_product_idx`` index.
    """

    qs = Review.objects.filter(
        product=product,
        status=ReviewStatus.APPROVED,
    )

    agg = qs.aggregate(count=Count("id"), avg=Avg("rating"))
    count = int(agg["count"] or 0)
    avg_value = agg["avg"]
    avg = round(float(avg_value), 1) if avg_value is not None else None

    # Histogram: always include keys 1..5 even if empty so the
    # template can render bars without conditionals.
    histogram = {k: 0 for k in range(1, 6)}
    if count:
        for row in qs.values("rating").annotate(n=Count("id")):
            rating = int(row["rating"])
            if 1 <= rating <= 5:
                histogram[rating] = int(row["n"])

    return ProductReviewSummary(
        count=count,
        avg=avg,
        histogram=histogram,
        show_rating=count >= MIN_APPROVED_REVIEWS_FOR_RATING,
    )


__all__ = [
    "MIN_APPROVED_REVIEWS_FOR_RATING",
    "ProductReviewSummary",
    "aggregate_rating_for_product",
]
