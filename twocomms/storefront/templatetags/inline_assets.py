"""Phase 21 (2026-05-10) — `inline_static`.

Reads a small static asset (CSS/JS) and returns its raw content so it
can be embedded directly into the HTML response. Useful for trading
one render-blocking round-trip for a few extra HTML bytes (e.g. the
~34 KiB ``bootstrap-home-subset.css``: gzip squeezes it back to
~10 KiB, which is the same as the standalone request would have
transferred — but we save the request itself, ~360 ms on slow mobile).

Behaviour:
    * Result is cached per-process via ``lru_cache`` so the file is
      read at most once between server restarts (collectstatic bumps
      the hash so a new render path is taken automatically).
    * Search order matches Django's static-file finders:
      ``STATICFILES_DIRS`` first, then ``STATIC_ROOT``.
    * If the file cannot be found, returns an empty string (we don't
      want to crash the response over a missing optional asset; the
      regular ``<link rel="stylesheet">`` fallback still works).

Always returns ``SafeString`` so the result is not auto-escaped.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    for p in getattr(settings, "STATICFILES_DIRS", ()) or ():
        dirs.append(Path(p))
    static_root = getattr(settings, "STATIC_ROOT", None)
    if static_root:
        dirs.append(Path(static_root))
    return dirs


@lru_cache(maxsize=64)
def _read_static_file(relative_path: str) -> str:
    rel = relative_path.lstrip("/")
    for base in _candidate_dirs():
        candidate = base / rel
        try:
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")
        except OSError:
            continue
    return ""


@register.simple_tag
def inline_static(relative_path: str):
    """Return the raw content of a static file, ready to embed in HTML.

    Usage in templates::

        <style>{% inline_static "css/bootstrap-home-subset.css" %}</style>

    The caller is responsible for the surrounding ``<style>`` /
    ``<script>`` tag — this keeps the helper neutral so it can also
    be used for inlining a tiny JS shim later.
    """
    return mark_safe(_read_static_file(relative_path))
