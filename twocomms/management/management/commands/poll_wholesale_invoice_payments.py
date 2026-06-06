"""
Поллінг статусу оплати накладних менеджерів (фолбек до webhook).

Monobank webhook не гарантований, тож періодично підтягуємо статус
pending-накладних через acquiring-токен (`mono_hrefs`). Ідемпотентно:
apply_payment_status переводить у paid лише раз, комісія — через OneToOne.

Док: twocomms/Management Implementations/04 (4.6) + 09 (9.1).
Cron (рекоменд.): */5 * * * * (flock).
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from management.models import CommandRunLog


class Command(BaseCommand):
    help = "Pulls Monobank status for pending manager wholesale invoices (webhook fallback)."

    def add_arguments(self, parser):
        parser.add_argument("--max-age-days", dest="max_age_days", type=int, default=14,
                            help="Skip invoices whose payment link is older than N days.")
        parser.add_argument("--limit", dest="limit", type=int, default=200)

    def handle(self, *args, **options):
        from orders.models import WholesaleInvoice
        from management.services.invoice_payments import sync_invoice_payment

        max_age_days = options.get("max_age_days") or 14
        limit = options.get("limit") or 200
        now = timezone.now()
        cutoff = now - timedelta(days=max_age_days)

        run_key = f"poll_wholesale_invoice_payments:{now.strftime('%Y%m%d%H%M')}"
        run_log, _ = CommandRunLog.objects.update_or_create(
            run_key=run_key,
            defaults={
                "command_name": "poll_wholesale_invoice_payments",
                "status": CommandRunLog.Status.RUNNING,
                "rows_processed": 0,
                "warnings_count": 0,
                "error_excerpt": "",
                "meta": {},
                "finished_at": None,
            },
        )

        qs = (
            WholesaleInvoice.objects.filter(payment_status="pending")
            .exclude(monobank_invoice_id__isnull=True)
            .exclude(monobank_invoice_id="")
            .filter(created_by__isnull=False)
        )
        # Не пуллимо протухлі (старіші за cutoff і без оновлень) — економимо rate limit.
        qs = qs.filter(payment_link_created_at__gte=cutoff) | qs.filter(payment_link_created_at__isnull=True)
        qs = qs.distinct().order_by("payment_link_created_at")[:limit]

        processed = 0
        paid = 0
        warnings = 0
        try:
            for invoice in qs:
                try:
                    status = sync_invoice_payment(invoice)
                    processed += 1
                    if status and status.strip().lower() in ("success", "hold"):
                        paid += 1
                except Exception as exc:  # одна накладна не валить весь прогін
                    warnings += 1
                    self.stderr.write(f"invoice {invoice.id}: {exc}")
            run_log.meta = {"processed": processed, "paid": paid, "warnings": warnings}
            run_log.save(update_fields=["meta"])
            run_log.mark_finished(
                status=CommandRunLog.Status.SUCCESS if not warnings else CommandRunLog.Status.PARTIAL,
                rows_processed=processed,
                warnings_count=warnings,
            )
        except Exception as exc:
            run_log.mark_finished(
                status=CommandRunLog.Status.FAILED, rows_processed=processed,
                warnings_count=warnings, error_excerpt=str(exc)[:500],
            )
            raise

        self.stdout.write(self.style.SUCCESS(
            f"Polled {processed} pending invoice(s); {paid} confirmed paid; {warnings} warning(s)."
        ))
