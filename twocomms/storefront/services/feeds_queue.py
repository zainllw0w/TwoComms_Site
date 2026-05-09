"""Feeds regeneration queue (cron-driven, no broker required).

Signals mark the feeds as "dirty" by touching a flag file. A cron job runs
``manage.py regenerate_feeds_if_dirty`` every few minutes and rebuilds all
marketplace feeds if (and only if) the flag is newer than the last successful
build timestamp.

This replaces the Celery-backed debounce that was using
``.apply_async(countdown=300)``; the project's shared hosting has no broker.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


def _state_dir() -> Path:
    """Directory used to store feed-queue flag files.

    Prefers ``BASE_DIR/tmp/feeds`` (already writable and ignored by git).
    """
    base = Path(getattr(settings, "BASE_DIR", Path(__file__).resolve().parents[3]))
    target = base / "tmp" / "feeds"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _dirty_flag_path() -> Path:
    return _state_dir() / "feeds_dirty.flag"


def _last_build_path() -> Path:
    return _state_dir() / "feeds_last_build.flag"


def mark_feeds_dirty(reason: str = "") -> None:
    """Touch the dirty flag so the next cron pass picks it up.

    Safe to call many times per request — just updates mtime.
    """
    try:
        path = _dirty_flag_path()
        path.touch(exist_ok=True)
        # Bump mtime explicitly (touch on exists sometimes no-ops).
        now = time.time()
        os.utime(path, (now, now))
        if reason:
            logger.debug("feeds marked dirty: %s", reason)
    except Exception as exc:  # pragma: no cover - fs edge cases
        logger.warning("Could not mark feeds dirty: %s", exc)


def mark_feeds_clean() -> None:
    """Record that a successful rebuild finished now."""
    try:
        path = _last_build_path()
        path.touch(exist_ok=True)
        now = time.time()
        os.utime(path, (now, now))
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not mark feeds clean: %s", exc)


def are_feeds_dirty() -> bool:
    """True when dirty flag is newer than last-build flag (or build never ran)."""
    dirty = _dirty_flag_path()
    last = _last_build_path()
    if not dirty.exists():
        return False
    if not last.exists():
        return True
    try:
        return dirty.stat().st_mtime > last.stat().st_mtime
    except Exception:  # pragma: no cover
        return True


def dirty_since_seconds() -> float | None:
    """How long (in seconds) feeds have been dirty. None if not dirty."""
    dirty = _dirty_flag_path()
    if not dirty.exists():
        return None
    try:
        return max(0.0, time.time() - dirty.stat().st_mtime)
    except Exception:  # pragma: no cover
        return None
