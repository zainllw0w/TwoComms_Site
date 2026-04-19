import logging
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from django.conf import settings
from django.urls import reverse


logger = logging.getLogger(__name__)

CORE_INDEXNOW_ROUTE_NAMES = (
    "home",
    "catalog",
    "custom_print",
    "delivery",
    "about",
    "contacts",
    "cooperation",
    "help_center",
    "faq",
    "size_guide",
    "care_guide",
    "order_tracking",
    "site_map_page",
    "news",
    "returns",
    "privacy_policy",
    "terms_of_service",
    "wholesale_page",
)


def get_site_base_url() -> str:
    base_url = (getattr(settings, "SITE_BASE_URL", "") or "https://twocomms.shop").strip()
    return base_url.rstrip("/")


def build_absolute_url(path: str) -> str:
    if not path:
        return get_site_base_url()
    if path.startswith(("http://", "https://")):
        return path
    return urljoin(f"{get_site_base_url()}/", path.lstrip("/"))


def get_indexnow_key() -> str:
    return (getattr(settings, "INDEXNOW_KEY", "") or "").strip()


def is_indexnow_enabled() -> bool:
    return bool(getattr(settings, "INDEXNOW_ENABLED", True))


def is_indexnow_configured() -> bool:
    return is_indexnow_enabled() and bool(get_indexnow_key())


def get_indexnow_host() -> str:
    return urlparse(get_site_base_url()).netloc


def get_indexnow_key_location() -> str:
    key = get_indexnow_key()
    if not key:
        return ""
    return build_absolute_url(f"/{key}.txt")


def get_product_public_url(product) -> str | None:
    if not product or not getattr(product, "slug", None):
        return None
    if getattr(product, "status", None) != "published":
        return None
    return build_absolute_url(f"/product/{product.slug}/")


def get_category_public_url(category) -> str | None:
    if not category or not getattr(category, "slug", None):
        return None
    if not getattr(category, "is_active", False):
        return None
    return build_absolute_url(f"/catalog/{category.slug}/")


def get_core_indexnow_urls() -> list[str]:
    return [build_absolute_url(reverse(route_name)) for route_name in CORE_INDEXNOW_ROUTE_NAMES]


def _normalize_urls(urls: Iterable[str]) -> list[str]:
    host = get_indexnow_host()
    normalized: list[str] = []
    seen: set[str] = set()

    for raw_url in urls:
        if not raw_url:
            continue
        url = raw_url.strip()
        if not url:
            continue
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != host:
            continue
        if url in seen:
            continue
        seen.add(url)
        normalized.append(url)

    return normalized


def submit_indexnow_urls(urls: Iterable[str]) -> bool:
    normalized_urls = _normalize_urls(urls)
    if not normalized_urls:
        return False

    if not is_indexnow_configured():
        logger.debug("IndexNow is not configured; skipped %s URLs", len(normalized_urls))
        return False

    timeout = float(getattr(settings, "INDEXNOW_TIMEOUT", 2.5) or 2.5)
    endpoint = getattr(settings, "INDEXNOW_ENDPOINT", "https://api.indexnow.org/indexnow")
    payload = {
        "host": get_indexnow_host(),
        "key": get_indexnow_key(),
        "keyLocation": get_indexnow_key_location(),
        "urlList": normalized_urls,
    }

    response = requests.post(
        endpoint,
        json=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=timeout,
    )
    response.raise_for_status()
    logger.info("IndexNow accepted %s URL(s)", len(normalized_urls))
    return True


def enqueue_indexnow_urls(urls: Iterable[str]) -> bool:
    normalized_urls = _normalize_urls(urls)
    if not normalized_urls or not is_indexnow_configured():
        return False

    try:
        from storefront.tasks import submit_indexnow_urls_task

        submit_indexnow_urls_task.delay(normalized_urls)
        return True
    except Exception as exc:  # pragma: no cover - Celery may be absent locally
        logger.warning("Celery unavailable for IndexNow, falling back to sync submit: %s", exc)
        try:
            return submit_indexnow_urls(normalized_urls)
        except Exception as sync_exc:  # pragma: no cover - defensive branch
            logger.error("Synchronous IndexNow submit failed: %s", sync_exc, exc_info=True)
            return False
