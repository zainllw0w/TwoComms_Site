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
    "blog",
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


INDEXNOW_BATCH_SIZE = 100
INDEXNOW_DEFAULT_TIMEOUT = 5.0
INDEXNOW_DEFAULT_RETRIES = 2


def _chunked(items: list[str], size: int) -> Iterable[list[str]]:
    if size <= 0:
        size = INDEXNOW_BATCH_SIZE
    for start in range(0, len(items), size):
        yield items[start:start + size]


def submit_indexnow_urls(
    urls: Iterable[str],
    *,
    batch_size: int | None = None,
    retries: int | None = None,
) -> bool:
    """POST batches of URLs to IndexNow, retrying transient failures.

    Args:
        urls: iterable of absolute URLs (any non-matching/foreign-host URLs
            are filtered out by ``_normalize_urls``).
        batch_size: max URLs per HTTP call (defaults to
            ``settings.INDEXNOW_BATCH_SIZE`` or ``INDEXNOW_BATCH_SIZE``).
        retries: per-batch retry attempts on transient errors (timeout, 5xx).
            Defaults to ``settings.INDEXNOW_RETRIES`` or 2.

    Returns:
        ``True`` iff every batch was accepted by the IndexNow endpoint.
    """
    normalized_urls = _normalize_urls(urls)
    if not normalized_urls:
        return False

    if not is_indexnow_configured():
        logger.debug("IndexNow is not configured; skipped %s URLs", len(normalized_urls))
        return False

    timeout = float(getattr(settings, "INDEXNOW_TIMEOUT", INDEXNOW_DEFAULT_TIMEOUT) or INDEXNOW_DEFAULT_TIMEOUT)
    endpoint = getattr(settings, "INDEXNOW_ENDPOINT", "https://api.indexnow.org/indexnow")
    effective_batch = int(batch_size or getattr(settings, "INDEXNOW_BATCH_SIZE", INDEXNOW_BATCH_SIZE) or INDEXNOW_BATCH_SIZE)
    effective_retries = int(retries if retries is not None else getattr(settings, "INDEXNOW_RETRIES", INDEXNOW_DEFAULT_RETRIES))

    base_payload = {
        "host": get_indexnow_host(),
        "key": get_indexnow_key(),
        "keyLocation": get_indexnow_key_location(),
    }

    accepted = 0
    failed_batches = 0
    for batch in _chunked(normalized_urls, effective_batch):
        payload = {**base_payload, "urlList": batch}
        last_exc: Exception | None = None
        for attempt in range(effective_retries + 1):
            try:
                response = requests.post(
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                    timeout=timeout,
                )
                # IndexNow returns 200/202 on success; treat 4xx as fatal (not retryable).
                if response.status_code in (200, 202):
                    accepted += len(batch)
                    last_exc = None
                    break
                if 500 <= response.status_code < 600:
                    last_exc = RuntimeError(f"IndexNow {response.status_code}: {response.text[:200]}")
                    logger.warning("IndexNow %s on attempt %s/%s: %s",
                                   response.status_code, attempt + 1, effective_retries + 1, last_exc)
                    continue
                # 4xx — not retryable
                logger.error("IndexNow rejected batch (%s): %s", response.status_code, response.text[:200])
                last_exc = RuntimeError(f"IndexNow rejected ({response.status_code})")
                break
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_exc = exc
                logger.warning("IndexNow transient error on attempt %s/%s: %s",
                               attempt + 1, effective_retries + 1, exc)
                continue
            except Exception as exc:  # pragma: no cover - defensive
                last_exc = exc
                logger.error("IndexNow unexpected error: %s", exc, exc_info=True)
                break
        if last_exc is not None:
            failed_batches += 1

    if accepted:
        logger.info("IndexNow accepted %s/%s URL(s) in %s batches",
                    accepted, len(normalized_urls),
                    (len(normalized_urls) + effective_batch - 1) // effective_batch)
    return failed_batches == 0 and accepted > 0


def enqueue_indexnow_urls(urls: Iterable[str]) -> bool:
    """Submit URLs to IndexNow synchronously.

    This function is designed to be called from inside
    ``transaction.on_commit`` hooks so it never blocks the user's request
    before the DB commit is durable. The IndexNow request is lightweight
    (one HTTP POST, 2.5 s timeout by default) and degrades silently if
    the endpoint is slow or unreachable.

    Historically this helper tried to dispatch the work to a Celery task
    and fell back to sync. There is no Celery broker on the production
    host, so the extra hop was pure overhead; we now go straight to sync.
    """
    normalized_urls = _normalize_urls(urls)
    if not normalized_urls or not is_indexnow_configured():
        return False

    try:
        return submit_indexnow_urls(normalized_urls)
    except Exception as exc:  # pragma: no cover - defensive branch
        logger.error("IndexNow submit failed: %s", exc, exc_info=True)
        return False
