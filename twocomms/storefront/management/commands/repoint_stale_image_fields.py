"""SEO/Performance v1.0 Phase 11 — fix stale ImageField pointers post-WebP swap.

Why: ``convert_originals_to_webp`` rewrites the ``ImageField.name`` of
the model that *owns* the file via ``upload_to`` — but the storefront
schema lets a ``Product.main_image`` (with ``upload_to='products/'``)
hold a value like ``product_colors/<chat-gpt-export>.png``. That is a
cross-table pointer: the file physically lives in
``/media/product_colors/`` (managed by ``ProductColorImage``), but a
second model (``Product``) also references it directly so the
homepage card can be set to a colour-variant photo from the admin.

When the WebP migration touches ``ProductColorImage.image`` it
correctly renames the file to ``.webp`` and updates *that* model's
row, but ``Product.main_image`` still holds the dead ``.png``
string. The card template tries to load ``/media/product_colors/X
.png`` → 404 → blank thumbnail on the homepage.

This command audits every concrete ``FileField`` across every model.
For each row whose stored name still ends in ``.png/.jpg/.jpeg``
**but** whose ``.webp`` sibling exists on disk *and* the original
file no longer does, we issue a single ``UPDATE`` swapping the
extension. Idempotent — already-webp pointers are skipped.

Usage:
    python manage.py repoint_stale_image_fields                # dry-run
    python manage.py repoint_stale_image_fields --apply        # commit
    python manage.py repoint_stale_image_fields --models storefront.Product.main_image
"""
from __future__ import annotations

import os
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import FileField


class Command(BaseCommand):
    help = "Repoint ImageField/FileField rows from stale .png/.jpg to existing .webp."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Actually write changes (default: dry-run).")
        parser.add_argument("--models", nargs="+", default=None,
                            help="Restrict to <app>.<model>.<field> selectors.")

    def handle(self, *args, **opts):
        apply = bool(opts["apply"])
        wanted = set(opts["models"] or [])

        media_root = Path(getattr(settings, "MEDIA_ROOT", "")).resolve()
        if not media_root or not media_root.is_dir():
            self.stderr.write(self.style.ERROR(
                f"MEDIA_ROOT invalid: {media_root!r}"))
            return

        targets = []
        for model in apps.get_models():
            if model._meta.abstract or model._meta.proxy:
                continue
            for field in model._meta.get_fields():
                if not isinstance(field, FileField):
                    continue
                selector = (
                    f"{model._meta.app_label}.{model.__name__}.{field.name}"
                )
                if wanted and selector not in wanted:
                    continue
                targets.append((model, field))

        prefix = "" if apply else "[DRY-RUN] "
        self.stdout.write(self.style.NOTICE(
            f"{prefix}Auditing {len(targets)} FileField targets…"))

        fixed_total = 0
        for model, field in targets:
            fname = field.name
            try:
                rows = list(
                    model.objects
                    .exclude(**{f"{fname}": ""})
                    .only("id", fname)
                )
            except Exception as exc:
                self.stdout.write(self.style.WARNING(
                    f"  skip {model.__name__}.{fname}: {exc}"))
                continue
            for inst in rows:
                v = getattr(inst, fname, None)
                if not v or not getattr(v, "name", ""):
                    continue
                name = v.name
                stem, ext = os.path.splitext(name)
                if ext.lower() not in (".png", ".jpg", ".jpeg"):
                    continue
                webp_rel = f"{stem}.webp"
                old_abs = media_root / name
                new_abs = media_root / webp_rel
                if not new_abs.is_file():
                    continue
                if old_abs.is_file():
                    # Both files exist — refuse to swap automatically.
                    # The .webp is probably an opt-in copy that the
                    # admin uploaded manually, not the result of the
                    # WebP migration.
                    continue
                fixed_total += 1
                self.stdout.write(
                    f"  {model._meta.app_label}.{model.__name__}.{fname} "
                    f"pk={inst.pk}: {name} → {webp_rel}"
                )
                if apply:
                    model.objects.filter(pk=inst.pk).update(
                        **{fname: webp_rel}
                    )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Repointed: {fixed_total} rows."
        ))
        if not apply and fixed_total:
            self.stdout.write(self.style.NOTICE(
                "Run with --apply to commit."))
