"""Template filters for colour-related rendering.

Phase 17h — provides ``translate_color`` so templates can render a
``Color.name`` in the active language at request time.
"""

from __future__ import annotations

from django import template
from django.utils.translation import get_language

from productcolors.color_i18n import translate_color_name

register = template.Library()


@register.filter(name="translate_color")
def translate_color(value, lang: str = "") -> str:
    """Return *value* translated to *lang* (or active language)."""
    if not value:
        return ""
    target = (lang or get_language() or "uk").split("-")[0].lower()
    if target not in ("ru", "en", "uk"):
        target = "uk"
    return translate_color_name(str(value), target)
