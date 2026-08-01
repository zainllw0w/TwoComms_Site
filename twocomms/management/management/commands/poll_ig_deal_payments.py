"""Backstop-поллінг статусів оплати угод IG-бота (якщо вебхук Monobank не дійшов).

Запуск кроном кожні кілька хвилин:
    python manage.py poll_ig_deal_payments
"""
from django.core.management.base import BaseCommand

from management.services import bot_payments


class Command(BaseCommand):
    help = "Поллінг угод IG-бота у статусі awaiting_payment (pull-verify Monobank)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument(
            "--check-only",
            action="store_true",
            help="Count bounded recovery candidates without provider calls, writes, or sends.",
        )

    def handle(self, *args, **opts):
        limit = max(1, min(int(opts.get("limit") or 50), 1000))
        if opts.get("check_only"):
            from management.models import IgDeal, IgPaymentProjection

            def bounded_count(queryset):
                return len(list(queryset.values_list("pk", flat=True)[:limit]))

            projection_candidates = bounded_count(
                IgPaymentProjection.objects.filter(needs_reconciliation=True).order_by(
                    "updated_at", "id"
                )
            )
            provider_candidates = bounded_count(
                IgDeal.objects.filter(status=IgDeal.Status.AWAITING_PAYMENT)
                .exclude(invoice_id="")
                .order_by("id")
            )
            order_candidates = bounded_count(
                IgDeal.objects.filter(status=IgDeal.Status.PAID, order__isnull=True).order_by(
                    "id"
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    "IG payment poll: check_only=true external_calls=0 writes=0 "
                    f"limit={limit} projections={projection_candidates} "
                    f"provider_invoices={provider_candidates} orders={order_candidates}"
                )
            )
            return

        reconciled = bot_payments.reconcile_payment_projections(limit=limit)
        paid = bot_payments.poll_pending_deals(limit=limit)
        # Safety-net: дотворюємо замовлення для оплачених угод з повними даними НП,
        # якщо модель не виставила тег [ORDER].
        from management.services import bot_orders

        fulfilled = bot_orders.fulfill_ready_paid_deals(limit=limit)
        shipped = bot_orders.notify_shipped_deals(limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                f"Звірено проєкцій: {reconciled}; Оплачено угод за цей прогін: {paid}; "
                f"дотворено замовлень: {fulfilled}; "
                f"сповіщень про відправку: {shipped}"
            )
        )
