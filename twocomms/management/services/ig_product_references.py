"""Resolve customer supplied product references without guessing identities."""

from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import urlsplit

from storefront.models import Product, ProductStatus

from .ig_commerce_types import ProductReference, ReferenceSource


_STOREFRONT_HOSTS = frozenset({"twocomms.shop", "www.twocomms.shop"})
_INSTAGRAM_HOSTS = frozenset({"instagram.com", "www.instagram.com"})
_PRODUCT_PATH = re.compile(
    r"^/(?:(?:uk|ru|en)/)?product/(?P<slug>[-a-z0-9_]+)/?(?P<options>.*)$",
    re.I,
)
_INSTAGRAM_PATH = re.compile(r"^/(?:p|reel|tv)/(?P<code>[A-Za-z0-9_-]+)/?", re.I)


def _empty(source=ReferenceSource.UNKNOWN, reason="unknown_reference", **kwargs):
    return ProductReference(source=source, reason=reason, **kwargs)


def _parse_owned_url(value: str) -> ProductReference:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return _empty(reason="invalid_url")
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _STOREFRONT_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
    ):
        return _empty(reason="untrusted_storefront_url")
    match = _PRODUCT_PATH.match(parsed.path or "")
    if not match:
        return _empty(reason="not_product_url")
    slug = match.group("slug").lower()
    product = Product.objects.filter(slug=slug, status=ProductStatus.PUBLISHED).first()
    if product is None:
        return _empty(reason="unknown_product")

    raw_options = [part for part in match.group("options").strip("/").split("/") if part]
    constraints: dict[str, str] = {}
    known_colors = {
        variant.slug.lower(): "color"
        for variant in product.color_variants.all()
        if variant.slug
    }
    known_fits = {
        option.code.lower(): "fit"
        for option in product.fit_options.filter(is_active=True)
        if option.code
    }
    for option in raw_options:
        key = known_colors.get(option.lower()) or known_fits.get(option.lower())
        if key is None:
            return _empty(
                source=ReferenceSource.STOREFRONT,
                reason="invalid_product_option",
            )
        previous = constraints.get(key)
        if previous is not None and previous != option.lower():
            return _empty(
                source=ReferenceSource.STOREFRONT,
                reason="conflicting_product_options",
            )
        constraints[key] = option.lower()
    return ProductReference(
        product_id=product.pk,
        is_exact=True,
        source=ReferenceSource.STOREFRONT,
        reason="exact_storefront_product",
        constraints=tuple(sorted(constraints.items())),
    )


def _parse_instagram_url(value: str) -> ProductReference:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return _empty(reason="invalid_url")
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in _INSTAGRAM_HOSTS:
        return _empty(reason="untrusted_instagram_url")
    match = _INSTAGRAM_PATH.match(parsed.path or "")
    if not match:
        return _empty(reason="not_instagram_post")
    prefix = (parsed.path.strip("/").split("/", 1)[0] or "p").lower()
    external_reference = f"{prefix}:{match.group('code')}"
    return _empty(
        source=ReferenceSource.INSTAGRAM_POST,
        reason="instagram_catalog_match_required",
        external_reference=external_reference,
    )


def _apply_media_evidence(result: ProductReference, media_evidence) -> ProductReference:
    evidence = [item for item in (media_evidence or []) if isinstance(item, dict)]
    if not evidence:
        return result
    matching = []
    for item in evidence:
        product_id = item.get("product_id")
        if not isinstance(product_id, int):
            continue
        if result.external_reference and item.get("external_reference") != result.external_reference:
            continue
        if item.get("verified_mapping") is True:
            matching.append(product_id)
    unique_verified = tuple(sorted(set(matching)))
    if len(unique_verified) == 1:
        return ProductReference(
            product_id=unique_verified[0],
            is_exact=True,
            source=result.source,
            reason="verified_media_mapping",
            external_reference=result.external_reference,
        )

    visual = [
        int(item["product_id"])
        for item in evidence
        if isinstance(item.get("product_id"), int)
        and item.get("verified_mapping") is not True
        and item.get("kind") in {"screenshot", "photo", "image"}
    ]
    if visual:
        return ProductReference(
            source=ReferenceSource.SCREENSHOT,
            reason="visual_match_requires_confirmation",
            candidate_product_ids=tuple(sorted(set(visual)))[:3],
        )
    return result


def resolve_product_reference(value: str | None, *, media_evidence=None) -> ProductReference:
    """Resolve the strongest reference in a message.

    Product links are authoritative.  Instagram links and images remain
    evidence until a verified local mapping (or a later deterministic match)
    supplies the product identity.
    """
    text = str(value or "")
    urls = re.findall(r"https?://[^\s<>]+", text)
    if not urls:
        if media_evidence:
            return _apply_media_evidence(
                _empty(source=ReferenceSource.SCREENSHOT, reason="visual_match_requires_confirmation"),
                media_evidence,
            )
        return _empty()

    storefront_results = [_parse_owned_url(url.rstrip(".,);]")) for url in urls]
    exact_storefront = [item for item in storefront_results if item.is_exact]
    if exact_storefront:
        product_ids = {item.product_id for item in exact_storefront}
        if len(product_ids) > 1:
            return _empty(source=ReferenceSource.STOREFRONT, reason="conflicting_product_references")
        constraints = defaultdict(set)
        for item in exact_storefront:
            for key, val in item.constraints:
                constraints[key].add(val)
        if any(len(values) > 1 for values in constraints.values()):
            return _empty(source=ReferenceSource.STOREFRONT, reason="conflicting_product_options")
        result = exact_storefront[0]
        return ProductReference(
            product_id=result.product_id,
            is_exact=True,
            source=result.source,
            reason=result.reason,
            constraints=tuple(sorted((key, next(iter(values))) for key, values in constraints.items())),
        )
    storefront_failures = [
        item for item in storefront_results if item.source == ReferenceSource.STOREFRONT
    ]
    if storefront_failures:
        return storefront_failures[0]

    instagram_results = [_parse_instagram_url(url.rstrip(".,);]")) for url in urls]
    instagram_results = [item for item in instagram_results if item.source == ReferenceSource.INSTAGRAM_POST]
    if instagram_results:
        external = instagram_results[0].external_reference
        if any(item.external_reference != external for item in instagram_results):
            return _empty(source=ReferenceSource.INSTAGRAM_POST, reason="conflicting_media_references")
        return _apply_media_evidence(instagram_results[0], media_evidence)

    return _empty(reason="unrecognized_reference")


ReferenceSource = ReferenceSource
