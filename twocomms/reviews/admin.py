"""Admin for the moderation queue.

Workflow:
    1. Reviews land with ``status='pending'``.
    2. Moderators land on the changelist filtered to ``status=pending``
       (default via list_filter); see them in chronological order.
    3. Bulk actions ``approve_selected`` / ``reject_selected`` flip the
       state and stamp ``moderated_by`` + ``moderated_at``.
    4. ``moderation_note`` is editable on the change form for
       institutional memory.
"""

from __future__ import annotations

from django.contrib import admin
from django.utils import timezone

from .models import Review, ReviewImage, ReviewStatus, ReviewVote


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 0
    fields = ("image", "order")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product",
        "rating_stars",
        "author_name",
        "status",
        "is_verified_purchase",
        "helpful_count",
        "created_at",
    )
    list_filter = ("status", "is_verified_purchase", "rating", "created_at")
    list_select_related = ("product", "user")
    search_fields = (
        "id", "title", "body", "author_name", "email",
        "product__title", "product__slug",
    )
    autocomplete_fields = ("product", "user", "moderated_by")
    readonly_fields = (
        "created_at", "updated_at", "moderated_at",
        "helpful_count", "unhelpful_count", "is_verified_purchase",
    )
    inlines = [ReviewImageInline]
    actions = ("approve_selected", "reject_selected")
    fieldsets = (
        ("Контент", {
            "fields": (
                "product", "rating", "title", "body",
                ("author_name", "user"),
                ("email", "anon_key"),
            ),
        }),
        ("Модерація", {
            "fields": (
                "status", "moderation_note",
                ("moderated_by", "moderated_at"),
            ),
            "description": (
                "Перед публікацією переконайтеся, що відгук осмислений, "
                "не містить персональних даних і не порушує політику. "
                "Bulk-actions зверху роблять те саме за один клік."
            ),
        }),
        ("Метрики", {
            "fields": (
                "is_verified_purchase",
                ("helpful_count", "unhelpful_count"),
                ("created_at", "updated_at"),
            ),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Оцінка", ordering="rating")
    def rating_stars(self, obj: Review) -> str:
        full = "★" * int(obj.rating)
        empty = "☆" * (5 - int(obj.rating))
        return f"{full}{empty}"

    @admin.action(description="Опублікувати вибрані відгуки")
    def approve_selected(self, request, queryset):
        now = timezone.now()
        updated = queryset.exclude(status=ReviewStatus.APPROVED).update(
            status=ReviewStatus.APPROVED,
            moderated_at=now,
            moderated_by=request.user if request.user.is_authenticated else None,
        )
        self.message_user(request, f"Опубліковано: {updated}.")

    @admin.action(description="Відхилити вибрані відгуки")
    def reject_selected(self, request, queryset):
        now = timezone.now()
        updated = queryset.exclude(status=ReviewStatus.REJECTED).update(
            status=ReviewStatus.REJECTED,
            moderated_at=now,
            moderated_by=request.user if request.user.is_authenticated else None,
        )
        self.message_user(request, f"Відхилено: {updated}.")


@admin.register(ReviewVote)
class ReviewVoteAdmin(admin.ModelAdmin):
    list_display = ("id", "review", "user", "anon_key", "value", "created_at")
    list_filter = ("value", "created_at")
    search_fields = ("review__id", "user__username", "anon_key")
    autocomplete_fields = ("review", "user")
    readonly_fields = ("created_at",)
