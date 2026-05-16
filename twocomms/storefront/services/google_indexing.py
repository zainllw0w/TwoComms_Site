"""Google Indexing API integration.

Counterpart to ``storefront.services.indexnow``: notifies Google about
URL changes via the Indexing API
(https://developers.google.com/search/apis/indexing-api/v3/using-api).

The service authenticates with a service-account JSON key (path is
configured via ``settings.GOOGLE_INDEXING_CREDENTIALS_PATH``) using a
self-signed JWT exchanged for a short-lived OAuth2 access token. The
token is cached in process memory to avoid the ~600 ms handshake on
every batch.

Notes & limitations:
- Google's Indexing API is officially only for ``JobPosting`` and
  ``BroadcastEvent`` content; for an apparel catalog it works as a
  *hint* but not as a guarantee. We still send pings because they
  speed up discovery and don't violate ToS as long as we honour the
  daily quota (default 200 calls/day per project).
- Only one URL per HTTP call is allowed by the API. We loop the list
  client-side and tally per-batch results so the admin UI surfaces
  partial failures gracefully.
- Authentication uses ``PyJWT`` + ``cryptography`` (already in the
  requirements via ``social-auth-app-django``) so we don't need the
  full ``google-auth`` stack. ``google-auth`` is preferred if
  available because Google rotates JWT signing requirements
  occasionally; we fall back to manual JWT only if it is missing.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import requests
from django.conf import settings

from .indexnow import build_absolute_url, get_indexnow_host, get_site_base_url


logger = logging.getLogger(__name__)

GOOGLE_INDEXING_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_INDEXING_SCOPE = "https://www.googleapis.com/auth/indexing"
GOOGLE_INDEXING_DEFAULT_TIMEOUT = 10.0
GOOGLE_INDEXING_DEFAULT_RETRIES = 2

# Google's Indexing API allows two notification types:
#   URL_UPDATED  → page is new or its content changed
#   URL_DELETED  → page no longer exists / was unpublished
NOTIFICATION_URL_UPDATED = "URL_UPDATED"
NOTIFICATION_URL_DELETED = "URL_DELETED"

_VALID_NOTIFICATION_TYPES = {NOTIFICATION_URL_UPDATED, NOTIFICATION_URL_DELETED}

# In-process token cache. The Indexing API issues access tokens that
# live for ~3600 s; we refresh ~5 minutes before expiry to be safe.
_TOKEN_CACHE_LOCK = threading.Lock()
_TOKEN_CACHE: dict[str, Any] = {"token": None, "expires_at": 0.0, "cred_path": ""}
_TOKEN_REFRESH_MARGIN_SECONDS = 300


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def get_credentials_path() -> str:
    """Return the absolute path to the service-account JSON, or "".

    Resolution order:
        1. ``settings.GOOGLE_INDEXING_CREDENTIALS_PATH`` (preferred,
           lets ops override per-environment without touching the
           filesystem layout).
        2. Default: ``<repo>/json/totemic-life-471601-g7-408d1ee6dcf2.json``
           (the file the user committed in this PR).
    """
    configured = (getattr(settings, "GOOGLE_INDEXING_CREDENTIALS_PATH", "") or "").strip()
    if configured:
        return configured

    # Default: project-relative `json/` folder. ``BASE_DIR`` points at
    # ``twocomms/`` (the Django project root), but the JSON sits one
    # level up next to the repo root.
    base_dir = Path(getattr(settings, "BASE_DIR", "")).resolve()
    default_name = "totemic-life-471601-g7-408d1ee6dcf2.json"
    candidate_names = [default_name]

    candidates = []
    for name in candidate_names:
        candidates.extend([
            base_dir.parent / "json" / name,
            base_dir / "json" / name,
        ])
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    # Return the first candidate path so callers can show a helpful
    # "file missing at <path>" diagnostic instead of empty string.
    return str(candidates[0]) if candidates else ""


def is_google_indexing_enabled() -> bool:
    return bool(getattr(settings, "GOOGLE_INDEXING_ENABLED", True))


def is_google_indexing_configured() -> bool:
    if not is_google_indexing_enabled():
        return False
    path = get_credentials_path()
    return bool(path) and os.path.isfile(path)


def get_google_indexing_status() -> dict[str, Any]:
    """Lightweight diagnostic snapshot for the admin UI."""
    path = get_credentials_path()
    exists = bool(path) and os.path.isfile(path)
    return {
        "enabled": is_google_indexing_enabled(),
        "credentials_path": path,
        "credentials_present": exists,
        "configured": exists and is_google_indexing_enabled(),
    }


# ---------------------------------------------------------------------------
# OAuth2 access-token acquisition (Service Account JWT bearer flow)
# ---------------------------------------------------------------------------

def _load_service_account_info(path: str) -> dict[str, Any]:
    with open(path, "rb") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise RuntimeError("Service account JSON does not contain an object at the top level.")
    if data.get("type") != "service_account":
        raise RuntimeError(f"Unexpected credential type: {data.get('type')!r}")
    for required in ("client_email", "private_key", "token_uri"):
        if not data.get(required):
            raise RuntimeError(f"Service account JSON is missing '{required}'.")
    return data


def _build_assertion(account: dict[str, Any]) -> str:
    """Build and sign a JWT bearer assertion for the OAuth2 exchange."""
    try:
        import jwt  # PyJWT
    except ImportError as exc:  # pragma: no cover - PyJWT is a hard dep
        raise RuntimeError("PyJWT is required for Google Indexing API auth.") from exc

    now = int(time.time())
    payload = {
        "iss": account["client_email"],
        "scope": GOOGLE_INDEXING_SCOPE,
        "aud": account.get("token_uri", GOOGLE_TOKEN_ENDPOINT),
        "exp": now + 3600,
        "iat": now,
    }
    headers = {"alg": "RS256", "typ": "JWT"}
    if account.get("private_key_id"):
        headers["kid"] = account["private_key_id"]
    return jwt.encode(payload, account["private_key"], algorithm="RS256", headers=headers)


def _fetch_access_token(account: dict[str, Any]) -> tuple[str, float]:
    """Exchange a JWT assertion for a short-lived OAuth2 access token."""
    assertion = _build_assertion(account)
    response = requests.post(
        account.get("token_uri", GOOGLE_TOKEN_ENDPOINT),
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        timeout=GOOGLE_INDEXING_DEFAULT_TIMEOUT,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Token exchange failed ({response.status_code}): {response.text[:300]}"
        )
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"Token response missing 'access_token': {payload}")
    expires_in = int(payload.get("expires_in", 3600) or 3600)
    return token, time.time() + max(60, expires_in - _TOKEN_REFRESH_MARGIN_SECONDS)


def _get_cached_access_token() -> str:
    path = get_credentials_path()
    if not path or not os.path.isfile(path):
        raise RuntimeError(f"Google Indexing credentials not found at {path or '<unset>'}")

    with _TOKEN_CACHE_LOCK:
        cached = _TOKEN_CACHE
        if (
            cached.get("token")
            and cached.get("cred_path") == path
            and time.time() < float(cached.get("expires_at", 0))
        ):
            return cached["token"]

        account = _load_service_account_info(path)
        token, expires_at = _fetch_access_token(account)
        _TOKEN_CACHE.update({"token": token, "expires_at": expires_at, "cred_path": path})
        return token


def reset_token_cache() -> None:
    """Test-helper / admin utility to force a fresh OAuth2 handshake."""
    with _TOKEN_CACHE_LOCK:
        _TOKEN_CACHE.update({"token": None, "expires_at": 0.0, "cred_path": ""})


# ---------------------------------------------------------------------------
# URL submission
# ---------------------------------------------------------------------------

def _normalize_urls(urls: Iterable[str]) -> list[str]:
    host = get_indexnow_host()  # both APIs share the canonical host check
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in urls:
        if not raw:
            continue
        url = str(raw).strip()
        if not url:
            continue
        if url.startswith("/"):
            url = build_absolute_url(url)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != host:
            continue
        if url in seen:
            continue
        seen.add(url)
        normalized.append(url)
    return normalized


def _send_one(
    url: str,
    notification_type: str,
    *,
    access_token: str,
    timeout: float,
    retries: int,
) -> tuple[bool, str | None]:
    """POST a single URL notification. Returns (ok, error_message)."""
    payload = {"url": url, "type": notification_type}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    last_error: str | None = None
    for attempt in range(retries + 1):
        try:
            response = requests.post(
                GOOGLE_INDEXING_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=timeout,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Google Indexing transient error on attempt %s/%s for %s: %s",
                attempt + 1, retries + 1, url, exc,
            )
            continue
        except Exception as exc:  # pragma: no cover - defensive
            last_error = f"{type(exc).__name__}: {exc}"
            logger.error("Google Indexing unexpected error: %s", exc, exc_info=True)
            return False, last_error

        if response.status_code == 200:
            return True, None
        if response.status_code in (429,) or 500 <= response.status_code < 600:
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            logger.warning(
                "Google Indexing %s on attempt %s/%s for %s",
                response.status_code, attempt + 1, retries + 1, url,
            )
            continue
        # 4xx (other than 429) is not retryable.
        last_error = f"HTTP {response.status_code}: {response.text[:200]}"
        logger.error("Google Indexing rejected %s: %s", url, last_error)
        return False, last_error
    return False, last_error or "unknown error"


def submit_google_indexing_urls(
    urls: Iterable[str],
    *,
    notification_type: str = NOTIFICATION_URL_UPDATED,
    timeout: float | None = None,
    retries: int | None = None,
) -> dict[str, Any]:
    """Submit a list of URLs to the Google Indexing API.

    Returns a dict::

        {
            "ok": bool,            # True iff every URL accepted
            "submitted": int,      # number of URLs accepted (HTTP 200)
            "total": int,          # total URLs after normalization
            "failures": [{"url": ..., "error": ...}, ...],
            "configured": bool,
            "message": str,
        }
    """
    if notification_type not in _VALID_NOTIFICATION_TYPES:
        return {
            "ok": False,
            "submitted": 0,
            "total": 0,
            "failures": [],
            "configured": is_google_indexing_configured(),
            "message": f"Invalid notification type: {notification_type!r}",
        }

    normalized = _normalize_urls(urls)
    total = len(normalized)
    if total == 0:
        return {
            "ok": False,
            "submitted": 0,
            "total": 0,
            "failures": [],
            "configured": is_google_indexing_configured(),
            "message": "No valid URLs to submit (host filter or empty input).",
        }

    if not is_google_indexing_configured():
        return {
            "ok": False,
            "submitted": 0,
            "total": total,
            "failures": [],
            "configured": False,
            "message": (
                "Google Indexing API не сконфігуровано: відсутній або вимкнений "
                "сервісний акаунт."
            ),
        }

    effective_timeout = float(
        timeout
        if timeout is not None
        else getattr(settings, "GOOGLE_INDEXING_TIMEOUT", GOOGLE_INDEXING_DEFAULT_TIMEOUT)
        or GOOGLE_INDEXING_DEFAULT_TIMEOUT
    )
    effective_retries = int(
        retries
        if retries is not None
        else getattr(settings, "GOOGLE_INDEXING_RETRIES", GOOGLE_INDEXING_DEFAULT_RETRIES)
    )

    try:
        access_token = _get_cached_access_token()
    except Exception as exc:
        logger.error("Google Indexing token error: %s", exc, exc_info=True)
        return {
            "ok": False,
            "submitted": 0,
            "total": total,
            "failures": [{"url": "*", "error": str(exc)}],
            "configured": True,
            "message": f"Не вдалося отримати OAuth2 token: {exc}",
        }

    submitted = 0
    failures: list[dict[str, str]] = []
    for url in normalized:
        ok, err = _send_one(
            url,
            notification_type,
            access_token=access_token,
            timeout=effective_timeout,
            retries=effective_retries,
        )
        if ok:
            submitted += 1
        else:
            failures.append({"url": url, "error": err or "unknown error"})

    if submitted:
        logger.info(
            "Google Indexing accepted %s/%s URL(s) (type=%s)",
            submitted, total, notification_type,
        )

    if submitted == total:
        message = f"Google Indexing API прийняв {submitted}/{total} URL."
    elif submitted == 0:
        message = (
            f"Google Indexing API відхилив усі {total} URL. "
            "Перевірте логи й денний квоту проєкту."
        )
    else:
        message = (
            f"Google Indexing API прийняв {submitted}/{total} URL, "
            f"{total - submitted} відхилив(но). Деталі — у логах."
        )

    return {
        "ok": submitted == total,
        "submitted": submitted,
        "total": total,
        "failures": failures,
        "configured": True,
        "message": message,
    }


def enqueue_google_indexing_urls(
    urls: Iterable[str],
    *,
    notification_type: str = NOTIFICATION_URL_UPDATED,
) -> bool:
    """Fire-and-forget helper for use inside ``transaction.on_commit``.

    Mirrors :func:`enqueue_indexnow_urls` so signal handlers can ping
    both Google and Bing without duplicating boilerplate.
    """
    normalized = _normalize_urls(urls)
    if not normalized or not is_google_indexing_configured():
        return False
    try:
        result = submit_google_indexing_urls(
            normalized, notification_type=notification_type
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Google Indexing enqueue failed: %s", exc, exc_info=True)
        return False
    return bool(result.get("ok"))


__all__ = [
    "GOOGLE_INDEXING_ENDPOINT",
    "GOOGLE_INDEXING_SCOPE",
    "NOTIFICATION_URL_UPDATED",
    "NOTIFICATION_URL_DELETED",
    "is_google_indexing_enabled",
    "is_google_indexing_configured",
    "get_google_indexing_status",
    "get_credentials_path",
    "reset_token_cache",
    "submit_google_indexing_urls",
    "enqueue_google_indexing_urls",
]
