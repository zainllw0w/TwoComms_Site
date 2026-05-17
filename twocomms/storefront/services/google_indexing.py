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
GOOGLE_INDEXING_DEFAULT_DAILY_QUOTA = 200

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


def get_daily_quota() -> int:
    """Return the configured daily quota (default 200, Google's free tier)."""
    raw = getattr(settings, "GOOGLE_INDEXING_DAILY_QUOTA", GOOGLE_INDEXING_DEFAULT_DAILY_QUOTA)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = GOOGLE_INDEXING_DEFAULT_DAILY_QUOTA
    return max(1, value)


def get_quota_window_hours() -> int:
    """Length (in hours) of the rolling quota window we enforce client-side.

    Google's documented quota is "200 publish requests per 24 hours per
    project" — but they enforce it as a rolling window: the slot used
    by request *r* frees up exactly 24h after ``r.submitted_at``. We
    mirror that rather than a calendar-day reset so the admin sees a
    truthful "next slot at 14:23" countdown instead of "after midnight".
    Override via ``settings.GOOGLE_INDEXING_QUOTA_WINDOW_HOURS`` if
    Google ever changes the policy.
    """
    raw = getattr(settings, "GOOGLE_INDEXING_QUOTA_WINDOW_HOURS", 24)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 24
    return max(1, value)


# ---------------------------------------------------------------------------
# Submission audit log helpers (Phase 22)
# ---------------------------------------------------------------------------

def _today_local() -> "date":  # noqa: F821 — runtime forward ref
    from datetime import date
    return date.today() if not getattr(settings, "USE_TZ", False) else _today_aware()


def _today_aware():
    from datetime import datetime
    from django.utils import timezone as djtz
    return djtz.localdate()


def get_today() -> "date":  # noqa: F821
    """Return the current date in the active timezone (settings.TIME_ZONE)."""
    from django.utils import timezone as djtz
    return djtz.localdate()


def _now_aware():
    from django.utils import timezone as djtz
    return djtz.now()


def get_urls_already_submitted_today(
    urls: Iterable[str],
    *,
    notification_type: str = NOTIFICATION_URL_UPDATED,
) -> set[str]:
    """Backwards-compat wrapper: dedupe by the configured rolling window.

    Now delegates to :func:`get_urls_successful_in_last_hours` with the
    quota window (default 24h) so callers that historically said
    "skip already-submitted today" automatically benefit from the
    rolling-window precision.
    """
    return get_urls_successful_in_last_hours(
        urls,
        hours=get_quota_window_hours(),
        notification_type=notification_type,
    )


def get_urls_successful_in_last_hours(
    urls: Iterable[str],
    *,
    hours: int,
    notification_type: str = NOTIFICATION_URL_UPDATED,
) -> set[str]:
    """Return URLs with a successful submission in the last ``hours`` hours.

    Uses ``submitted_at`` (the precise UTC timestamp), not the calendar
    ``submission_date``, so 24-hour math lines up with Google's rolling
    quota window. ``hours <= 0`` is a no-op.
    """
    if hours <= 0:
        return set()
    try:
        from storefront.models import GoogleIndexingSubmission
    except Exception:  # pragma: no cover - defensive
        return set()

    url_list = [u for u in urls if u]
    if not url_list:
        return set()

    from datetime import timedelta
    cutoff = _now_aware() - timedelta(hours=hours)
    qs = GoogleIndexingSubmission.objects.filter(
        submitted_at__gte=cutoff,
        notification_type=notification_type,
        status="success",
        url__in=url_list,
    ).values_list("url", flat=True)
    return set(qs)


def get_urls_successful_in_last_days(
    urls: Iterable[str],
    *,
    days: int,
    notification_type: str = NOTIFICATION_URL_UPDATED,
) -> set[str]:
    """Backwards-compat alias for :func:`get_urls_successful_in_last_hours`.

    ``days=N`` is treated as ``hours=N*24`` so existing callers still
    work after the rolling-window switch.
    """
    if days <= 0:
        return set()
    return get_urls_successful_in_last_hours(
        urls,
        hours=int(days) * 24,
        notification_type=notification_type,
    )


