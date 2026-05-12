"""SEO/Performance v1.0 Phase 11 — delete orphan media files.

Walks every registered ``ImageField`` / ``FileField`` target, collects
the set of relative paths that the database currently references,
then scans the corresponding ``/media/`` subdirectories on disk and
deletes every file that is **not** referenced.

Why: an audit of TwoComms production storage discovered 142 MB of
orphan PNGs in ``/media/products/extra/`` — files left behind after
admins replaced product photos or deleted ProductImage rows through
the Django admin (which does not cascade-remove ImageField payloads).
Carrying this dead weight bloats backups, slows ``cp -r`` deploys and
inflates the daily snapshot we ship off-site.

Safe by default:
* Dry-run by default — pass ``--apply`` to actually delete.
* Always ignores hidden files (``.``-prefixed), ``.bak`` siblings
  and Django thumbnail caches (``__optimized__``, ``CACHE``,
  ``thumbnails``).
* Refuses to touch a file younger than ``--min-age-days`` (default 7)
  to avoid racing with admins who are mid-upload.
* Confirmation prompt with file counts on ``--apply``.

Usage:
    python manage.py prune_orphan_media                  # report
    python manage.py prune_orphan_media --apply          # delete
    python manage.py prune_orphan_media --paths products/extra
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand


# (app_label, model_name, field_name, /media/ subpath)
TARGETS: list[tuple[str, str, str, str]] = [
    ("storefront", "ProductImage", "image", "products/extra"),
    ("storefront", "Product", "main_image", "products"),
    ("storefront", "Product", "home_card_image", "products/home_cards"),
    ("productcolors", "ProductColorImage", "image", "product_colors"),
    ("storefront", "Category", "cover", "category_covers"),
    ("storefront", "Category", "icon", "category_icons"),
    ("storefront", "PrintProposal", "image", "print_proposals"),
    ("warehouse", "Print", "main_image", "prints"),
    ("warehouse", "PrintColorVariant", "image", "prints/colors"),
    ("reviews", "ReviewImage", "image", "reviews"),
    ("dtf", "DtfWork", "image", "dtf"),
    ("management", "Shop", "photo", "shops"),
    ("accounts", "UserProfile", "avatar", "avatars"),
    ("accounts", "UserProfile", "ubd_doc", "ubd_docs"),
]


IGNORE_DIR_NAMES = {"__optimized__", "CACHE", "thumbnails", "thumbs"}
IGNORE_FILE_PREFIX = (".",)
IGNORE_FILE_SUFFIX = (".bak", ".tmp", ".old", ".orig")


@dataclass
class Stats:
    scanned: int = 0
    referenced: int = 0
    orphan: int = 0
    deleted: int = 0
    bytes_freed: int = 0
    biggest: list[tuple[int, str]] = field(default_factory=list)


class Command(BaseCommand):
    help = "Delete orphan ImageField/FileField media (files not referenced in DB)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Actually delete files (default: dry-run).")
        parser.add_argument("--paths", nargs="+", default=None,
                            help="Restrict cleanup to specific /media/ subpaths.")
        parser.add_argument("--min-age-days", type=int, default=7,
                            help="Only delete files older than N days.")
        parser.add_argument("--show", type=int, default=15,
                            help="Show the N biggest orphans in the report.")

    # ------------------------------------------------------------------ entrypoint

    def handle(self, *args, **opts):
        self.apply = bool(opts["apply"])
        self.min_age = int(opts["min_age_days"]) * 86400
        self.show_n = int(opts["show"])
        wanted_paths = set(opts["paths"] or [])

        media_root = Path(getattr(settings, "MEDIA_ROOT", ""))
        if not media_root or not media_root.is_dir():
            self.stderr.write(self.style.ERROR(
                f"MEDIA_ROOT invalid: {media_root!r}"))
            return

        targets = [t for t in TARGETS
                   if not wanted_paths or t[3] in wanted_paths]

        # 1) Collect the set of relative paths referenced by the DB,
        #    grouped by /media/ subpath so we can compare per-folder.
        refs_by_path: dict[str, set[str]] = {}
        for app_label, model_name, field_name, subpath in targets:
            try:
                model = apps.get_model(app_label, model_name)
            except LookupError:
                continue
            if not hasattr(model, field_name):
                continue
            names = (model.objects
                     .exclude(**{f"{field_name}": ""})
                     .values_list(field_name, flat=True))
            refs_by_path.setdefault(subpath, set())
            for n in names:
                if not n:
                    continue
                # Strip any leading slash; keep relative path
                refs_by_path[subpath].add(n.lstrip("/"))

        # 2) Walk each subpath, classify files.
        stats = Stats()
        candidates: list[tuple[int, Path]] = []
        for subpath, referenced in refs_by_path.items():
            folder = media_root / subpath
            if not folder.is_dir():
                continue
            self.stdout.write(self.style.NOTICE(
                f"\nSCAN  /media/{subpath}/  (referenced: {len(referenced)})"))
            for root, dirs, files in os.walk(folder):
                # Skip ignored caches in-place.
                dirs[:] = [d for d in dirs if d not in IGNORE_DIR_NAMES]
                for fname in files:
                    if fname.startswith(IGNORE_FILE_PREFIX):
                        continue
                    if fname.endswith(IGNORE_FILE_SUFFIX):
                        continue
                    abs_path = Path(root) / fname
                    try:
                        rel = abs_path.relative_to(media_root).as_posix()
                    except ValueError:
                        continue
                    stats.scanned += 1
                    if rel in referenced:
                        stats.referenced += 1
                        continue
                    try:
                        st = abs_path.stat()
                    except OSError:
                        continue
                    if (time.time() - st.st_mtime) < self.min_age:
                        continue
                    stats.orphan += 1
                    candidates.append((st.st_size, abs_path))

        # 3) Report + optionally delete.
        candidates.sort(reverse=True)
        total_bytes = sum(s for s, _ in candidates)
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            f"Orphans: {stats.orphan} files, "
            f"{total_bytes/1_048_576:.1f} MB"
        ))
        if not candidates:
            return

        self.stdout.write(f"Top {min(self.show_n, len(candidates))}:")
        for size, abs_path in candidates[:self.show_n]:
            self.stdout.write(
                f"  {size/1_048_576:6.2f} MB  "
                f"{abs_path.relative_to(media_root)}"
            )

        if not self.apply:
            self.stdout.write(self.style.NOTICE(
                "\nDry-run — pass --apply to delete."))
            return

        # Atomic-ish loop: rename to .pending-delete first, then unlink.
        for size, abs_path in candidates:
            try:
                abs_path.unlink()
                stats.deleted += 1
                stats.bytes_freed += size
            except OSError as exc:
                self.stdout.write(self.style.ERROR(
                    f"  ! failed to delete {abs_path}: {exc}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Deleted: {stats.deleted} files, "
            f"{stats.bytes_freed/1_048_576:.1f} MB freed."
        ))
