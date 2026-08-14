"""Policy boundary between editorial links and shareable catalog UI state."""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlsplit

from django.conf import settings
from django.urls import translate_url
from django.utils.translation import override

from .catalog_facets import FACET_ALLOWED


_INTERNAL_HOSTS = {"twocomms.shop", "www.twocomms.shop"}
_UI_STATE_QUERY_KEYS = frozenset(FACET_ALLOWED) | {
    "category",
    "page",
    "q",
    "sort",
}


def is_internal_ui_state_url(url: object) -> bool:
    """Return whether an internal link selects query-based listing state."""

    raw_url = str(url or "").strip()
    if not raw_url:
        return False
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return False

    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        return False
    if parsed.netloc and (parsed.hostname or "").lower() not in _INTERNAL_HOSTS:
        return False

    query_keys = {
        key.lower()
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True)
    }
    return bool(query_keys & _UI_STATE_QUERY_KEYS)


def _language_code(value: object) -> str:
    return str(value or settings.LANGUAGE_CODE).split("-", 1)[0].lower()


def _supported_language_codes() -> frozenset[str]:
    return frozenset(_language_code(code) for code, _label in settings.LANGUAGES)


def _source_language_for_path(path: str) -> str:
    first_segment = str(path or "").lstrip("/").split("/", 1)[0].lower()
    if first_segment in _supported_language_codes():
        return first_segment
    return _language_code(settings.LANGUAGE_CODE)


def localize_internal_editorial_url(url: object, language: object) -> str:
    """Translate a known same-site path without guessing route prefixes."""

    raw_url = str(url or "").strip()
    if not raw_url:
        return raw_url
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return raw_url

    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        return raw_url
    if parsed.netloc:
        if (parsed.hostname or "").lower() not in _INTERNAL_HOSTS:
            return raw_url
    elif not parsed.path.startswith("/"):
        return raw_url

    target_language = _language_code(language)
    if target_language not in _supported_language_codes():
        return raw_url

    source_language = _source_language_for_path(parsed.path)
    try:
        # Stored category HTML is normally owned by the unprefixed default
        # locale. Resolve under that source locale before reversing for the
        # request locale; resolving directly under RU/EN leaves it unchanged.
        with override(source_language):
            return translate_url(raw_url, target_language)
    except (TypeError, ValueError):
        return raw_url


def _serialize_start_tag(tag: str, attrs, *, self_closing: bool = False) -> str:
    rendered_attrs = []
    for name, value in attrs:
        if value is None:
            rendered_attrs.append(f" {name}")
        else:
            rendered_attrs.append(f' {name}="{escape(str(value), quote=True)}"')
    closing = " />" if self_closing else ">"
    return f"<{tag}{''.join(rendered_attrs)}{closing}"


class _EditorialLinkPreparer(HTMLParser):
    def __init__(self, *, language: object = None) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.anchor_policy_stack: list[bool] = []
        self.language = language

    def _prepared_anchor(self, tag: str, attrs, *, self_closing: bool) -> str:
        href_index = next(
            (index for index, (name, _value) in enumerate(attrs) if name.lower() == "href"),
            None,
        )
        if href_index is None or self.language is None:
            return self.get_starttag_text()

        href_name, href = attrs[href_index]
        localized_href = localize_internal_editorial_url(href, self.language)
        if localized_href == str(href or ""):
            return self.get_starttag_text()

        prepared_attrs = list(attrs)
        prepared_attrs[href_index] = (href_name, localized_href)
        return _serialize_start_tag(
            tag,
            prepared_attrs,
            self_closing=self_closing,
        )

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == "a":
            href = next(
                (value for name, value in attrs if name.lower() == "href"),
                "",
            )
            strip_anchor = is_internal_ui_state_url(href)
            self.anchor_policy_stack.append(strip_anchor)
            if strip_anchor:
                return
            self.parts.append(
                self._prepared_anchor(tag, attrs, self_closing=False)
            )
            return
        self.parts.append(self.get_starttag_text())

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag.lower() == "a":
            href = next(
                (value for name, value in attrs if name.lower() == "href"),
                "",
            )
            if is_internal_ui_state_url(href):
                return
            self.parts.append(
                self._prepared_anchor(tag, attrs, self_closing=True)
            )
            return
        self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self.anchor_policy_stack:
            if self.anchor_policy_stack.pop():
                return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.parts.append(f"<?{data}>")


def strip_internal_ui_state_links(value: object) -> str:
    """Remove only disallowed anchor tags while preserving their content."""

    html = str(value or "")
    if "<a" not in html.lower():
        return html
    parser = _EditorialLinkPreparer()
    parser.feed(html)
    parser.close()
    return "".join(parser.parts)


def prepare_editorial_html(value: object, *, language: object) -> str:
    """Strip UI-state anchors and localize clean, resolvable internal links."""

    html = str(value or "")
    if "<a" not in html.lower():
        return html
    parser = _EditorialLinkPreparer(language=language)
    parser.feed(html)
    parser.close()
    return "".join(parser.parts)


def filter_editorial_link_items(items):
    """Drop link-shaped items that point at non-owner query state."""

    return [
        item
        for item in items or []
        if not is_internal_ui_state_url(
            item.get("url") if isinstance(item, dict) else getattr(item, "url", "")
        )
    ]


__all__ = [
    "filter_editorial_link_items",
    "is_internal_ui_state_url",
    "localize_internal_editorial_url",
    "prepare_editorial_html",
    "strip_internal_ui_state_links",
]
