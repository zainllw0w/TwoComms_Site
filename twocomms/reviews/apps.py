from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    """Phase 21 (2026-05-10) — product reviews.

    Surfaces real, moderated user reviews on the PDP and feeds the
    Product ``aggregateRating`` (only emitted at ≥3 approved reviews,
    per ``storefront.templatetags.seo_tags.product_rating_schema``).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "reviews"
    verbose_name = "Відгуки про товари"

    def ready(self):
        # Register signal handlers (IndexNow ping on approve, etc.).
        # Imported lazily so app loading order doesn't matter.
        from . import signals  # noqa: F401
