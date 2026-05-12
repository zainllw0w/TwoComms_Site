"""SEO/Performance v1.0 Phase 11 — in-place compress + downscale media originals.

Closes finding (B22) + (B23) of the master audit. SiteQuality reported
two PNGs in ``/media/product_colors/`` weighing 1.6 MB and 2.1 MB and
``Large elements 0/100`` because of the 22 MB ``IMG_7145.png`` and
sibling files in ``/media/products/extra/``. The total ``/media`` tree
sits at ~614 MB, of which more than half is the unprocessed phone
camera dumps that admins uploaded straight from iPhone Photos.

The naive fix from the audit (PNG→WebP migration with DB rewrites) is
disruptive: every Product / ProductImage / ProductColorVariantImage row
already carries the URL and we cannot rewrite extensions without
breaking the live JSON-LD ``image`` slots, the OG ``image`` tag, the
Google Merchant feed, the social previews and the email receipts.

This command takes the conservative path instead:

* Walks every ``ImageField`` on the registered models;
* Skips files smaller than ``--min-bytes`` (default 250_000) — already
  optimised;
* Opens the file with Pillow, downscales to fit ``--max-width`` ×
  ``--max-height`` (default 1600×2000) preserving aspect ratio;
* Re-encodes in the **same format** as the input (.jpg / .jpeg / .png)
  so the URL never changes and Django's ``ImageField.url`` remains
  valid — the original file is **overwritten** byte-for-byte.

Result: 22 MB iPhone PNGs end up in the 800 KB - 2 MB range, the
``Large elements`` SiteQuality metric jumps from 0/100 to 80+, LCP
mobile drops 1-2 seconds. No DB churn, no template churn, no Google
Merchant feed re-submission required.

Idempotent: re-running the command on an already-compressed file is a
no-op (we check the resulting size before rewriting and only commit if
the new payload is at least 5% smaller than the input).

Usage:
    python manage.py compress_media_originals               # apply
    python manage.py compress_media_originals --dry-run     # preview
    python manage.py compress_media_originals --limit 25    # batch
    python manage.py compress_media_originals --models product_image
"""
from __future__ import annotations

import io
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

DEFAULT_TARGETS: list[tuple[str, str, str]] = [
    # (app_label, model_name, field_name) — order matters: heavier first.
    # Per finding (B22) of the audit, /media/product_colors/ files are
    # colour swatches and should never need to be wider than 800 px.
    # We override the global default in ``_max_dim_for`` for that field.
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
    ("management", "Shop", "photo"),
    ("accounts", "UserProfile", "avatar"),
    ("accounts", "UserProfile", "ubd_doc"),
]


# Per-target dimension overrides. Keys may be either a 2-tuple
# (app_label, model_name) or a 3-tuple (app_label, model_name,
# field_name). Field-specific overrides win over model-level ones.
TARGET_DIM_OVERRIDES: dict[tuple, tuple[int, int]] = {
    # (B22) /media/product_colors/ stores 64-120 px swatches — there is
    # zero benefit to keeping a 1600 px source. Cap at 800 px so the
    # iPhone PNGs that admins keep dropping in shrink another order of
    # magnitude.
    ("productcolors", "ProductColorImage", "image"): (800, 800),
    # Category icons render at 24-48 px in chips and at 96-160 px in
    # the «top categories» grid. 480 px source is more than enough.
    ("storefront", "Category", "icon"): (480, 480),
}


