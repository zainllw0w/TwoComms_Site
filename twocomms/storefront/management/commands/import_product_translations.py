"""Phase 17z5 — import hand-crafted RU/EN translations for Product /
Category / ProductFAQ from a JSON file.

The JSON file is keyed by Ukrainian source text:

    {
      "products": {
        "Футболка класична": {
          "title":             {"ru": "...", "en": "..."},
          "short_description": {"ru": "...", "en": "..."},
          "_match_by":         "title"
        },
        ...
      },
      "by_id": {
        "42": {
          "short_description": {"ru": "...", "en": "..."}
        }
      }
    }

Both lookup modes are supported simultaneously:

* The ``products`` section uses the canonical Ukrainian text of a field
  (usually ``title``) as the lookup key. Every product whose ``title_uk``
  matches gets the listed field translations.
* The ``by_id`` section overrides specific objects by PK regardless of
  whether the ``products`` section matched them.

Usage::

    python manage.py import_product_translations \
        --file /path/to/translations.json [--dry-run] [--force]

If no ``--file`` is provided the command looks for
``twocomms/data/product_translations.json``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from storefront.models import Category, Product, ProductFAQ


SECTION_TO_MODEL = {
    "products": Product,
    "categories": Category,
    "faq": ProductFAQ,
}

# Default lookup field per section when ``_match_by`` is not specified.
DEFAULT_MATCH_FIELD = {
    "products": "title",
    "categories": "name",
    "faq": "question",
}


class Command(BaseCommand):
    help = (
        "Apply hand-crafted RU/EN translations to Product/Category/ProductFAQ "
        "fields from a JSON file (UA source text as key)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="",
            help="Path to translations JSON. Defaults to "
            "twocomms/data/product_translations.json relative to BASE_DIR.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not save; report what would change.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing RU/EN values even when they are non-empty.",
        )
        parser.add_argument(
            "--sections",
            default="products,categories,faq",
            help="Comma-separated sections to import.",
        )
        parser.add_argument(
            "--target-langs",
            default="ru,en",
            help="Comma-separated target languages to apply (default: ru,en).",
        )

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        path = options["file"].strip() or str(
            Path(settings.BASE_DIR) / "data" / "product_translations.json"
        )
        translations_path = Path(path)
        if not translations_path.exists():
            raise CommandError(f"Translations file not found: {translations_path}")

        with translations_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

        sections = [
            s.strip() for s in (options["sections"] or "").split(",") if s.strip()
        ]
        langs = [
            code.strip() for code in (options["target_langs"] or "").split(",") if code.strip()
        ]
        if not langs:
            raise CommandError("--target-langs cannot be empty")

        dry_run: bool = options["dry_run"]
        force: bool = options["force"]

        total_changes = 0
        total_unmatched: list[tuple[str, str]] = []
        per_section_stats: dict[str, dict[str, int]] = {}

        for section in sections:
            if section not in SECTION_TO_MODEL:
                self.stdout.write(self.style.WARNING(f"Skip unknown section: {section}"))
                continue
            stats, changes, unmatched = self._import_section(
                section=section,
                payload=payload,
                langs=langs,
                dry_run=dry_run,
                force=force,
            )
            total_changes += changes
            total_unmatched.extend((section, key) for key in unmatched)
            per_section_stats[section] = stats

        self.stdout.write("")
        for section, stats in per_section_stats.items():
            self.stdout.write(
                self.style.NOTICE(
                    f"[{section}] matched={stats['matched']} "
                    f"updated_fields={stats['updated']} "
                    f"skipped={stats['skipped']} "
                    f"unmatched_keys={stats['unmatched']}"
                )
            )
        if total_unmatched:
            self.stdout.write(self.style.WARNING("\nUnmatched keys:"))
            for section, key in total_unmatched[:50]:
                preview = key if len(key) < 80 else key[:79] + "…"
                self.stdout.write(f"  [{section}] {preview}")
            if len(total_unmatched) > 50:
                self.stdout.write(f"  … and {len(total_unmatched) - 50} more")

        verb = "would apply" if dry_run else "applied"
        self.stdout.write(
            self.style.SUCCESS(f"\nDone. {verb} {total_changes} field-language updates.")
        )

    # ------------------------------------------------------------------
    def _import_section(
        self,
        *,
        section: str,
        payload: dict[str, Any],
        langs: list[str],
        dry_run: bool,
        force: bool,
    ) -> tuple[dict[str, int], int, list[str]]:
        model = SECTION_TO_MODEL[section]
        section_data = payload.get(section) or {}
        by_id_data = (payload.get("by_id") or {}).get(section, {})

        stats = {"matched": 0, "updated": 0, "skipped": 0, "unmatched": 0}
        changes_total = 0
        unmatched_keys: list[str] = []

        # Build lookup: ``{normalized_uk: [list of objects]}`` keyed by the
        # field declared in ``_match_by`` (default ``title`` / ``name`` /
        # ``question``).
        match_field = DEFAULT_MATCH_FIELD[section]
        objects = list(model.objects.all())
        lookup: dict[str, list[Any]] = {}
        for obj in objects:
            uk_val = (getattr(obj, f"{match_field}_uk", None) or "").strip()
            base_val = (getattr(obj, match_field, None) or "").strip()
            key = self._normalize(uk_val or base_val)
            if key:
                lookup.setdefault(key, []).append(obj)

        # 1) Iterate the keyed section (UA source as key)
        dirty: dict[int, Any] = {}
        for raw_key, body in section_data.items():
            key = self._normalize(raw_key)
            local_match_field = (body.get("_match_by") or match_field).strip()
            # If `_match_by` differs from default, build a per-key lookup.
            if local_match_field != match_field:
                matched_objs = [
                    o
                    for o in objects
                    if self._normalize(
                        getattr(o, f"{local_match_field}_uk", None)
                        or getattr(o, local_match_field, None)
                    )
                    == key
                ]
            else:
                matched_objs = lookup.get(key, [])

            if not matched_objs:
                stats["unmatched"] += 1
                unmatched_keys.append(raw_key)
                continue

            stats["matched"] += len(matched_objs)
            for obj in matched_objs:
                changes_total += self._apply_translations(
                    obj=obj,
                    body=body,
                    langs=langs,
                    force=force,
                    stats=stats,
                )
                dirty[obj.pk] = obj

        # 2) Apply by_id overrides
        if by_id_data:
            objs_by_pk = {o.pk: o for o in objects}
            for raw_pk, body in by_id_data.items():
                try:
                    pk = int(raw_pk)
                except ValueError:
                    self.stdout.write(
                        self.style.WARNING(f"  by_id key {raw_pk!r} is not an int")
                    )
                    continue
                obj = objs_by_pk.get(pk)
                if not obj:
                    stats["unmatched"] += 1
                    unmatched_keys.append(f"by_id:{raw_pk}")
                    continue
                stats["matched"] += 1
                changes_total += self._apply_translations(
                    obj=obj,
                    body=body,
                    langs=langs,
                    force=force,
                    stats=stats,
                )
                dirty[obj.pk] = obj

        if not dry_run and dirty:
            with transaction.atomic():
                for obj in dirty.values():
                    try:
                        obj.save()
                    except Exception as exc:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ! save failed for {model.__name__}#{obj.pk}: {exc}"
                            )
                        )

        return stats, changes_total, unmatched_keys

    # ------------------------------------------------------------------
    def _apply_translations(
        self,
        *,
        obj: Any,
        body: dict[str, Any],
        langs: list[str],
        force: bool,
        stats: dict[str, int],
    ) -> int:
        applied = 0
        for field_name, lang_map in body.items():
            if field_name.startswith("_"):
                continue
            if not isinstance(lang_map, dict):
                continue
            for lang in langs:
                tgt_attr = f"{field_name}_{lang}"
                if not hasattr(obj, tgt_attr):
                    continue
                value = (lang_map.get(lang) or "").strip()
                if not value:
                    continue
                existing = (getattr(obj, tgt_attr, "") or "").strip()
                if existing and not force:
                    stats["skipped"] += 1
                    continue
                setattr(obj, tgt_attr, value)
                stats["updated"] += 1
                applied += 1
        return applied

    # ------------------------------------------------------------------
    @staticmethod
    def _normalize(text: str | None) -> str:
        """Make UA lookup tolerant to surrounding whitespace and CRLF noise."""
        if not text:
            return ""
        return " ".join(text.replace("\r\n", "\n").split()).strip()
