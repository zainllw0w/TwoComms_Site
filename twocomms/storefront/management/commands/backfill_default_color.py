"""Backfill a default ``ProductColorVariant`` for products that have none.

Many legacy products predate the colour-variant feature and live in the
DB without a single ``ProductColorVariant`` row. The Phase 9 catalog
colour filter joins through ``color_variants`` so those products are
invisible whenever any colour chip is selected — even users who explicitly
filter "Чорний" (the most common base colour) cannot see them.

This command repairs the data: for every published product that has zero
``ProductColorVariant`` rows, it creates one row pointing to the existing
"Чорний" ``Color`` (primary_hex ``#000000``) and marks it as the default.
The variant has no images attached — catalog cards / PDP gallery fall
back to ``product.main_image`` cleanly (existing behaviour for products
whose default variant is image-less).

The command is idempotent: re-running it is a no-op for products that
already have any variant. Use ``--dry-run`` to inspect changes first.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count

from productcolors.models import Color, ProductColorVariant
from storefront.models import Product


BLACK_HEX = "#000000"
BLACK_NAME_HINTS = ("чорн", "black")


class Command(BaseCommand):
    help = (
        "Створити для опублікованих товарів без color_variants дефолтний "
        "ProductColorVariant із кольором 'Чорний' — щоб вони були видимі "
        "за фільтром ?color=black."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показати, що буде створено, без запису в БД.",
        )
        parser.add_argument(
            "--include-drafts",
            action="store_true",
            help=(
                "Заповнити також для status != 'published' "
                "(за замовчуванням торкаємось лише published)."
            ),
        )

    def _resolve_black_color(self):
        # Prefer an exact hex match; fall back to a name lookup so the
        # command works even on installations where the canonical
        # "Чорний" row was created with the colour code in upper case
        # or with stray whitespace. The fallback uses a Python-side
        # case-fold compare because SQLite (used in tests) does not
        # case-fold Cyrillic characters via ``__icontains`` — Postgres
        # (production) does, but we want consistent semantics so the
        # command's behaviour can be validated by unit tests.
        color = Color.objects.filter(primary_hex__iexact=BLACK_HEX).order_by("id").first()
        if color is not None:
            return color
        all_colors = list(Color.objects.all().order_by("id"))
        for hint in BLACK_NAME_HINTS:
            hint_lc = hint.lower()
            for candidate in all_colors:
                if hint_lc in (candidate.name or "").lower():
                    return candidate
        return None

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        include_drafts: bool = options["include_drafts"]

        black = self._resolve_black_color()
        if black is None:
            raise CommandError(
                "У БД немає кольору з primary_hex='#000000' або з назвою 'Чорний'. "
                "Створіть його через адмін-панель Color і перезапустіть."
            )

        products_qs = Product.objects.all()
        if not include_drafts:
            products_qs = products_qs.filter(status="published")

        # Annotate so we touch only products without any variant rows.
        candidates = list(
            products_qs.annotate(c=Count("color_variants"))
            .filter(c=0)
            .order_by("id")
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Знайдено {len(candidates)} товарів без color_variants "
                f"(колір за замовчуванням: id={black.id}, name={black.name!r})."
            )
        )

        if not candidates:
            self.stdout.write(self.style.SUCCESS("Нічого робити, виходимо."))
            return

        created = 0
        with transaction.atomic():
            for product in candidates:
                if dry_run:
                    self.stdout.write(
                        f"  [dry-run] {product.id:4d}  {product.slug!r:40s}  {product.title[:60]}"
                    )
                    continue
                # Re-check inside the transaction to guard against a
                # concurrent admin save creating a variant between the
                # initial query and this insert.
                if ProductColorVariant.objects.filter(product=product).exists():
                    continue
                variant = ProductColorVariant(
                    product=product,
                    color=black,
                    is_default=True,
                    order=0,
                )
                # ``ProductColorVariant.save`` auto-generates the ``slug``
                # field via ``_generate_url_slug`` (will resolve to
                # ``black`` for the canonical "Чорний" colour). We don't
                # set it explicitly so the dedup logic in the model can
                # still kick in if the slug is somehow taken.
                variant.save()
                created += 1
                self.stdout.write(
                    f"  + {product.id:4d}  {product.slug!r:40s}  -> variant id={variant.id} slug={variant.slug!r}"
                )

            if dry_run:
                # Force rollback even though we never wrote anything;
                # explicit raise keeps test assertions readable.
                transaction.set_rollback(True)

        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run: жодних змін не збережено."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Створено {created} нових ProductColorVariant."))
