import hashlib
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.ig_bot_models import IgPaymentProjection
from management.models import (
    IgCheckoutInventoryReservation,
    IgCheckoutProposal,
    IgCheckoutProposalItem,
    IgClient,
    IgDeal,
    IgLifecycleEvent,
    IgOrderAttribution,
)
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from management.services.ig_order_assignments import link_order_to_client
from storefront.models import Category, Product
from productcolors.models import Color, ProductColorVariant
from orders.models import Order, PaymentAttempt


class InstagramCheckoutReconciliationTests(TestCase):
    def setUp(self):
        self.client = IgClient.get_or_create_for_sender("ig-reconcile")
        self.deal = IgDeal.objects.create(
            client=self.client,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("900.00"),
            requested_payment_amount=Decimal("900.00"),
        )
        self.episode = ensure_episode_for_deal(self.deal)
        category = Category.objects.create(name="Reconcile", slug="ig-reconcile")
        self.product = Product.objects.create(
            title="Reconcile shirt",
            slug="ig-reconcile-shirt",
            category=category,
            price=Decimal("900.00"),
            status="published",
        )
        self.proposal = IgCheckoutProposal.objects.create_current(
            deal=self.deal,
            commercial_episode=self.episode,
            catalog_total=Decimal("900.00"),
            quoted_total=Decimal("900.00"),
            requested_payment_amount=Decimal("900.00"),
            items_digest=hashlib.sha256(b"reconcile").hexdigest(),
        )
        self.item = IgCheckoutProposalItem.objects.create(
            proposal=self.proposal,
            product=self.product,
            product_title=self.product.title,
            quantity=1,
            catalog_unit_price=Decimal("900.00"),
            catalog_line_total=Decimal("900.00"),
            quoted_unit_price=Decimal("900.00"),
            quoted_line_total=Decimal("900.00"),
        )

    def _bind_paid_delivered_order(self):
        order = Order.objects.create(
            full_name="Delivered Buyer",
            phone="+380501112299",
            city="Kyiv",
            np_office="Branch 9",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("900.00"),
        )
        Order.objects.filter(pk=order.pk).update(
            status="done",
            tracking_number="20450000000009",
            shipment_status="Отримано",
            tracking_status_code=9,
            tracking_terminal_at=timezone.now(),
            payment_payload={
                "np_tracking": {
                    "last_status_code": "9",
                    "last_status_text": "Отримано",
                },
            },
        )
        order.refresh_from_db()
        attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"paid-delivered-attempt").hexdigest(),
            full_name=order.full_name,
            phone=order.phone,
            city=order.city,
            np_office=order.np_office,
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.CONVERTED,
            cart_snapshot={"checkout_surface": "instagram_proposal", "cart": []},
            gross_amount=Decimal("900.00"),
            payable_amount=Decimal("900.00"),
            payment_amount=Decimal("900.00"),
            paid_amount=Decimal("900.00"),
            order=order,
        )
        self.proposal.payment_attempt = attempt
        self.proposal.status = IgCheckoutProposal.Status.PAID
        self.proposal.paid_at = timezone.now()
        self.proposal.save(update_fields=[
            "payment_attempt", "status", "paid_at", "updated_at",
        ])
        IgOrderAttribution.objects.create(
            order=order,
            client=self.client,
            deal=self.deal,
            creation_mode="provider_auto",
            payment_source="provider_attempt",
        )
        link_order_to_client(order, client=self.client)
        IgPaymentProjection.objects.create(
            deal=self.deal,
            client=self.client,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=order.total_sum,
            paid_at=self.deal.paid_at,
        )
        from management.services.ig_lifecycle import ensure_lifecycle_event

        event, created = ensure_lifecycle_event(
            order,
            IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
            payload={
                "attempt_id": attempt.pk,
                "attempt_reference": attempt.reference,
                "amount": "900.00",
                "currency": self.proposal.currency,
            },
        )
        self.assertIsNotNone(event)
        self.assertTrue(created)
        return order

    @patch("management.services.ig_lifecycle.dispatch_lifecycle_event")
    def test_paid_delivered_truth_repairs_missing_fulfillment_events_idempotently(
        self,
        dispatch_lifecycle_event,
    ):
        order = self._bind_paid_delivered_order()

        from management.services.ig_checkout_reconciliation import reconcile_ig_checkout

        first = reconcile_ig_checkout(limit=20, pull_ambiguous=False)
        second = reconcile_ig_checkout(limit=20, pull_ambiguous=False)

        self.assertEqual(first.get("ttn_events"), 1, first)
        self.assertEqual(first.get("delivery_events"), 1, first)
        self.assertEqual(second.get("ttn_events"), 0, second)
        self.assertEqual(second.get("delivery_events"), 0, second)
        self.assertEqual(
            IgLifecycleEvent.objects.filter(
                order=order,
                kind=IgLifecycleEvent.Kind.TTN_CREATED,
            ).count(),
            1,
        )
        self.assertEqual(
            IgLifecycleEvent.objects.filter(
                order=order,
                kind=IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            ).count(),
            1,
        )
        ttn_event = IgLifecycleEvent.objects.get(
            order=order,
            kind=IgLifecycleEvent.Kind.TTN_CREATED,
        )
        delivery_event = IgLifecycleEvent.objects.get(
            order=order,
            kind=IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
        )
        self.assertEqual(ttn_event.payload["tracking_number"], order.tracking_number)
        self.assertEqual(delivery_event.payload["status_code"], "9")
        dispatch_lifecycle_event.assert_not_called()

    def test_cancelled_lifecycle_generations_are_recreated_once(self):
        order = self._bind_paid_delivered_order()
        from management.services.ig_lifecycle import ensure_lifecycle_event

        payment_event = IgLifecycleEvent.objects.get(
            order=order,
            kind=IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
        )
        payment_event.state = IgLifecycleEvent.State.CANCELLED
        payment_event.last_error = "payment_not_verified"
        payment_event.save(update_fields=["state", "last_error", "updated_at"])
        kinds_and_payloads = (
            (
                IgLifecycleEvent.Kind.TTN_CREATED,
                {
                    "tracking_number": order.tracking_number,
                    "order_number": order.order_number,
                },
            ),
            (
                IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
                {
                    "status_code": str(order.tracking_status_code),
                    "status": order.shipment_status,
                    "tracking_number": order.tracking_number,
                    "tracking_terminal_at": order.tracking_terminal_at.isoformat(),
                },
            ),
        )
        cancelled = [payment_event]
        for kind, payload in kinds_and_payloads:
            event, created = ensure_lifecycle_event(order, kind, payload=payload)
            self.assertTrue(created)
            event.state = IgLifecycleEvent.State.CANCELLED
            event.last_error = (
                "tracking_number_changed"
                if kind == IgLifecycleEvent.Kind.TTN_CREATED
                else "carrier delivery not confirmed"
            )
            event.save(update_fields=["state", "last_error", "updated_at"])
            cancelled.append(event)

        from management.services.ig_checkout_reconciliation import reconcile_ig_checkout

        first = reconcile_ig_checkout(limit=20, pull_ambiguous=False)
        second = reconcile_ig_checkout(limit=20, pull_ambiguous=False)

        self.assertEqual(first["payment_events"], 1, first)
        self.assertEqual(first["ttn_events"], 1, first)
        self.assertEqual(first["delivery_events"], 1, first)
        self.assertEqual(second["payment_events"], 0, second)
        self.assertEqual(second["ttn_events"], 0, second)
        self.assertEqual(second["delivery_events"], 0, second)
        for original in cancelled:
            events = IgLifecycleEvent.objects.filter(
                event_key__startswith=f"{original.event_key}:retry:"
            )
            self.assertEqual(events.count(), 1)
            self.assertNotEqual(events.get().state, IgLifecycleEvent.State.CANCELLED)

    @patch("management.services.ig_lifecycle.dispatch_lifecycle_event")
    def test_manual_done_without_carrier_delivery_does_not_repair_delivery_event(
        self,
        dispatch_lifecycle_event,
    ):
        order = self._bind_paid_delivered_order()
        Order.objects.filter(pk=order.pk).update(
            tracking_status_code=7,
            tracking_terminal_at=None,
        )

        from management.services.ig_checkout_reconciliation import reconcile_ig_checkout

        result = reconcile_ig_checkout(limit=20, pull_ambiguous=False)

        self.assertEqual(result.get("ttn_events"), 1, result)
        self.assertEqual(result.get("delivery_events"), 0, result)
        self.assertFalse(
            IgLifecycleEvent.objects.filter(
                order=order,
                kind=IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            ).exists()
        )
        dispatch_lifecycle_event.assert_not_called()

    @patch("management.services.ig_lifecycle.dispatch_lifecycle_event")
    def test_paid_delivered_dry_run_reports_missing_events_without_writes(
        self,
        dispatch_lifecycle_event,
    ):
        order = self._bind_paid_delivered_order()

        from management.services.ig_checkout_reconciliation import reconcile_ig_checkout

        result = reconcile_ig_checkout(
            limit=20,
            pull_ambiguous=False,
            dry_run=True,
        )

        self.assertEqual(result.get("ttn_events"), 1, result)
        self.assertEqual(result.get("delivery_events"), 1, result)
        self.assertFalse(
            IgLifecycleEvent.objects.filter(
                order=order,
                kind__in=[
                    IgLifecycleEvent.Kind.TTN_CREATED,
                    IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
                ],
            ).exists()
        )
        dispatch_lifecycle_event.assert_not_called()

    def test_expired_proposal_and_reservation_are_released_idempotently(self):
        reservation = IgCheckoutInventoryReservation.objects.create(
            proposal=self.proposal,
            item=self.item,
            product=self.product,
            quantity=1,
            reservation_fingerprint=hashlib.sha256(b"expired-reservation").hexdigest(),
            expires_at=timezone.now(),
        )
        self.proposal.expires_at = timezone.now()
        self.proposal.save(update_fields=["expires_at", "updated_at"])

        from management.services.ig_checkout_reconciliation import reconcile_ig_checkout

        first = reconcile_ig_checkout(limit=20, pull_ambiguous=False)
        second = reconcile_ig_checkout(limit=20, pull_ambiguous=False)

        self.proposal.refresh_from_db()
        reservation.refresh_from_db()
        self.assertEqual(self.proposal.status, IgCheckoutProposal.Status.EXPIRED)
        self.assertEqual(reservation.state, IgCheckoutInventoryReservation.State.RELEASED)
        self.assertEqual(first["expired_proposals"], 1)
        self.assertGreaterEqual(first["released_reservations"], 1)
        self.assertEqual(second["expired_proposals"], 0)
        self.assertEqual(second["released_reservations"], 0)

    def test_dry_run_reports_expiry_without_writes_or_provider_calls(self):
        reservation = IgCheckoutInventoryReservation.objects.create(
            proposal=self.proposal,
            item=self.item,
            product=self.product,
            quantity=1,
            reservation_fingerprint=hashlib.sha256(b"dry-run-reservation").hexdigest(),
            expires_at=timezone.now(),
        )
        self.proposal.expires_at = timezone.now()
        self.proposal.save(update_fields=["expires_at", "updated_at"])

        from management.services.ig_checkout_reconciliation import reconcile_ig_checkout

        result = reconcile_ig_checkout(limit=20, pull_ambiguous=True, dry_run=True)

        self.proposal.refresh_from_db()
        reservation.refresh_from_db()
        self.assertEqual(self.proposal.status, IgCheckoutProposal.Status.READY)
        self.assertEqual(reservation.state, IgCheckoutInventoryReservation.State.ACTIVE)
        self.assertEqual(result["expired_proposals"], 1)
        self.assertEqual(result["released_reservations"], 1)

    def test_expired_unclaimed_details_lock_releases_attempt_and_active_pointer(self):
        attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"unclaimed-details-lock").hexdigest(),
            full_name="Instagram Buyer",
            phone="+380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.INITIATED,
            cart_snapshot={"checkout_surface": "instagram_proposal", "cart": []},
            gross_amount=Decimal("900.00"),
            payable_amount=Decimal("900.00"),
            payment_amount=Decimal("900.00"),
        )
        reservation = IgCheckoutInventoryReservation.objects.create(
            proposal=self.proposal,
            item=self.item,
            product=self.product,
            quantity=1,
            reservation_fingerprint=hashlib.sha256(b"unclaimed-reservation").hexdigest(),
            expires_at=timezone.now(),
        )
        self.proposal.payment_attempt = attempt
        self.proposal.status = IgCheckoutProposal.Status.DETAILS_LOCKED
        self.proposal.details_locked_at = timezone.now()
        self.proposal.expires_at = timezone.now()
        self.proposal.save(update_fields=[
            "payment_attempt", "status", "details_locked_at", "expires_at", "updated_at",
        ])

        from management.services.ig_checkout_reconciliation import reconcile_ig_checkout

        result = reconcile_ig_checkout(limit=20, pull_ambiguous=False)

        attempt.refresh_from_db()
        reservation.refresh_from_db()
        self.proposal.refresh_from_db()
        self.deal.refresh_from_db()
        self.assertEqual(result["expired_proposals"], 1)
        self.assertEqual(attempt.status, PaymentAttempt.Status.EXPIRED)
        self.assertEqual(self.proposal.status, IgCheckoutProposal.Status.EXPIRED)
        self.assertIsNone(self.deal.active_checkout_proposal_id)
        self.assertEqual(reservation.state, IgCheckoutInventoryReservation.State.RELEASED)

    def test_reconciliation_prioritizes_repairable_rows_over_permanent_ambiguity(self):
        ambiguous_attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"ambiguous-starvation").hexdigest(),
            full_name="Instagram Buyer",
            phone="+380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.PROCESSING,
            cart_snapshot={"checkout_surface": "instagram_proposal", "cart": []},
            gross_amount=Decimal("900.00"),
            payable_amount=Decimal("900.00"),
            payment_amount=Decimal("900.00"),
            event_state={"invoice_creation_ambiguous": True},
        )
        self.proposal.payment_attempt = ambiguous_attempt
        self.proposal.status = IgCheckoutProposal.Status.INVOICE_CREATED
        self.proposal.save(update_fields=["payment_attempt", "status", "updated_at"])

        bound_client = IgClient.get_or_create_for_sender("ig-reconcile-bound")
        bound_deal = IgDeal.objects.create(
            client=bound_client,
            status=IgDeal.Status.AWAITING_PAYMENT,
            amount=Decimal("900.00"),
            requested_payment_amount=Decimal("900.00"),
        )
        bound_episode = ensure_episode_for_deal(bound_deal)
        bound_proposal = IgCheckoutProposal.objects.create_current(
            deal=bound_deal,
            commercial_episode=bound_episode,
            catalog_total=Decimal("900.00"),
            quoted_total=Decimal("900.00"),
            requested_payment_amount=Decimal("900.00"),
            items_digest=hashlib.sha256(b"repairable-row").hexdigest(),
            status=IgCheckoutProposal.Status.DETAILS_LOCKED,
        )
        bound_order = Order.objects.create(
            full_name="Bound Buyer",
            phone="+380501112244",
            city="Kyiv",
            np_office="Branch 2",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("900.00"),
        )
        bound_attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"repairable-attempt").hexdigest(),
            full_name="Bound Buyer",
            phone="+380501112244",
            city="Kyiv",
            np_office="Branch 2",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.CONVERTED,
            cart_snapshot={"checkout_surface": "instagram_proposal", "cart": []},
            gross_amount=Decimal("900.00"),
            payable_amount=Decimal("900.00"),
            payment_amount=Decimal("900.00"),
            paid_amount=Decimal("900.00"),
            order=bound_order,
        )
        bound_proposal.payment_attempt = bound_attempt
        bound_proposal.save(update_fields=["payment_attempt", "updated_at"])

        from management.services.ig_checkout_reconciliation import reconcile_ig_checkout

        result = reconcile_ig_checkout(limit=1, pull_ambiguous=False)

        bound_proposal.refresh_from_db()
        self.assertEqual(result["bound_attempts"], 1, result)
        self.assertEqual(bound_proposal.status, IgCheckoutProposal.Status.PAID)
        ambiguous_attempt.refresh_from_db()
        self.assertTrue((ambiguous_attempt.event_state or {}).get("invoice_creation_ambiguous"))

    def test_released_catalog_reservation_without_payment_time_requires_review(self):
        color = Color.objects.create(name="Blue", primary_hex="#2244AA")
        variant = ProductColorVariant.objects.create(
            product=self.product,
            color=color,
            stock=1,
            sku="REC-BLUE",
        )
        self.item.color_variant = variant
        self.item.save(update_fields=["color_variant"])
        reservation = IgCheckoutInventoryReservation.objects.create(
            proposal=self.proposal,
            item=self.item,
            product=self.product,
            color_variant=variant,
            quantity=1,
            reservation_fingerprint=hashlib.sha256(b"released-late-success").hexdigest(),
            state=IgCheckoutInventoryReservation.State.RELEASED,
            release_reason="expired",
            released_at=timezone.now(),
            expires_at=timezone.now(),
        )

        from management.services.ig_inventory import consume_proposal_inventory

        self.assertEqual(consume_proposal_inventory(self.proposal), 1)
        variant.refresh_from_db()
        reservation.refresh_from_db()
        self.assertEqual(variant.stock, 1)
        self.assertEqual(
            reservation.state,
            IgCheckoutInventoryReservation.State.OVERBOOKED_REVIEW,
        )
        self.assertEqual(consume_proposal_inventory(self.proposal), 0)
