"""Phase 17z3 — translate Product / Category / ProductFAQ fields into RU and EN.

The site uses django-modeltranslation: every translatable field gets per-
language columns (``title``, ``title_uk``, ``title_ru``, ``title_en``).
Source text lives in ``title_uk`` (Ukrainian); ``title_ru`` and
``title_en`` are usually empty until populated by this command.

Usage examples:

    # Dry-run — show what would be translated without saving
    python manage.py translate_products --dry-run

    # Translate just products (no categories or FAQ)
    python manage.py translate_products --models product

    # Translate specific items by ID
    python manage.py translate_products --ids 12,34,56

    # Force re-translation of fields that already have RU/EN values
    python manage.py translate_products --force

    # Translate only into Russian
    python manage.py translate_products --target-langs ru

The command uses the OpenAI API (gpt-4o by default) when ``OPENAI_API_KEY``
is configured. Without an API key it falls back to mirroring the source
into the target column when ``--mirror-fallback`` is passed (so the page
renders something even though the value is not actually translated).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Iterable

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Model

from storefront.models import Category, Product, ProductFAQ


_DEFAULT_TARGETS = ("ru", "en")
_SOURCE_LANG = "uk"
_LANG_LABEL = {
    "ru": "Russian",
    "en": "English",
    "uk": "Ukrainian",
}

_MODEL_REGISTRY: dict[str, tuple[type[Model], tuple[str, ...]]] = {
    "product": (
        Product,
        (
            "title",
            "short_description",
            "description",
            "full_description",
            "target_audience",
            "care_instructions",
            "main_image_alt",
            "seo_title",
            "seo_description",
            "seo_keywords",
            "seo_bottom_html",
        ),
    ),
    "category": (
        Category,
        (
            "name",
            "description",
            "seo_text_title",
            "seo_intro_html",
            "seo_title",
            "seo_h1",
            "seo_description",
        ),
    ),
    "faq": (
        ProductFAQ,
        ("question", "answer"),
    ),
}


@dataclass
class FieldUpdate:
    obj: Model
    field: str
    target_lang: str
    source: str
    translated: str


class Command(BaseCommand):
    help = (
        "Translate Product / Category / ProductFAQ translatable fields "
        "from Ukrainian into Russian / English using OpenAI."
    )

    def add_arguments(self, parser):  # noqa: D401 — Django convention
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not save any changes; print what would be translated.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-translate fields even if a value is already present.",
        )
        parser.add_argument(
            "--models",
            default="product,category,faq",
            help="Comma-separated subset: product,category,faq.",
        )
        parser.add_argument(
            "--ids",
            default="",
            help="Comma-separated PK list. Applies to all selected models.",
        )
        parser.add_argument(
            "--target-langs",
            default=",".join(_DEFAULT_TARGETS),
            help="Comma-separated target languages (default: ru,en).",
        )
        parser.add_argument(
            "--source-lang",
            default=_SOURCE_LANG,
            help="Language of the canonical text (default: uk).",
        )
        parser.add_argument(
            "--max-items",
            type=int,
            default=0,
            help="Process at most N rows per model (0 = no limit).",
        )
        parser.add_argument(
            "--mirror-fallback",
            action="store_true",
            help="When OpenAI is unavailable, copy the source text into the "
            "target field instead of skipping it.",
        )
        parser.add_argument(
            "--openai-model",
            default=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            help="OpenAI model to use for translation.",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.0,
            help="Seconds to sleep between API calls (rate-limit guard).",
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def handle(self, *args, **options) -> None:
        dry_run: bool = options["dry_run"]
        force: bool = options["force"]
        max_items: int = options["max_items"]
        sleep_for: float = options["sleep"]
        mirror_fallback: bool = options["mirror_fallback"]
        openai_model: str = options["openai_model"]
        source_lang: str = (options["source_lang"] or _SOURCE_LANG).strip()
        target_langs = [
            code.strip() for code in (options["target_langs"] or "").split(",") if code.strip()
        ]
        if not target_langs:
            raise CommandError("--target-langs cannot be empty")

        selected_models = [
            slug.strip().lower() for slug in (options["models"] or "").split(",") if slug.strip()
        ]
        unknown = [s for s in selected_models if s not in _MODEL_REGISTRY]
        if unknown:
            raise CommandError(
                f"Unknown models {unknown}. Available: {sorted(_MODEL_REGISTRY)}"
            )

        ids: set[int] = set()
        if options["ids"]:
            try:
                ids = {int(x) for x in options["ids"].split(",") if x.strip()}
            except ValueError as exc:
                raise CommandError(f"--ids must be comma-separated integers: {exc}")

        client = self._build_openai_client()
        if client is None and not mirror_fallback:
            self.stdout.write(
                self.style.WARNING(
                    "OPENAI_API_KEY is not set. Re-run with --mirror-fallback "
                    "to copy Ukrainian text verbatim into RU/EN columns."
                )
            )
            return

        total_filled = 0
        total_skipped = 0
        total_errors = 0

        for slug in selected_models:
            model, fields = _MODEL_REGISTRY[slug]
            qs = model.objects.all().order_by("pk")
            if ids:
                qs = qs.filter(pk__in=ids)
            if max_items:
                qs = qs[:max_items]

            self.stdout.write(self.style.NOTICE(f"\n=== {slug} ({qs.count()} rows) ==="))
            for obj in qs:
                pk = obj.pk
                self.stdout.write(self.style.NOTICE(f"  • {model.__name__}#{pk}"))
                pending: list[FieldUpdate] = []
                for field in fields:
                    src_attr = f"{field}_{source_lang}"
                    source_value = getattr(obj, src_attr, "") or ""
                    if not source_value.strip():
                        # Backfill canonical *_uk from the base field if empty.
                        base_value = getattr(obj, field, "") or ""
                        if base_value.strip():
                            source_value = base_value
                            if not dry_run:
                                setattr(obj, src_attr, source_value)
                    if not source_value.strip():
                        continue

                    for lang in target_langs:
                        tgt_attr = f"{field}_{lang}"
                        if not hasattr(obj, tgt_attr):
                            continue
                        existing = (getattr(obj, tgt_attr, "") or "").strip()
                        if existing and not force:
                            continue
                        translated = self._translate(
                            client=client,
                            text=source_value,
                            target_lang=lang,
                            mirror_fallback=mirror_fallback,
                            openai_model=openai_model,
                        )
                        if not translated:
                            total_errors += 1
                            self.stdout.write(
                                self.style.ERROR(
                                    f"      ! failed translating {field}->{lang}"
                                )
                            )
                            continue
                        pending.append(
                            FieldUpdate(
                                obj=obj,
                                field=tgt_attr,
                                target_lang=lang,
                                source=source_value,
                                translated=translated,
                            )
                        )
                        if sleep_for > 0:
                            time.sleep(sleep_for)

                if not pending:
                    total_skipped += 1
                    self.stdout.write("      (nothing to fill)")
                    continue

                for upd in pending:
                    setattr(obj, upd.field, upd.translated)
                    self.stdout.write(
                        f"      + {upd.field}: {self._preview(upd.translated)}"
                    )
                if not dry_run:
                    try:
                        obj.save()
                    except Exception as exc:  # pragma: no cover — rare
                        total_errors += 1
                        self.stdout.write(
                            self.style.ERROR(f"      ! save failed: {exc}")
                        )
                        continue
                total_filled += len(pending)

        verb = "would fill" if dry_run else "filled"
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {verb} {total_filled} field-language pairs; "
                f"skipped {total_skipped} rows; errors {total_errors}."
            )
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_openai_client(self):
        api_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get(
            "OPENAI_API_KEY"
        )
        if not api_key:
            return None
        try:
            import openai
        except ImportError:
            self.stdout.write(
                self.style.WARNING(
                    "openai package is not installed; falling back to mirror mode."
                )
            )
            return None
        try:
            return openai.OpenAI(api_key=api_key)
        except Exception as exc:  # pragma: no cover — defensive
            self.stdout.write(
                self.style.WARNING(f"OpenAI client init failed: {exc}")
            )
            return None

    def _translate(
        self,
        *,
        client: Any,
        text: str,
        target_lang: str,
        mirror_fallback: bool,
        openai_model: str,
    ) -> str:
        text = text.strip()
        if not text:
            return ""
        if client is None:
            return text if mirror_fallback else ""

        prompt_lang = _LANG_LABEL.get(target_lang, target_lang)
        system = (
            "You translate Ukrainian e-commerce copy into "
            f"{prompt_lang} for the streetwear brand TwoComms. "
            "Keep the same meaning, tone of voice and brand voice. "
            "Preserve HTML tags, Markdown markers, percent signs, "
            "currency, units, line breaks and the exact word 'TwoComms'. "
            "Return only the translated text, no commentary."
        )
        try:
            resp = client.chat.completions.create(
                model=openai_model,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ],
            )
            choice = resp.choices[0]
            return (choice.message.content or "").strip()
        except Exception as exc:  # pragma: no cover — network errors
            self.stdout.write(
                self.style.WARNING(f"      OpenAI error ({target_lang}): {exc}")
            )
            return text if mirror_fallback else ""

    @staticmethod
    def _preview(text: str, limit: int = 80) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 1] + "…"
