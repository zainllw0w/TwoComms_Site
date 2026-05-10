"""Phase 21 (PR-4c) — review submission + voting endpoints.

All routes are POST-only and CSRF-protected via Django's default
middleware. Rate-limiting is intentionally lightweight (cache-backed
counter keyed by IP+product) so we don't take a hard dependency on
django-ratelimit for one endpoint; the moderation queue is the real
backstop against spam.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from storefront.models import Product

from .forms import ReviewForm
from .models import Review, ReviewImage, ReviewStatus, ReviewVote
from .services.permissions import has_paid_order_with_product


log = logging.getLogger(__name__)


# Photo upload caps. Enforced server-side; the template's <input
# type="file" multiple> doesn't natively limit count or size.
_MAX_IMAGES_PER_REVIEW = 5
_MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
_ALLOWED_IMAGE_CT = {"image/jpeg", "image/png", "image/webp"}

# Guest rate-limit — at most ``_GUEST_RATE_LIMIT`` review submissions
# per ``_GUEST_RATE_WINDOW`` seconds per (IP, product) tuple. Auth
# users are not rate-limited here (admin can ban abusers manually).
_GUEST_RATE_LIMIT = 2
_GUEST_RATE_WINDOW = 60 * 60  # 1 hour


def _client_ip(request: HttpRequest) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def _anon_key(request: HttpRequest) -> str:
    """Stable per-session-ish guest identity. Hashed so we never store
    raw IPs alongside review content."""
    raw = f"{_client_ip(request)}|{request.session.session_key or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def _is_rate_limited(request: HttpRequest, product_id: int) -> bool:
    if request.user.is_authenticated:
        return False
    key = f"reviews:rl:{_client_ip(request)}:{product_id}"
    current = cache.get(key, 0) or 0
    if current >= _GUEST_RATE_LIMIT:
        return True
    cache.set(key, current + 1, _GUEST_RATE_WINDOW)
    return False


def _validate_uploaded_images(files):
    """Return a list of cleaned file objects or raise ``ValueError``.

    ``files`` is a ``MultiValueDict.getlist('images')`` result; we
    cap at ``_MAX_IMAGES_PER_REVIEW`` and reject oversize / wrong-MIME
    files outright (no silent truncation — the user deserves to know).
    """
    cleaned = []
    for f in files[: _MAX_IMAGES_PER_REVIEW + 1]:
        if len(cleaned) >= _MAX_IMAGES_PER_REVIEW:
            raise ValueError(f"Максимум {_MAX_IMAGES_PER_REVIEW} фото на відгук.")
        if f.size > _MAX_IMAGE_SIZE_BYTES:
            raise ValueError(f"Фото «{f.name}» більше за 5 МБ.")
        ct = (getattr(f, "content_type", "") or "").lower()
        if ct not in _ALLOWED_IMAGE_CT:
            raise ValueError(
                f"Фото «{f.name}»: дозволені формати JPEG, PNG, WebP."
            )
        cleaned.append(f)
    return cleaned


def _redirect_back(request: HttpRequest, product: Product) -> HttpResponseRedirect:
    """After a (form) POST we always bounce to the product page with
    an anchor so the user sees their pending notice / errors. We
    never trust ``HTTP_REFERER`` blindly — must point at our own
    product URL."""
    return HttpResponseRedirect(
        reverse("product", kwargs={"slug": product.slug}) + "#product-reviews"
    )


@require_POST
def submit_review(request: HttpRequest, product_slug: str):
    """Public endpoint — anyone can POST. Auth users get
    ``is_verified_purchase=True`` automatically when they have a paid
    order containing the product.

    Returns:
        JsonResponse for AJAX (``X-Requested-With == XMLHttpRequest``),
        or a 302 to the PDP otherwise.
    """
    product = get_object_or_404(
        Product.objects.filter(status="published"),
        slug=product_slug,
    )

    is_ajax = request.headers.get("X-Requested-With", "") == "XMLHttpRequest"

    if _is_rate_limited(request, product.id):
        msg = "Забагато спроб. Спробуйте через годину."
        if is_ajax:
            return JsonResponse({"ok": False, "error": msg}, status=429)
        messages.error(request, msg)
        return _redirect_back(request, product)

    form = ReviewForm(request.POST)
    if not form.is_valid():
        # Compact error format for AJAX, message-bus for traditional POST.
        if is_ajax:
            return JsonResponse(
                {"ok": False, "errors": form.errors.get_json_data()},
                status=400,
            )
        for error in form.errors.values():
            messages.error(request, error[0])
        return _redirect_back(request, product)

    cleaned = form.cleaned_data
    if cleaned.get("_is_bot"):
        # Honeypot tripped — pretend success, drop silently. Logging
        # the IP so abuse-watch dashboards can see the rate.
        log.info("reviews.honeypot.tripped ip=%s product=%s", _client_ip(request), product.id)
        if is_ajax:
            return JsonResponse({"ok": True, "status": "pending"})
        messages.success(request, "Дякуємо! Ваш відгук на модерації.")
        return _redirect_back(request, product)

    # Photos (optional).
    try:
        images = _validate_uploaded_images(request.FILES.getlist("images"))
    except ValueError as exc:
        if is_ajax:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        messages.error(request, str(exc))
        return _redirect_back(request, product)

    user = request.user if request.user.is_authenticated else None
    anon_key = "" if user else _anon_key(request)
    is_verified = has_paid_order_with_product(user, product) if user else False

    review = Review.objects.create(
        product=product,
        user=user,
        author_name=cleaned["author_name"],
        email=cleaned.get("email") or "",
        anon_key=anon_key,
        rating=cleaned["rating"],
        title=cleaned.get("title") or "",
        body=cleaned["body"],
        is_verified_purchase=is_verified,
        status=ReviewStatus.PENDING,
    )
    for idx, f in enumerate(images):
        ReviewImage.objects.create(review=review, image=f, order=idx)

    if is_ajax:
        return JsonResponse({"ok": True, "status": "pending", "review_id": review.id})
    messages.success(
        request,
        "Дякуємо! Ваш відгук відправлено на модерацію — після перевірки він зʼявиться на сторінці товару.",
    )
    return _redirect_back(request, product)


@require_POST
def vote_review(request: HttpRequest, review_id: int):
    """Helpful / unhelpful vote. JSON-only (called from PDP JS)."""
    try:
        review = Review.objects.get(pk=review_id, status=ReviewStatus.APPROVED)
    except Review.DoesNotExist:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    value = (request.POST.get("value") or "").strip()
    if value not in (ReviewVote.HELPFUL, ReviewVote.UNHELPFUL):
        return HttpResponseBadRequest("invalid value")

    user = request.user if request.user.is_authenticated else None
    anon_key = "" if user else _anon_key(request)

    # Upsert: same user/anon flipping their vote rewrites the row
    # rather than creating a duplicate (constraints would block it).
    lookup = {"review": review}
    if user is not None:
        lookup["user"] = user
    else:
        lookup["user__isnull"] = True
        lookup["anon_key"] = anon_key

    existing = ReviewVote.objects.filter(**lookup).first()
    if existing is not None:
        if existing.value == value:
            # idempotent — already voted this way
            pass
        else:
            existing.value = value
            existing.save(update_fields=["value"])
    else:
        ReviewVote.objects.create(
            review=review,
            user=user,
            anon_key=anon_key if user is None else "",
            value=value,
        )

    # Recompute aggregate counters cheaply.
    helpful = ReviewVote.objects.filter(review=review, value=ReviewVote.HELPFUL).count()
    unhelpful = ReviewVote.objects.filter(review=review, value=ReviewVote.UNHELPFUL).count()
    Review.objects.filter(pk=review.pk).update(
        helpful_count=helpful, unhelpful_count=unhelpful
    )

    return JsonResponse({"ok": True, "helpful": helpful, "unhelpful": unhelpful})


@login_required
def my_reviews(request: HttpRequest):
    """Phase 21 (R12) — personal cabinet section listing the logged-in
    user's reviews grouped by moderation status. Read-only — editing
    requires re-submitting via the PDP form; rejections show the
    moderator note so the user understands why.
    """
    reviews_qs = (
        Review.objects
        .filter(user=request.user)
        .select_related("product")
        .prefetch_related("images")
        .order_by("-created_at")
    )
    counts = {
        "approved": 0,
        "pending": 0,
        "rejected": 0,
    }
    for r in reviews_qs:
        if r.status in counts:
            counts[r.status] += 1
    return render(
        request,
        "pages/my_reviews.html",
        {
            "reviews": reviews_qs,
            "counts": counts,
            "total_reviews": sum(counts.values()),
        },
    )
