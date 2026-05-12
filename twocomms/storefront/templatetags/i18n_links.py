"""Phase 17a — i18n URL helpers.

Tags
----
``{% language_alternates as ctx %}``
    Returns ``{"uk": <url>, "ru": <url>, "en": <url>, "x_default": <url>}``
    where each value is an absolute URL pointing at the current
    ``request.path`` rewritten for the target language. The default
    language (Ukrainian) has no URL prefix; others use ``/<code>/``.

``{% og_locale_for_lang code %}``
    Renders the OG-style locale string ("uk_UA"/"ru_RU"/"en_US").

``{% language_switch_links as ctx %}``
    Same payload as ``language_alternates`` but with native language
    labels suitable for the footer language picker.
"""

from __future__ import annotations

from typing import Dict, Iterable

from django import template
from django.conf import settings
from django.urls import translate_url

register = template.Library()


_DEFAULT_LANG = "uk"
_SUPPORTED = ("uk", "ru", "en")

_NATIVE_LABELS = {
    "uk": "Українська",
    "ru": "Русский",
    "en": "English",
}
_SHORT_LABELS = {
    "uk": "UA",
    "ru": "RU",
    "en": "EN",
}
_FLAGS = {
    "uk": "🇺🇦",
    "ru": "🌐",  # neutral globe (no flag rendering for RU per political stance)
    "en": "🇬🇧",
}


def _site_base() -> str:
    return (getattr(settings, "SITE_BASE_URL", "") or "https://twocomms.shop").rstrip("/")


def _absolute(path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    if not path.startswith("/"):
        path = "/" + path
    return _site_base() + path


def _split_path_qs(full_path: str) -> tuple[str, str]:
    """Split ``request.get_full_path()`` into ``(path, "?qs")``.

    Returned query string keeps the leading ``?`` if present, so callers
    can concatenate without further branching. We can't rely on
    ``request.path`` + ``request.META["QUERY_STRING"]`` because callers
    sometimes pass synthetic paths during testing; splitting the value
    Django itself produced is more robust.
    """

    if "?" in full_path:
        path, qs = full_path.split("?", 1)
        return path, "?" + qs
    return full_path, ""


def _path_for_language(request, lang_code: str) -> str:
    """Translate the current request path into the target language prefix.

    SEO v1.0 Phase 1 (2026-05-12) — explicit query-string preservation.
    The old implementation deferred entirely to ``django.urls.translate_url``,
    which silently drops query strings for URL patterns outside
    ``i18n_patterns()`` (e.g. ``/catalog/?page=2``) — that bug created
    258 reciprocal-hreflang errors in the Ahrefs CSV from 2026-05-11
    (cf. ``docs/seo/2026-05-11-deep-seo-audit-and-keyword-research.md``,
    finding LLL + B18). We now split the query string off, translate
    only the path component, then re-append the query string verbatim
    so paginated and filtered URLs keep self-referential alternates.
    """

    if request is None:
        return "/" if lang_code == _DEFAULT_LANG else f"/{lang_code}/"
    try:
        full = request.get_full_path()
    except Exception:
        full = "/"
    path_only, qs = _split_path_qs(full)
    try:
        translated_path = translate_url(path_only, lang_code)
    except Exception:
        translated_path = path_only
    return translated_path + qs


@register.simple_tag(takes_context=True)
def language_alternates(context) -> Dict[str, str]:
    """Return canonical-language alternates for the current request.

    SEO v1.0 Phase 1 (2026-05-12) — under Path A (RU/EN un-translated and
    marked ``noindex``) the storefront effectively behaves as a
    single-language UA site. We still expose all three URLs so the
    footer language switcher keeps working, but ``x_default`` mirrors
    the UA URL (a single-language site treats UA as the universal
    fallback). ``base.html`` only emits ``hreflang="uk"`` +
    ``hreflang="x-default"`` while on the UA render — RU/EN renders are
    ``noindex`` so hreflang from those pages would be ignored anyway.
    """

    request = context.get("request")
    out: Dict[str, str] = {}
    for code in _SUPPORTED:
        out[code] = _absolute(_path_for_language(request, code))
    out["x_default"] = out[_DEFAULT_LANG]
    return out


@register.simple_tag(takes_context=True)
def language_switch_links(context) -> list[dict]:
    request = context.get("request")
    current = getattr(request, "LANGUAGE_CODE", _DEFAULT_LANG) if request else _DEFAULT_LANG
    items = []
    for code in _SUPPORTED:
        items.append(
            {
                "code": code,
                "label": _NATIVE_LABELS.get(code, code.upper()),
                "short": _SHORT_LABELS.get(code, code.upper()),
                "flag": _FLAGS.get(code, ""),
                "url": _path_for_language(request, code),
                "is_current": (code == current),
            }
        )
    return items


@register.simple_tag
def og_locale_for_lang(code: str | None) -> str:
    mapping = getattr(settings, "LANGUAGE_OG_LOCALE", {})
    return mapping.get((code or _DEFAULT_LANG), "uk_UA")


@register.simple_tag(takes_context=True)
def og_locale_alternates(context) -> Dict[str, str]:
    request = context.get("request")
    current = getattr(request, "LANGUAGE_CODE", _DEFAULT_LANG) if request else _DEFAULT_LANG
    mapping = getattr(settings, "LANGUAGE_OG_LOCALE", {})
    out: Dict[str, str] = {}
    for code in _SUPPORTED:
        if code == current:
            continue
        og = mapping.get(code)
        if og:
            out[code] = og
    return out
