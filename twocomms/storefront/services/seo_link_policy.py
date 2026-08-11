"""Policy boundary between editorial links and shareable catalog UI state."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlsplit


_INTERNAL_HOSTS = {"twocomms.shop", "www.twocomms.shop"}
_UI_STATE_QUERY_KEYS = {
    "availability",
    "category",
    "collection",
    "color",
    "fit",
    "page",
    "q",
    "size",
    "sort",
    "theme",
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


class _EditorialLinkStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.anchor_policy_stack: list[bool] = []

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
        self.parts.append(self.get_starttag_text())

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag.lower() == "a":
            href = next(
                (value for name, value in attrs if name.lower() == "href"),
                "",
            )
            if is_internal_ui_state_url(href):
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
    parser = _EditorialLinkStripper()
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
    "strip_internal_ui_state_links",
]
