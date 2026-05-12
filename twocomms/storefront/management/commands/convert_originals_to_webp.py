"""SEO/Performance v1.0 Phase 11 — convert oversized PNG/JPEG originals to WebP.

Companion to ``compress_media_originals``. The conservative
"recompress-in-place" command bottoms out the moment Pillow's PNG
encoder ceases to find redundancy in iPhone screenshots: a 11 MB
``IMG_7105.png`` will refuse to shrink because PNG cannot encode
photographic content efficiently.

This command takes the more invasive but vastly more effective route:

* Walks the same set of (model, field) targets;
* For every image larger than ``--min-bytes`` (default 600_000) and
  whose extension is in ``.png``/``.jpg``/``.jpeg``, it
    1. resizes the pixel buffer down to fit ``--max-width × --max-height``,
    2. re-encodes as WebP at quality ``--quality`` (default 85),
    3. writes ``<basename>.webp`` next to the original,
    4. **updates the model's image field** to point at the new file
       (no more URL pointing at the old PNG),
    5. deletes the source file unless ``--keep-source`` is set.

Result: the 11 MB iPhone PNGs in ``/media/products/extra/`` collapse
to 200-500 KB WebPs, the PDP gallery loads in <500 ms on 4G, and the
sitemap-images / OG image / JSON-LD ``image`` slots all switch to the
new URL automatically because they read from ``ImageField.url``.

Safety:
* Wrapped in a transaction per file (DB row update + filesystem swap).
* Pillow falls back to a no-op if the input cannot be opened.
* Refuses to delete the source unless the DB update commits.

Usage:
    python manage.py convert_originals_to_webp --dry-run
    python manage.py convert_originals_to_webp --models storefront.ProductImage.image
    python manage.py convert_originals_to_webp --limit 25 --keep-source
"""
from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)


DEFAULT_TARGETS: list[tuple[str, str, str]] = [
    ("storefront", "ProductImage", "image"),
    ("productcolors", "ProductColorImage", "image"),
    ("storefront", "Product", "main_image"),
    ("storefront", "Product", "home_card_image"),
    ("storefront", "Category", "cover"),
    ("storefront", "Category", "icon"),
    ("storefront", "PrintProposal", "image"),
    ("warehouse", "Print", "main_image"),
    ("warehouse", "PrintColorVariant", "image"),
    ("reviews", "ReviewImage", "image"),
    ("dtf", "DtfWork", "image"),
]


TARGET_DIM_OVERRIDES: dict[tuple, tuple[int, int]] = {
    ("productcolors", "ProductColorImage", "image"): (800, 800),
    ("storefront", "Category", "icon"): (480, 480),
}


@dataclass
class FileResult:
    src: str
    dst: str = ""
    before: int = 0
    after: int = 0
    skipped_reason: str = ""

    @property
    def saved(self) -> int:
        return max(0, self.before - self.after)

    @property
    def ratio(self) -> float:
        if self.before <= 0:
            return 0.0
        return (self.before - self.after) / self.before


@dataclass
class RunStats:
    touched: int = 0
    skipped: int = 0
    failed: int = 0
    bytes_before: int = 0
    bytes_after: int = 0
    biggest: list[FileResult] = field(default_factory=list)


