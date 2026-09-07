"""Redact customer media before it enters durable manager-notification payloads."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import re
from urllib.parse import urlsplit

from django.urls import reverse
from django.utils import timezone


_PROVIDER_MEDIA_SUFFIXES = ("cdninstagram.com", "fbcdn.net", "fbsbx.com")
_OUTWARD_MEDIA_FIELDS = (
    "role", "url", "local_url", "product_id", "product_title", "product_url", "confidence",
)
_CUSTOMER_ROLES = frozenset({"receipt", "payment_candidate"})
_PRIVATE_PREVIEW_PATH_RE = re.compile(r"^/bot/private-media/[1-9][0-9]*/mp1_[0-9a-f]{32}/preview/$")
_URL_RE = re.compile(r"https?://[^\s<>\"'\]\)]+", re.IGNORECASE)
_ANCHOR_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*(['\"])(?P<url>.*?)\1[^>]*>.*?</a>",
    re.IGNORECASE | re.DOTALL,
)


def _provider_media_url(value: object) -> bool:
    try:
        hostname = (urlsplit(str(value or "")).hostname or "").casefold()
    except ValueError:
        return False
    return any(hostname == suffix or hostname.endswith(f".{suffix}") for suffix in _PROVIDER_MEDIA_SUFFIXES)


def _legacy_customer_url(value: object) -> bool:
    try:
        path = (urlsplit(str(value or "")).path or "").casefold()
    except ValueError:
        return False
    return "/ig_message_media/" in path or "/ig_payment_reviews/" in path


def _customer_media(item: Mapping[str, object]) -> bool:
    return bool(
        item.get("private_storage")
        or item.get("private_storage_name")
        or item.get("storage_name")
        or item.get("source_part_id")
        or item.get("message_id")
        or item.get("source_message_id")
        or str(item.get("provenance") or "") == "live_webhook"
        or str(item.get("role") or "").casefold() in _CUSTOMER_ROLES
        or _provider_media_url(item.get("url"))
        or _legacy_customer_url(item.get("url"))
        or _legacy_customer_url(item.get("local_url"))
    )


def _preview_url(message_id: object, source_part_id: object) -> str:
    try:
        message_id = int(message_id)
    except (TypeError, ValueError):
        return ""
    source_part_id = str(source_part_id or "").strip()
    if message_id <= 0 or not source_part_id:
        return ""
    try:
        relative = reverse(
            "management_bot_private_media_preview",
            args=[message_id, source_part_id],
            urlconf="management.urls",
        )
    except Exception:
        return ""
    from management.services.ig_alerts import management_base_url

    return f"{management_base_url()}{relative}"


def _trusted_preview_url(value: object) -> str:
    try:
        parsed = urlsplit(str(value or ""))
    except ValueError:
        return ""
    from management.services.ig_alerts import management_base_url

    base = urlsplit(management_base_url())
    if (
        parsed.scheme != "https"
        or base.scheme != "https"
        or parsed.scheme != base.scheme
        or parsed.netloc != base.netloc
        or parsed.query
        or parsed.fragment
        or not _PRIVATE_PREVIEW_PATH_RE.fullmatch(parsed.path or "")
    ):
        return ""
    return parsed.geturl()


def project_manager_media(media) -> list[dict]:
    """Return redacted display metadata with an authorized private-preview link.

    No signed CDN URL, storage path, raw bytes, digest, or Telegram upload
    handle survives. A preview URL only identifies a guarded application route;
    the route independently validates operator permission, ownership, erasure,
    active state, and current digest.
    """
    projected = []
    for raw in list(media or [])[:8]:
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        if item.get("availability") in {"private_preview", "unavailable"}:
            preserved = {
                "role": str(item.get("role") or "customer_media")[:64],
                "availability": str(item["availability"]),
            }
            preview_url = _trusted_preview_url(item.get("preview_url"))
            if item.get("availability") == "private_preview" and preview_url:
                preserved["preview_url"] = preview_url
            elif item.get("availability") == "private_preview":
                preserved["availability"] = "unavailable"
            projected.append(preserved)
            continue
        if _customer_media(item):
            preview_url = _preview_url(
                item.get("message_id") or item.get("source_message_id"),
                item.get("source_part_id"),
            )
            projected.append({
                "role": str(item.get("role") or "customer_media")[:64],
                "availability": "private_preview" if preview_url else "unavailable",
                **({"preview_url": preview_url} if preview_url else {}),
            })
            continue
        # Preserve non-customer product/operational media. Customer/provider
        # sources were classified above and never reach this branch.
        safe = {
            key: str(item.get(key) or "")[:300]
            for key in _OUTWARD_MEDIA_FIELDS
            if item.get(key) not in (None, "")
        }
        if safe:
            projected.append(safe)
    return projected


def _redact_provider_urls(value, *, forbidden_urls=frozenset()):
    if isinstance(value, str):
        def anchor_replacement(match):
            url = match.group("url")
            return "[приватний файл]" if url in forbidden_urls or _provider_media_url(url) or _legacy_customer_url(url) else match.group(0)

        value = _ANCHOR_RE.sub(anchor_replacement, value)
        return _URL_RE.sub(
            lambda match: "[приватний файл]"
            if (
                match.group(0) in forbidden_urls
                or _provider_media_url(match.group(0))
                or _legacy_customer_url(match.group(0))
            )
            else match.group(0),
            value,
        )
    if isinstance(value, list):
        return [_redact_provider_urls(item, forbidden_urls=forbidden_urls) for item in value]
    if isinstance(value, Mapping):
        return {
            str(key): _redact_provider_urls(item, forbidden_urls=forbidden_urls)
            for key, item in value.items()
        }
    return value


def _safe_reply_markup(value, *, forbidden_urls=frozenset()):
    if not isinstance(value, Mapping):
        return None
    result = dict(value)
    keyboard = value.get("inline_keyboard")
    if not isinstance(keyboard, list):
        return result
    rows = []
    for row in keyboard:
        if not isinstance(row, list):
            continue
        buttons = []
        for raw_button in row:
            if not isinstance(raw_button, Mapping):
                continue
            button = dict(raw_button)
            url = button.get("url")
            if url is not None:
                url = str(url)
                try:
                    has_scheme = bool(urlsplit(url).scheme)
                except ValueError:
                    has_scheme = False
                if (
                    url in forbidden_urls
                    or _provider_media_url(url)
                    or _legacy_customer_url(url)
                    or not has_scheme
                ):
                    continue
            buttons.append(button)
        if buttons:
            rows.append(buttons)
    if not rows:
        return None
    result["inline_keyboard"] = rows
    return result


def redact_notification_payload(payload: Mapping[str, object] | None) -> dict:
    """Sanitize queued media, text, and markup without changing other alerts."""
    result = dict(payload or {})
    raw_media = result.get("media") if isinstance(result.get("media"), list) else []
    forbidden_urls = frozenset(
        str(item.get(key) or "")
        for item in raw_media
        if isinstance(item, Mapping) and _customer_media(item)
        for key in ("url", "local_url")
        if item.get(key)
    )
    if raw_media:
        result["media"] = project_manager_media(raw_media)
    result["text"] = _redact_provider_urls(
        str(result.get("text") or ""), forbidden_urls=forbidden_urls,
    )
    if isinstance(result.get("reply_markup"), Mapping):
        markup = _safe_reply_markup(
            result["reply_markup"], forbidden_urls=forbidden_urls,
        )
        if markup is None:
            result.pop("reply_markup", None)
        else:
            result["reply_markup"] = markup
    previews = [
        str(item.get("preview_url") or "")
        for item in result.get("media") or []
        if isinstance(item, Mapping) and item.get("preview_url")
    ]
    if previews:
        links = "\n".join(f"Приватний перегляд: {url}" for url in dict.fromkeys(previews))
        if links not in result["text"]:
            result["text"] = (result["text"].rstrip() + "\n" + links).strip()
        markup = result.get("reply_markup")
        if not isinstance(markup, Mapping):
            markup = {"inline_keyboard": []}
        keyboard = list(markup.get("inline_keyboard") or [])
        existing_preview_urls = {
            _trusted_preview_url(button.get("url"))
            for row in keyboard if isinstance(row, list)
            for button in row if isinstance(button, Mapping)
            if _trusted_preview_url(button.get("url"))
        }
        for url in dict.fromkeys(previews):
            if url in existing_preview_urls:
                continue
            keyboard.append([{"text": "Приватний перегляд", "url": url}])
        result["reply_markup"] = {**markup, "inline_keyboard": keyboard}
    return result


def expire_failed_capture_urls(media, *, now, legacy_delete_after=None) -> list[dict]:
    """Remove expired provider URLs while retaining the part's durable outcome.

    B01.4 writes ``url_metadata_delete_after`` for a failed/expired capture;
    its periodic cleanup caller belongs to the integration step. This pure
    helper deliberately keeps source-part identity, state, and error reason so
    coverage never loses an unreadable part merely because its signed URL aged
    out.
    """
    result = []
    terminal = {"unavailable", "failed", "expired", "blocked", "metadata_only"}
    for raw in media or ():
        if not isinstance(raw, Mapping):
            result.append(raw)
            continue
        item = dict(raw)
        deadline = item.get("url_metadata_delete_after")
        if deadline in (None, ""):
            deadline = legacy_delete_after
        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            except ValueError:
                deadline = None
        if isinstance(deadline, datetime) and timezone.is_naive(deadline):
            deadline = timezone.make_aware(deadline, timezone.get_default_timezone())
        if (
            str(item.get("status") or "").casefold() in terminal
            and isinstance(deadline, datetime)
            and deadline <= now
        ):
            item.pop("url", None)
            item["url_metadata_expired"] = True
        result.append(item)
    return result