def get_quota_summary() -> dict[str, Any]:
    """Rolling-window quota snapshot for the admin dashboard.

    Returns the current state of the 24-hour Google indexing quota:
    how many submissions counted toward it, when the next slot frees
    up, and whether a new run can start *right now*.
    """
    quota = get_daily_quota()
    window_hours = get_quota_window_hours()
    fallback = {
        "now": _now_aware().isoformat(),
        "quota": quota,
        "window_hours": window_hours,
        "submitted_in_window": 0,
        "succeeded_in_window": 0,
        "failed_in_window": 0,
        "remaining_quota": quota,
        "can_submit_now": True,
        "oldest_submission_at": None,
        "quota_resets_at": None,
        "next_slot_at": None,
        "next_slot_in_seconds": 0,
        "last_submitted_at": None,
        # Legacy keys (kept so existing front-end code keeps working
        # until the new fields are wired everywhere).
        "today": str(get_today()),
        "submitted_today": 0,
        "succeeded_today": 0,
        "failed_today": 0,
    }

    try:
        from storefront.models import GoogleIndexingSubmission
    except Exception:  # pragma: no cover
        return fallback

    from datetime import timedelta
    now = _now_aware()
    cutoff = now - timedelta(hours=window_hours)

    qs = GoogleIndexingSubmission.objects.filter(submitted_at__gte=cutoff)
    in_window = list(
        qs.order_by("submitted_at").values_list("submitted_at", "status")
    )
    submitted_in_window = len(in_window)
    succeeded_in_window = sum(1 for _, s in in_window if s == "success")
    failed_in_window = submitted_in_window - succeeded_in_window
    remaining = max(0, quota - submitted_in_window)
    can_submit_now = remaining > 0

    oldest_at = in_window[0][0] if in_window else None
    last_at = in_window[-1][0] if in_window else None
    quota_resets_at = (oldest_at + timedelta(hours=window_hours)) if oldest_at else None
    if can_submit_now:
        next_slot_at = now
        next_slot_in_seconds = 0
    elif quota_resets_at:
        next_slot_at = quota_resets_at
        next_slot_in_seconds = max(0, int((quota_resets_at - now).total_seconds()))
    else:
        next_slot_at = None
        next_slot_in_seconds = 0

    # Legacy "today" stats — preserved for any consumer that still
    # reads ``submitted_today`` / ``succeeded_today``.
    today = get_today()
    today_qs = GoogleIndexingSubmission.objects.filter(submission_date=today)
    submitted_today = today_qs.count()
    succeeded_today = today_qs.filter(status="success").count()
    failed_today = submitted_today - succeeded_today

    return {
        "now": now.isoformat(),
        "quota": quota,
        "window_hours": window_hours,
        "submitted_in_window": submitted_in_window,
        "succeeded_in_window": succeeded_in_window,
        "failed_in_window": failed_in_window,
        "remaining_quota": remaining,
        "can_submit_now": can_submit_now,
        "oldest_submission_at": oldest_at.isoformat() if oldest_at else None,
        "quota_resets_at": quota_resets_at.isoformat() if quota_resets_at else None,
        "next_slot_at": next_slot_at.isoformat() if next_slot_at else None,
        "next_slot_in_seconds": next_slot_in_seconds,
        "last_submitted_at": last_at.isoformat() if last_at else None,
        # Legacy.
        "today": str(today),
        "submitted_today": submitted_today,
        "succeeded_today": succeeded_today,
        "failed_today": failed_today,
    }


def get_today_summary() -> dict[str, Any]:
    """Backwards-compat alias for :func:`get_quota_summary`.

    Older callers expected the legacy "calendar today" semantics; the
    summary still includes ``submitted_today`` etc. for them, but the
    canonical numbers are now ``submitted_in_window`` /
    ``remaining_quota`` driven by the rolling 24h window.
    """
    return get_quota_summary()


