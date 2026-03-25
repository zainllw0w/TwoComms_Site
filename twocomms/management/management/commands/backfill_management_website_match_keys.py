from django.core.management.base import BaseCommand

from management.models import Client, ManagementLead, normalize_website_for_match


class Command(BaseCommand):
    help = "Backfill website_match_key for management Client and ManagementLead records."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=500, help="Rows per DB iterator batch.")
        parser.add_argument("--limit", type=int, default=0, help="Optional max rows per model.")
        parser.add_argument("--dry-run", action="store_true", help="Only count affected rows without saving.")

    def handle(self, *args, **options):
        batch_size = max(1, int(options["batch_size"] or 500))
        limit = max(0, int(options["limit"] or 0))
        dry_run = bool(options["dry_run"])

        client_count = self._backfill_queryset(
            queryset=Client.objects.only("id", "website_url", "website_match_key").order_by("id"),
            batch_size=batch_size,
            limit=limit,
            dry_run=dry_run,
        )
        lead_count = self._backfill_queryset(
            queryset=ManagementLead.objects.only("id", "website_url", "website_match_key").order_by("id"),
            batch_size=batch_size,
            limit=limit,
            dry_run=dry_run,
        )

        mode = "dry-run" if dry_run else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"website_match_key {mode}: clients={client_count}, leads={lead_count}"
            )
        )

    def _backfill_queryset(self, *, queryset, batch_size: int, limit: int, dry_run: bool) -> int:
        updated = 0
        processed = 0
        pending = []

        for obj in queryset.iterator(chunk_size=batch_size):
            if limit and processed >= limit:
                break
            processed += 1
            normalized = normalize_website_for_match(obj.website_url)
            if normalized == (obj.website_match_key or ""):
                continue
            updated += 1
            if dry_run:
                continue
            obj.website_match_key = normalized
            pending.append(obj)
            if len(pending) >= batch_size:
                queryset.model.objects.bulk_update(pending, ["website_match_key"], batch_size=batch_size)
                pending = []

        if pending and not dry_run:
            queryset.model.objects.bulk_update(pending, ["website_match_key"], batch_size=batch_size)
        return updated