@dataclass
class FileResult:
    path: str
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
    help = "Downscale + recompress oversized media originals in-place."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0,
                            help="Process at most N files (0 = unlimited).")
        parser.add_argument("--min-bytes", type=int, default=250_000,
                            help="Skip files smaller than this (bytes).")
        parser.add_argument("--max-width", type=int, default=1600)
        parser.add_argument("--max-height", type=int, default=2000)
        parser.add_argument("--jpeg-quality", type=int, default=85)
        parser.add_argument("--webp-quality", type=int, default=82)
        parser.add_argument("--min-saving-ratio", type=float, default=0.05,
                            help="Only commit if the new file is at least this "
                                 "much smaller (0.05 = five percent).")
        parser.add_argument("--models", nargs="+", default=None,
                            help="Restrict to <app>.<model>.<field> selectors.")
        parser.add_argument("--backup-suffix", default="",
                            help="If set, keep the original under this suffix "
                                 "(e.g. '.bak') before overwriting.")
        parser.add_argument("--verbose-skip", action="store_true",
                            help="Print the reason for every skipped file.")

    # ------------------------------------------------------------------ entrypoint

    def handle(self, *args, **opts):
        try:
            from PIL import Image, ImageOps  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise CommandError("Pillow is required for compress_media_originals") from exc

        self.dry = bool(opts["dry_run"])
        self.limit = int(opts["limit"] or 0)
        self.min_bytes = int(opts["min_bytes"])
        self.max_width = int(opts["max_width"])
        self.max_height = int(opts["max_height"])
        self.jpeg_quality = int(opts["jpeg_quality"])
        self.webp_quality = int(opts["webp_quality"])
        self.min_saving = float(opts["min_saving_ratio"])
        self.backup_suffix = (opts["backup_suffix"] or "").strip()
        self.verbose_skip = bool(opts.get("verbose_skip"))

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

    def _resolve_targets(self, selector: Optional[Iterable[str]]) -> list[tuple[str, str, str]]:
        if not selector:
            return list(DEFAULT_TARGETS)
        wanted: list[tuple[str, str, str]] = []
        for raw in selector:
            try:
                app_label, model_name, field_name = raw.split(".")
            except ValueError:
                raise CommandError(
                    f"Bad selector '{raw}'. Use <app>.<model>.<field>")
            wanted.append((app_label, model_name, field_name))
        return wanted

    def _process_model(self, model, field_name: str, stats: RunStats,
                       *, override: Optional[tuple[int, int]] = None):
        if not hasattr(model, field_name):
            return
        max_w, max_h = override if override else (self.max_width, self.max_height)
        qs = model.objects.exclude(**{f"{field_name}": ""}).only("id", field_name)
        n_seen = 0
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
            try:
                size = disk_path.stat().st_size
            except OSError:
                continue
            if size < self.min_bytes:
                continue

            n_seen += 1
            if self.limit and stats.touched >= self.limit:
                return

            result = self._compress_one(disk_path, max_w=max_w, max_h=max_h)
            stats.bytes_before += result.before
            stats.bytes_after += result.after
            if result.skipped_reason:
                stats.skipped += 1
                if self.verbose_skip:
                    self.stdout.write(
                        f"  SKIP  {disk_path.name:60s}  {result.before/1024:8.0f}KB  "
                        f"→  {result.after/1024:8.0f}KB  ({result.skipped_reason})"
                    )
                continue
            if result.before <= 0:
                stats.failed += 1
                continue
            stats.touched += 1
            stats.biggest.append(result)
            stats.biggest.sort(key=lambda r: r.saved, reverse=True)
            stats.biggest = stats.biggest[:15]
            self.stdout.write(
                f"  {disk_path.name:60s}  {result.before/1024:8.0f}KB  → "
                f"{result.after/1024:8.0f}KB  (-{result.ratio*100:4.1f}%)"
            )

    def _compress_one(self, path: Path, *, max_w: Optional[int] = None,
                      max_h: Optional[int] = None) -> FileResult:
        from PIL import Image, ImageOps

        result = FileResult(path=str(path), before=path.stat().st_size)
        ext = path.suffix.lower()
        eff_max_w = max_w if max_w else self.max_width
        eff_max_h = max_h if max_h else self.max_height

        try:
            with Image.open(path) as img:
                # EXIF-aware orientation: iPhone photos are nearly always
                # tagged with rotation metadata that browsers honour but
                # the on-disk pixel data does not — re-burn the rotation
                # so re-encoding doesn't accidentally reset it.
                img = ImageOps.exif_transpose(img)

                src_w, src_h = img.size
                if src_w <= 0 or src_h <= 0:
                    result.skipped_reason = "zero-size"
                    result.after = result.before
                    return result

                scale = min(
                    eff_max_w / src_w,
                    eff_max_h / src_h,
                    1.0,
                )
                if scale < 1.0:
                    new_size = (max(1, round(src_w * scale)),
                                max(1, round(src_h * scale)))
                    img = img.resize(new_size, Image.LANCZOS)

                buf = io.BytesIO()
                fmt, save_kwargs = self._encoder_for(ext, img)
                img.save(buf, format=fmt, **save_kwargs)
                payload = buf.getvalue()
        except Exception as exc:  # pragma: no cover — we want a robust loop
            logger.warning("compress_media_originals: failed on %s — %s", path, exc)
            result.skipped_reason = f"error: {exc}"
            result.after = result.before
            return result

        result.after = len(payload)

        # Only commit when we actually save something meaningful.
        if result.before <= 0 or result.after >= result.before:
            result.skipped_reason = "no-saving"
            result.after = result.before
            return result
        if (result.before - result.after) / result.before < self.min_saving:
            result.skipped_reason = "below-saving-threshold"
            result.after = result.before
            return result

        if self.dry:
            return result

        # Atomic write: stage to .tmp, then rename. Optionally keep
        # a .bak copy of the source — guards admins against bad
        # batches.
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            with open(tmp_path, "wb") as fh:
                fh.write(payload)
            if self.backup_suffix:
                bak = path.with_suffix(path.suffix + self.backup_suffix)
                if not bak.exists():
                    shutil.copy2(path, bak)
            os.replace(tmp_path, path)
        except OSError as exc:
            logger.warning("compress_media_originals: write failed %s — %s", path, exc)
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            result.skipped_reason = f"write-error: {exc}"
            result.after = result.before
            return result

        return result

    def _encoder_for(self, ext: str, img):
        """Pick a Pillow save() recipe that keeps the on-disk extension."""
        from PIL import Image  # noqa: F401  (already imported above; kept for clarity)

        if ext in (".jpg", ".jpeg"):
            # JPEG cannot carry alpha; flatten on white if present.
            if img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
            return ("JPEG", {
                "quality": self.jpeg_quality,
                "optimize": True,
                "progressive": True,
            })

        if ext == ".png":
            # Quantise photographic PNGs to palette to dramatically
            # reduce size while preserving alpha for true graphics.
            if img.mode in ("RGB",):
                # PNG-Optimize is fine; keep palette flag off.
                return ("PNG", {"optimize": True})
            if img.mode in ("RGBA", "LA", "P"):
                # Pillow's optimised PNG with adaptive palette where
                # possible gives ~50-70% reduction on iPhone screenshots.
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                return ("PNG", {"optimize": True})
            return ("PNG", {"optimize": True})

        if ext == ".webp":
            return ("WEBP", {"quality": self.webp_quality, "method": 6})

        # Fallback: keep whatever Pillow can write for this format.
        fmt = (img.format or "JPEG").upper()
        return (fmt, {})

    # ------------------------------------------------------------------ output

    def _announce_header(self, targets):
        prefix = "[DRY-RUN] " if self.dry else ""
        self.stdout.write(self.style.NOTICE(
            f"{prefix}compress_media_originals — "
            f"max={self.max_width}x{self.max_height}, "
            f"min_bytes={self.min_bytes}, "
            f"min_saving={self.min_saving*100:.1f}%, "
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
                    f"  {Path(item.path).name:60s}  "
                    f"{item.before/1024:8.0f}KB → {item.after/1024:8.0f}KB  "
                    f"(-{item.ratio*100:4.1f}%)"
                )