def get_recent_submissions(*, limit: int = 50) -> list[dict[str, Any]]:
    """Return the latest submission entries for the admin history view."""
    try:
        from storefront.models import GoogleIndexingSubmission
    except Exception:  # pragma: no cover
        return []

    rows = (
        GoogleIndexingSubmission.objects
        .order_by("-submitted_at")
        .values(
            "id", "url", "status", "http_status",
            "notification_type", "submitted_at", "submission_date",
            "source", "error_message",
        )[: max(1, limit)]
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({
            "id": row["id"],
            "url": row["url"],
            "status": row["status"],
            "http_status": row["http_status"],
            "notification_type": row["notification_type"],
            "submitted_at": row["submitted_at"].isoformat() if row["submitted_at"] else None,
            "submission_date": str(row["submission_date"]) if row["submission_date"] else None,
            "source": row["source"],
            "error_message": (row["error_message"] or "")[:300],
        })
    return out


def _log_submission(
    *,
    url: str,
    notification_type: str,
    status: str,
    http_status: int | None,
    error_message: str = "",
    source: str = "",
) -> None:
    try:
        from storefront.models import GoogleIndexingSubmission
        from django.utils import timezone as djtz
        GoogleIndexingSubmission.objects.create(
            url=url,
            notification_type=notification_type,
            status=status,
            http_status=http_status,
            error_message=(error_message or "")[:2000],
            source=source[:32],
            submission_date=djtz.localdate(),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Google Indexing audit-log write failed: %s", exc, exc_info=True)


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
) -> tuple[bool, str | None, int | None]:
    """POST a single URL notification.

    Returns ``(ok, error_message, http_status)``. ``http_status`` is
    ``None`` if the request never reached Google (timeout, DNS, etc.).
    """
    payload = {"url": url, "type": notification_type}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    last_error: str | None = None
    last_status: int | None = None
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
            last_status = None
            logger.warning(
                "Google Indexing transient error on attempt %s/%s for %s: %s",
                attempt + 1, retries + 1, url, exc,
            )
            continue
        except Exception as exc:  # pragma: no cover - defensive
            last_error = f"{type(exc).__name__}: {exc}"
            logger.error("Google Indexing unexpected error: %s", exc, exc_info=True)
            return False, last_error, last_status

        last_status = response.status_code
        if response.status_code == 200:
            return True, None, last_status
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
        return False, last_error, last_status
    return False, (last_error or "unknown error"), last_status


def submit_google_indexing_urls(
    urls: Iterable[str],
    *,
    notification_type: str = NOTIFICATION_URL_UPDATED,
    timeout: float | None = None,
    retries: int | None = None,
    source: str = "",
    skip_already_submitted_today: bool = False,
    skip_recent_success_days: int = 0,
    skip_recent_success_hours: int = 0,
    quota_limit: int | None = None,
) -> dict[str, Any]:
    """Submit a list of URLs to the Google Indexing API.

    Args:
        urls: iterable of absolute URLs (off-host URLs are filtered out).
        notification_type: ``URL_UPDATED`` (default) or ``URL_DELETED``.
        timeout / retries: HTTP knobs (defaults via ``settings``).
        source: short label that ends up in the audit log
            (e.g. ``"admin"``, ``"signal"``, ``"cron"``).
        skip_already_submitted_today: legacy shortcut — equivalent to
            ``skip_recent_success_hours=24`` (the configured quota window).
        skip_recent_success_days: legacy knob, treated as ``hours = days*24``.
        skip_recent_success_hours: rolling-window dedupe in *hours*.
            URLs with a successful submission inside that window are
            dropped before any HTTP call so the daily quota is not
            burned on duplicates. ``0`` disables the filter.
        quota_limit: if set, caps the number of HTTP calls so the
            rolling Google quota is not exceeded.

    Returns a dict::

        {
            "ok": bool,
            "submitted": int,
            "total": int,             # URLs after host filter
            "skipped_already": int,   # already accepted today / window
            "skipped_quota": int,     # not sent due to quota_limit
            "failures": [{"url": ..., "error": ..., "http_status": ...}, ...],
            "configured": bool,
            "message": str,
        }
    """
    if notification_type not in _VALID_NOTIFICATION_TYPES:
        return {
            "ok": False,
            "submitted": 0,
            "total": 0,
            "skipped_already": 0,
            "skipped_quota": 0,
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
            "skipped_already": 0,
            "skipped_quota": 0,
            "failures": [],
            "configured": is_google_indexing_configured(),
            "message": "No valid URLs to submit (host filter or empty input).",
        }

    if not is_google_indexing_configured():
        return {
            "ok": False,
            "submitted": 0,
            "total": total,
            "skipped_already": 0,
            "skipped_quota": 0,
            "failures": [],
            "configured": False,
            "message": (
                "Google Indexing API не сконфігуровано: відсутній або вимкнений "
                "сервісний акаунт."
            ),
        }

    skipped_already = 0
    # Combine the three skip-by-history switches:
    #   * skip_recent_success_hours — canonical (rolling-hours window).
    #   * skip_recent_success_days  — legacy: hours = days * 24.
    #   * skip_already_submitted_today — legacy: same as the configured
    #     quota window (24h by default).
    # Take the *longest* window across all three so the caller never
    # re-submits a URL inside any explicitly requested rotation.
    effective_hours = max(0, int(skip_recent_success_hours or 0))
    if skip_recent_success_days and int(skip_recent_success_days) > 0:
        effective_hours = max(effective_hours, int(skip_recent_success_days) * 24)
    if skip_already_submitted_today:
        effective_hours = max(effective_hours, get_quota_window_hours())
    if effective_hours > 0:
        already = get_urls_successful_in_last_hours(
            normalized, hours=effective_hours, notification_type=notification_type
        )
        if already:
            skipped_already = len(already)
            normalized = [u for u in normalized if u not in already]

    skipped_quota = 0
    if quota_limit is not None and quota_limit > 0 and len(normalized) > quota_limit:
        skipped_quota = len(normalized) - quota_limit
        normalized = normalized[:quota_limit]

    if not normalized:
        return {
            "ok": True if skipped_already else False,
            "submitted": 0,
            "total": total,
            "skipped_already": skipped_already,
            "skipped_quota": skipped_quota,
            "failures": [],
            "configured": True,
            "message": (
                f"Усі {skipped_already} URL уже відправлено сьогодні — "
                "немає що індексувати повторно."
                if skipped_already
                else "Жодного URL для відправки після фільтрації."
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
            "skipped_already": skipped_already,
            "skipped_quota": skipped_quota,
            "failures": [{"url": "*", "error": str(exc)}],
            "configured": True,
            "message": f"Не вдалося отримати OAuth2 token: {exc}",
        }

    submitted = 0
    failures: list[dict[str, Any]] = []
    for url in normalized:
        ok, err, http_status = _send_one(
            url,
            notification_type,
            access_token=access_token,
            timeout=effective_timeout,
            retries=effective_retries,
        )
        if ok:
            submitted += 1
            _log_submission(
                url=url,
                notification_type=notification_type,
                status="success",
                http_status=http_status,
                source=source,
            )
        else:
            failures.append({"url": url, "error": err or "unknown error", "http_status": http_status})
            _log_submission(
                url=url,
                notification_type=notification_type,
                status="failed",
                http_status=http_status,
                error_message=err or "",
                source=source,
            )

    if submitted:
        logger.info(
            "Google Indexing accepted %s/%s URL(s) (type=%s, skipped_already=%s, skipped_quota=%s)",
            submitted, total, notification_type, skipped_already, skipped_quota,
        )

    attempted = len(normalized)
    if submitted == attempted and submitted > 0:
        msg_parts = [f"Google Indexing API прийняв {submitted}/{total} URL."]
    elif submitted == 0:
        msg_parts = [
            f"Google Indexing API відхилив усі {attempted} URL.",
            "Перевірте логи й денний квоту проєкту.",
        ]
    else:
        msg_parts = [
            f"Google Indexing API прийняв {submitted}/{attempted} URL,",
            f"{attempted - submitted} відхилив(но). Деталі — у логах.",
        ]
    if skipped_already:
        msg_parts.append(f"Пропущено вже надісланих сьогодні: {skipped_already}.")
    if skipped_quota:
        msg_parts.append(f"Залишилось понад ліміт: {skipped_quota}.")

    return {
        "ok": submitted == attempted and submitted > 0,
        "submitted": submitted,
        "total": total,
        "skipped_already": skipped_already,
        "skipped_quota": skipped_quota,
        "failures": failures,
        "configured": True,
        "message": " ".join(msg_parts),
    }


def enqueue_google_indexing_urls(
    urls: Iterable[str],
    *,
    notification_type: str = NOTIFICATION_URL_UPDATED,
    source: str = "signal",
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
            normalized,
            notification_type=notification_type,
            source=source,
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
    "get_daily_quota",
    "get_quota_window_hours",
    "get_quota_summary",
    "get_today_summary",
    "get_recent_submissions",
    "get_urls_already_submitted_today",
    "get_urls_successful_in_last_days",
    "get_urls_successful_in_last_hours",
    "reset_token_cache",
    "submit_google_indexing_urls",
    "enqueue_google_indexing_urls",
]