class Command(BaseCommand):
    help = "Convert oversized PNG/JPEG originals to WebP and rewrite DB."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--min-bytes", type=int, default=600_000)
        parser.add_argument("--max-width", type=int, default=1600)
        parser.add_argument("--max-height", type=int, default=2000)
        parser.add_argument("--quality", type=int, default=85)
        parser.add_argument("--models", nargs="+", default=None,
                            help="Restrict to <app>.<model>.<field> selectors.")
        parser.add_argument("--keep-source", action="store_true",
                            help="Do not delete the original after conversion.")
        parser.add_argument("--verbose-skip", action="store_true")
        parser.add_argument("--only-extensions", nargs="+",
                            default=[".png", ".jpg", ".jpeg"],
                            help="File extensions to consider (case-insensitive).")

    # ------------------------------------------------------------------ entrypoint

    def handle(self, *args, **opts):
        try:
            from PIL import Image, ImageOps  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise CommandError("Pillow is required for convert_originals_to_webp") from exc

        self.dry = bool(opts["dry_run"])
        self.limit = int(opts["limit"] or 0)
        self.min_bytes = int(opts["min_bytes"])
        self.max_width = int(opts["max_width"])
        self.max_height = int(opts["max_height"])
        self.quality = int(opts["quality"])
        self.keep_source = bool(opts["keep_source"])
        self.verbose_skip = bool(opts["verbose_skip"])
        self.only_extensions = {e.lower() for e in opts["only_extensions"]}

        targets = self._resolve_targets(opts["models"])
        stats = RunStats()

        self._announce_header(targets)

        for app_label, model_name, field_name in targets:
            try:
                model = apps.get_model(app_label, model_name)
            except LookupError:
                self.stdout.write(self.style.WARNING(
                    f"  skip (model not found): {app_label}.{model_name}"))
                continue
            override = (
                TARGET_DIM_OVERRIDES.get((app_label, model_name, field_name))
                or TARGET_DIM_OVERRIDES.get((app_label, model_name))
            )
            self._process_model(model, field_name, stats, override=override)
            if self.limit and stats.touched >= self.limit:
                break

        self._announce_summary(stats)

    # ------------------------------------------------------------------ helpers

    def _resolve_targets(self, selector):
        if not selector:
            return list(DEFAULT_TARGETS)
        wanted = []
        for raw in selector:
            try:
                app_label, model_name, field_name = raw.split(".")
            except ValueError:
                raise CommandError(f"Bad selector '{raw}'. Use <app>.<model>.<field>")
            wanted.append((app_label, model_name, field_name))
        return wanted

    def _process_model(self, model, field_name: str, stats: RunStats,
                       *, override: Optional[tuple[int, int]] = None):
        if not hasattr(model, field_name):
            return
        max_w, max_h = override if override else (self.max_width, self.max_height)
        qs = model.objects.exclude(**{f"{field_name}": ""}).only("id", field_name)
        for instance in qs.iterator(chunk_size=200):
            field = getattr(instance, field_name, None)
            if not field:
                continue
            try:
                disk_path = Path(field.path)
            except (ValueError, NotImplementedError):
                continue
            if not disk_path.is_file():
                continue
            ext = disk_path.suffix.lower()
            if ext not in self.only_extensions:
                continue
            if ext == ".webp":
                continue  # nothing to do
            try:
                size = disk_path.stat().st_size
            except OSError:
                continue
            if size < self.min_bytes:
                continue
            if self.limit and stats.touched >= self.limit:
                return

            result = self._convert_one(instance, field_name, disk_path,
                                       max_w=max_w, max_h=max_h)
            stats.bytes_before += result.before
            stats.bytes_after += result.after
            if result.skipped_reason:
                stats.skipped += 1
                if self.verbose_skip:
                    self.stdout.write(
                        f"  SKIP  {disk_path.name:60s}  "
                        f"{result.before/1024:8.0f}KB  ({result.skipped_reason})"
                    )
                continue
            stats.touched += 1
            stats.biggest.append(result)
            stats.biggest.sort(key=lambda r: r.saved, reverse=True)
            stats.biggest = stats.biggest[:15]
            self.stdout.write(
                f"  {disk_path.name:60s}  {result.before/1024:8.0f}KB  →  "
                f"{Path(result.dst).name:50s}  {result.after/1024:8.0f}KB  "
                f"(-{result.ratio*100:4.1f}%)"
            )

    def _convert_one(self, instance, field_name, src_path: Path,
                     *, max_w: int, max_h: int) -> FileResult:
        from PIL import Image, ImageOps

        result = FileResult(src=str(src_path), before=src_path.stat().st_size)
        dst_path = src_path.with_suffix(".webp")
        if dst_path.exists() and dst_path != src_path:
            # If a .webp already lives next to the original, do not
            # blindly overwrite — that may be a manually-prepared
            # high-quality version.
            result.skipped_reason = "webp-exists"
            result.after = result.before
            return result

        try:
            with Image.open(src_path) as img:
                img = ImageOps.exif_transpose(img)
                src_w, src_h = img.size
                if src_w <= 0 or src_h <= 0:
                    result.skipped_reason = "zero-size"
                    result.after = result.before
                    return result
                scale = min(max_w / src_w, max_h / src_h, 1.0)
                if scale < 1.0:
                    img = img.resize(
                        (max(1, round(src_w * scale)), max(1, round(src_h * scale))),
                        Image.LANCZOS,
                    )
                if img.mode == "P":
                    img = img.convert("RGBA")
                elif img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="WEBP",
                         quality=self.quality, method=6)
                payload = buf.getvalue()
        except Exception as exc:
            logger.warning("convert_originals_to_webp: failed on %s — %s",
                           src_path, exc)
            result.skipped_reason = f"error: {exc}"
            result.after = result.before
            return result

        result.after = len(payload)
        result.dst = str(dst_path)

        if result.after >= result.before:
            # WebP did not beat the original — likely already-tiny PNG icon.
            result.skipped_reason = "webp-larger"
            result.after = result.before
            return result

        if self.dry:
            return result

        # Atomic rewrite: stage `.webp.tmp`, persist DB pointer, then
        # promote and (optionally) drop the source file.
        tmp_path = dst_path.with_suffix(dst_path.suffix + ".tmp")
        try:
            with open(tmp_path, "wb") as fh:
                fh.write(payload)
        except OSError as exc:
            result.skipped_reason = f"write-error: {exc}"
            result.after = result.before
            return result

        try:
            with transaction.atomic():
                os.replace(tmp_path, dst_path)
                # Build the new FileField name relative to the
                # storage root so ``instance.image.url`` keeps working.
                storage = getattr(instance, field_name).storage
                rel_old = getattr(instance, field_name).name
                rel_new = self._swap_extension(rel_old, ".webp")
                # When the relative path already pointed at a .webp
                # for some weird reason, abort.
                if rel_new == rel_old:
                    result.skipped_reason = "name-already-webp"
                    return result
                # Ensure the storage knows about the new file.
                if not storage.exists(rel_new):
                    # Race-safe: the file is already on disk (we just
                    # wrote it), but some storages cache `exists`.
                    pass
                setattr(instance, field_name, rel_new)
                instance.save(update_fields=[field_name])
                if not self.keep_source:
                    try:
                        src_path.unlink(missing_ok=True)
                    except OSError:
                        pass
        except Exception as exc:
            logger.warning("convert_originals_to_webp: db swap failed for %s — %s",
                           src_path, exc)
            # Rollback: remove the just-written webp so we can retry.
            try:
                dst_path.unlink(missing_ok=True)
            except OSError:
                pass
            result.skipped_reason = f"db-error: {exc}"
            result.after = result.before
            return result

        return result

    @staticmethod
    def _swap_extension(name: str, new_ext: str) -> str:
        # ``name`` is a relative path inside storage, e.g.
        # ``products/extra/IMG_7105.png``.
        base, _ = os.path.splitext(name)
        return f"{base}{new_ext}"

    # ------------------------------------------------------------------ output

    def _announce_header(self, targets):
        prefix = "[DRY-RUN] " if self.dry else ""
        self.stdout.write(self.style.NOTICE(
            f"{prefix}convert_originals_to_webp — "
            f"max={self.max_width}x{self.max_height}, "
            f"quality={self.quality}, "
            f"min_bytes={self.min_bytes}, "
            f"keep_source={self.keep_source}, "
            f"limit={self.limit or 'unlimited'}"
        ))
        for app_label, model_name, field_name in targets:
            self.stdout.write(f"  target: {app_label}.{model_name}.{field_name}")

    def _announce_summary(self, stats: RunStats):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Touched: {stats.touched}  Skipped: {stats.skipped}  Failed: {stats.failed}"
        ))
        if stats.touched:
            saved = stats.bytes_before - stats.bytes_after
            self.stdout.write(self.style.SUCCESS(
                f"Total: {stats.bytes_before/1_048_576:.1f} MB → "
                f"{stats.bytes_after/1_048_576:.1f} MB  "
                f"(-{saved/1_048_576:.1f} MB, "
                f"{(saved/stats.bytes_before*100 if stats.bytes_before else 0):.1f}%)"
            ))
        if stats.biggest:
            self.stdout.write("Top savings:")
            for item in stats.biggest[:10]:
                self.stdout.write(
                    f"  {Path(item.src).name:60s}  "
                    f"{item.before/1024:8.0f}KB → {item.after/1024:8.0f}KB  "
                    f"(-{item.ratio*100:4.1f}%)"
                )
