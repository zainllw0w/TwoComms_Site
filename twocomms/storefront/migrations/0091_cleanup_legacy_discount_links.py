"""Remove the exact persisted links to the retired discount facet."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlsplit

from django.db import migrations


_CATEGORY_SLUGS = {"hoodie", "tshirts", "long-sleeve"}
_LOCALE_PREFIXES = {"", "uk", "ru", "en"}


def _is_retired_discount_url(value: object) -> bool:
    try:
        parsed = urlsplit(str(value or "").strip())
    except ValueError:
        # A malformed persisted href must not abort the whole data migration.
        return False
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        return False
    if parsed.netloc and (parsed.hostname or "").lower() not in {
        "twocomms.shop", "www.twocomms.shop",
    }:
        return False
    path_parts = [part for part in parsed.path.rstrip("/").split("/") if part]
    if len(path_parts) == 3 and path_parts[0] in _LOCALE_PREFIXES:
        _locale, catalog, category = path_parts
    elif len(path_parts) == 2:
        catalog, category = path_parts
    else:
        return False
    if catalog != "catalog" or category not in _CATEGORY_SLUGS:
        return False
    query = parse_qsl(parsed.query, keep_blank_values=True)
    return sum(key == "sort" and value == "discount" for key, value in query) == 1


class _RetiredDiscountAnchorRemover(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []
        self._drop_anchor = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = next((v for k, v in attrs if k.lower() == "href"), "")
            drop = _is_retired_discount_url(href)
            self._drop_anchor.append(drop)
            if drop:
                return
        self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._drop_anchor:
            if self._drop_anchor.pop():
                return
        self.parts.append(f"</{tag}>")

    def handle_startendtag(self, tag, attrs):
        if tag.lower() == "a":
            href = next((v for k, v in attrs if k.lower() == "href"), "")
            if _is_retired_discount_url(href):
                return
        self.parts.append(self.get_starttag_text())

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def handle_comment(self, data):
        self.parts.append(f"<!--{data}-->")


def _remove_retired_discount_anchors(value: object) -> str:
    html = str(value or "")
    if "sort=discount" not in html:
        return html
    parser = _RetiredDiscountAnchorRemover()
    parser.feed(html)
    parser.close()
    return "".join(parser.parts)


def remove_legacy_discount_links(apps, schema_editor):
    Category = apps.get_model("storefront", "Category")
    Item = apps.get_model("storefront", "CategorySeoBlockItem")

    for item in Item._base_manager.all().iterator():
        if _is_retired_discount_url(item.url):
            item.delete()

    fields = (
        "description", "description_uk", "description_ru", "description_en",
    )
    rows = Category._base_manager.values("pk", *fields)
    for category in rows.iterator():
        # Historical model fields are plain columns; use the projected row
        # directly so modeltranslation descriptors cannot reintroduce fallback
        # values while this data migration is running.
        updates = {}
        for field in fields:
            value = category.get(field)
            if not value:
                continue
            cleaned = _remove_retired_discount_anchors(value)
            if cleaned != value:
                updates[field] = cleaned
        if updates:
            # Use the historical manager's update path; modeltranslation
            # descriptors are bypassed by the projected values above.
            Category._base_manager.filter(pk=category["pk"]).update(**updates)


class Migration(migrations.Migration):
    dependencies = [("storefront", "0090_category_order_language_indexes")]
    operations = [migrations.RunPython(remove_legacy_discount_links, migrations.RunPython.noop)]
