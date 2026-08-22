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
from urllib.parse import parse_qsl, urlencode

from django import template
from django.conf import settings
from django.urls import translate_url
from django.utils.translation import gettext_lazy as _

from storefront.utm_utils import TRACKING_QUERY_PARAMS

register = template.Library()


_DEFAULT_LANG = "uk"
_SUPPORTED = ("uk", "ru", "en")

# 2026-05-16 — Phase 17v. Native labels are wrapped in ``gettext_lazy`` so the
# language switcher emits Ukrainian-only ``Українська`` only on UA renders;
# the RU/EN renders fall back to translated labels (``Украинский`` /
# ``Ukrainian``). This eliminates a UA-text leak that the prod scan in
# ``_scan_prod.sh`` flagged on every /ru/ and /en/ page.
_NATIVE_LABELS = {
    "uk": _("Українська"),
    "ru": _("Русский"),
    "en": _("English"),
}
_SHORT_LABELS = {
    "uk": "UA",
    "ru": "RU",
    "en": "EN",
}
_FLAGS = {
    "uk": "🇺🇦",
    "ru": "",  # rendered as image (see _FLAG_IMAGES) per political stance
    "en": "🇬🇧",
}
# Phase 17r — image-based language icons. When set, the language switcher
# template renders ``<img>`` instead of the emoji fallback. Russian uses a
# satirical PTN icon (BrandDNA/ptn.png) per the brand's positioning toward
# the russian federation.
_FLAG_IMAGES = {
    "ru": "img/lang/ptn.png",
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
    if qs:
        query = urlencode(
            [
                (key, value)
                for key, value in parse_qsl(qs[1:], keep_blank_values=True)
                if key not in TRACKING_QUERY_PARAMS
            ],
            doseq=True,
        )
        qs = f"?{query}" if query else ""
    try:
        translated_path = translate_url(path_only, lang_code)
    except Exception:
        translated_path = path_only
    return translated_path + qs


@register.simple_tag(takes_context=True)
def language_alternates(context) -> Dict[str, str]:
    """Return canonical-language alternates for the current request.

    Standard Product pages may provide ``locale_publication``. In that case
    only locale owners with independent raw content are emitted, and an
    ineligible ``noindex`` page emits no hreflang cluster at all. Other
    routes retain the established three-language behavior.
    """

    request = context.get("request")
    # Query-based catalog/search states are UX surfaces, not independent
    # locale owners. Their canonical points at the clean listing, so emitting
    # hreflang URLs with the same query would create a contradictory cluster.
    if context.get("suppress_hreflang"):
        return {}
    publication = context.get("locale_publication")
    if publication is not None:
        if not publication.get("indexable"):
            return {}
        eligible = set(publication.get("eligible_locales") or ())
    else:
        eligible = set(_SUPPORTED)
    out: Dict[str, str] = {}
    for code in _SUPPORTED:
        if code not in eligible:
            continue
        out[code] = _absolute(_path_for_language(request, code))
    if _DEFAULT_LANG in out:
        out["x_default"] = out[_DEFAULT_LANG]
    return out


@register.simple_tag(takes_context=True)
def language_switch_links(context) -> list[dict]:
    from django.templatetags.static import static

    request = context.get("request")
    current = getattr(request, "LANGUAGE_CODE", _DEFAULT_LANG) if request else _DEFAULT_LANG
    items = []
    for code in _SUPPORTED:
        flag_image_rel = _FLAG_IMAGES.get(code, "")
        flag_image_url = static(flag_image_rel) if flag_image_rel else ""
        items.append(
            {
                "code": code,
                "label": _NATIVE_LABELS.get(code, code.upper()),
                "short": _SHORT_LABELS.get(code, code.upper()),
                "flag": _FLAGS.get(code, ""),
                "flag_image_url": flag_image_url,
                "url": _path_for_language(request, code),
                "is_current": (code == current),
            }
        )
    return items


@register.simple_tag
def og_locale_for_lang(code: str | None) -> str:
    mapping = getattr(settings, "LANGUAGE_OG_LOCALE", {})
    return mapping.get((code or _DEFAULT_LANG), "uk_UA")


@register.simple_tag
def html_lang_for(code: str | None) -> str:
    """Return the BCP-47 regional code for ``<html lang>`` (Phase 17n).

    Maps ``uk``/``ru``/``en`` to ``uk-UA``/``ru-UA``/``en-UA`` so search
    engines understand that every language variant targets the Ukrainian
    market. The default fallback is ``uk-UA``.
    """

    mapping = getattr(settings, "LANGUAGE_HTML_LANG", {})
    return mapping.get((code or _DEFAULT_LANG), "uk-UA")


@register.simple_tag
def hreflang_for(code: str | None) -> str:
    """Return the BCP-47 hreflang code for the given language (Phase 17n)."""

    mapping = getattr(settings, "LANGUAGE_HREFLANG", {})
    return mapping.get((code or _DEFAULT_LANG), "uk-UA")


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


@register.simple_tag
def localized_social_image_path(code: str | None) -> str:
    """Return the approved cache-busting OG/Twitter fallback.

    The August 2026 brand card is intentionally shared across locales. Entity
    pages still override it with their product, category, or article image.
    One versioned path prevents locale drift and stale social-crawler caches.
    """

    return "img/social-preview-2026-08.jpg"
