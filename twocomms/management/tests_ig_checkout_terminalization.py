"""Regression contract for local assisted-payment terminalization.

These tests deliberately avoid provider I/O.  A local deadline or an explicit
checkout-session cancellation is operational evidence, not provider payment
truth; a later provider-verified success must therefore remain recoverable.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.utils import timezone

from management.models import (
    IgCheckoutInventoryReservation,
    IgCheckoutProposal,
    IgCheckoutProposalItem,
    IgClient,
    IgDeal,
    IgPaymentEvent,
    IgPaymentProjection,
)
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from orders.models import Order, PaymentAttempt
from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, PromoCode


class AssistedAttemptTerminalizationTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.category = Category.objects.create(
            name="Terminalization",
            slug="ig-terminalization",
        )
        self.product = Product.objects.create(
            title="Terminalization shirt",
            slug="ig-terminalization-shirt",
            category=self.category,
            price=Decimal("900.00"),
            status="published",
        )
        self.color = Color.objects.create(
            name="Terminal black",
            primary_hex="#111111",
        )
        self.variant = ProductColorVariant.objects.create(
            product=self.product,
            color=self.color,
            stock=1,
        )
        self.user = get_user_model().objects.create_user(
            username="ig-terminalization-user",
        )
        self.sequence = 0

    def _graph(
        self,
        *,
        invoice_expires_at,
        age=timedelta(minutes=1),
        status=PaymentAttempt.Status.PROCESSING,
        ambiguous=False,
        with_inventory=False,
        with_promo=False,
        with_order=False,
    ):
        self.sequence += 1
        suffix = str(self.sequence)
        client = IgClient.get_or_create_for_sender(f"terminalization-{suffix}")
        deal = IgDeal.objects.create(
            client=client,
            status=IgDeal.Status.AWAITING_PAYMENT,
            amount=Decimal("900.00"),
            requested_payment_amount=Decimal("900.00"),
        )
        episode = ensure_episode_for_deal(deal)
        proposal = IgCheckoutProposal.objects.create_current(
            deal=deal,
            commercial_episode=episode,
            catalog_total=Decimal("900.00"),
            quoted_total=Decimal("900.00"),
            requested_payment_amount=Decimal("900.00"),
            items_digest=hashlib.sha256(f"proposal-{suffix}".encode()).hexdigest(),
            expires_at=self.now + timedelta(days=1),
        )
        item = IgCheckoutProposalItem.objects.create(
            proposal=proposal,
            product=self.product,
            color_variant=self.variant,
            product_title=self.product.title,
            quantity=1,
            catalog_unit_price=Decimal("900.00"),
            catalog_line_total=Decimal("900.00"),
            quoted_unit_price=Decimal("900.00"),
            quoted_line_total=Decimal("900.00"),
        )
        promo = None
        event_state = {}
        if ambiguous:
            event_state["invoice_creation_ambiguous"] = True
        if with_promo:
            promo = PromoCode.objects.create(
                code=f"TERM{suffix}",
                discount_type="percentage",
                discount_value=Decimal("5.00"),
                max_uses=10,
                current_uses=1,
            )
            event_state["promo_reservation"] = {
                "promo_id": promo.pk,
                "state": "reserved",
                "capacity_reserved": True,
                "reserved_at": (self.now - age).isoformat(),
            }
        order = None
        if with_order:
            order = Order.objects.create(
                full_name="Already paid",
                phone="+380501112233",
                city="Kyiv",
                np_office="Branch 1",
                pay_type="online_full",
                payment_status="paid",
                total_sum=Decimal("900.00"),
            )
        attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(f"attempt-{suffix}".encode()).hexdigest(),
            user=self.user if with_promo else None,
            session_key=f"session-{suffix}",
            full_name="Instagram Buyer",
            phone="+380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=status,
            cart_snapshot={
                "checkout_surface": "instagram_proposal",
                "sale_source": "Instagram",
                "proposal_id": str(proposal.public_id),
                "cart": [
                    {
                        "product_id": self.product.pk,
                        "title": self.product.title,
                        "qty": 1,
                        "size": "",
                        "fit_option_code": "",
                        "fit_option_label": "",
                        "color_variant_id": self.variant.pk,
                        "option_values": {},
                        "option_labels": {},
                        "unit_price": "900.00",
                        "line_total": "900.00",
                    }
                ],
            },
            gross_amount=Decimal("900.00"),
            payable_amount=Decimal("900.00"),
            payment_amount=Decimal("900.00"),
            promo_code=promo,
            event_state=event_state,
            monobank_invoice_id=f"invoice-{suffix}",
            invoice_url=f"https://pay.example/{suffix}",
            invoice_expires_at=invoice_expires_at,
            order=order,
        )
        PaymentAttempt.objects.filter(pk=attempt.pk).update(created=self.now - age)
        attempt.refresh_from_db()
        proposal.payment_attempt = attempt
        proposal.status = IgCheckoutProposal.Status.INVOICE_CREATED
        proposal.save(update_fields=["payment_attempt", "status", "updated_at"])
        reservation = None
        if with_inventory:
            reservation = IgCheckoutInventoryReservation.objects.create(
                proposal=proposal,
                item=item,
                product=self.product,
                color_variant=self.variant,
                allocation_source="catalog_variant",
                allocation_key=f"catalog_variant:variant:{self.variant.pk}",
                line_ids=[item.pk],
                quantity=1,
                reservation_fingerprint=hashlib.sha256(
                    f"reservation-{suffix}".encode()
                ).hexdigest(),
                expires_at=self.now - timedelta(seconds=1),
            )
        return {
            "client": client,
            "deal": deal,
            "proposal": proposal,
            "attempt": attempt,
            "reservation": reservation,
            "promo": promo,
        }

    def test_explicit_invoice_deadline_terminalizes_immediately(self):
        graph = self._graph(
            invoice_expires_at=self.now - timedelta(seconds=1),
            age=timedelta(minutes=1),
        )

        from management.services.ig_checkout_terminalization import (
            expire_due_assisted_attempts,
        )

        result = expire_due_assisted_attempts(now=self.now, limit=10)

        graph["attempt"].refresh_from_db()
        graph["proposal"].refresh_from_db()
        event = IgPaymentEvent.objects.get(deal=graph["deal"])
        projection = IgPaymentProjection.objects.get(deal=graph["deal"])
        self.assertEqual(result["expired_attempts"], 1)
        self.assertEqual(graph["attempt"].status, PaymentAttempt.Status.EXPIRED)
        self.assertEqual(graph["attempt"].error_reason, "invoice_expired")
        self.assertEqual(graph["proposal"].status, IgCheckoutProposal.Status.EXPIRED)
        self.assertIsNone(graph["proposal"].invoice_cancelled_at)
        self.assertIsNone(graph["proposal"].provider_cancellation_event_id)
        self.assertEqual(event.source, "system_expiry")
        self.assertEqual(event.provider_status, "expired")
        self.assertEqual(projection.last_event_id, event.pk)
        self.assertEqual(
            graph["attempt"].event_state["terminalization"]["source"],
            "system_expiry",
        )

    def test_null_expiry_uses_only_the_24_hour_legacy_fallback(self):
        recent = self._graph(
            invoice_expires_at=None,
            age=timedelta(hours=23, minutes=59),
        )
        old = self._graph(
            invoice_expires_at=None,
            age=timedelta(hours=24, seconds=1),
        )

        from management.services.ig_checkout_terminalization import (
            expire_due_assisted_attempts,
        )

        result = expire_due_assisted_attempts(now=self.now, limit=10)

        recent["attempt"].refresh_from_db()
        old["attempt"].refresh_from_db()
        self.assertEqual(result["expired_attempts"], 1)
        self.assertEqual(recent["attempt"].status, PaymentAttempt.Status.PROCESSING)
        self.assertEqual(old["attempt"].status, PaymentAttempt.Status.EXPIRED)

    def test_expiry_releases_inventory_and_promo_capacity(self):
        graph = self._graph(
            invoice_expires_at=self.now,
            with_inventory=True,
            with_promo=True,
        )

        from management.services.ig_checkout_terminalization import (
            expire_due_assisted_attempts,
        )

        result = expire_due_assisted_attempts(now=self.now, limit=10)

        graph["attempt"].refresh_from_db()
        graph["reservation"].refresh_from_db()
        graph["promo"].refresh_from_db()
        self.assertEqual(result["released_inventory"], 1)
        self.assertEqual(result["released_promos"], 1)
        self.assertEqual(
            graph["reservation"].state,
            IgCheckoutInventoryReservation.State.RELEASED,
        )
        self.assertEqual(graph["promo"].current_uses, 0)
        self.assertEqual(
            graph["attempt"].event_state["promo_reservation"]["state"],
            "released",
        )

    def test_reconciler_is_the_runtime_owner_for_due_attempts(self):
        graph = self._graph(invoice_expires_at=self.now)

        from management.services.ig_checkout_reconciliation import reconcile_ig_checkout

        result = reconcile_ig_checkout(limit=10, pull_ambiguous=False)

        graph["attempt"].refresh_from_db()
        self.assertEqual(result["expired_attempts"], 1)
        self.assertEqual(graph["attempt"].status, PaymentAttempt.Status.EXPIRED)

    def test_session_reset_uses_the_same_locked_terminalization_boundary(self):
        graph = self._graph(
            invoice_expires_at=self.now + timedelta(minutes=20),
            with_inventory=True,
            with_promo=True,
        )
        request = RequestFactory().get("/cart/")
        SessionMiddleware(lambda _request: None).process_request(request)
        request.session["monobank_pending_attempt_id"] = graph["attempt"].pk
        request.session.save()

        from storefront.views.utils import _reset_monobank_session

        _reset_monobank_session(request, drop_pending=True)

        graph["attempt"].refresh_from_db()
        graph["reservation"].refresh_from_db()
        graph["promo"].refresh_from_db()
        event = IgPaymentEvent.objects.get(deal=graph["deal"])
        self.assertEqual(graph["attempt"].status, PaymentAttempt.Status.CANCELLED)
        self.assertEqual(graph["reservation"].state, IgCheckoutInventoryReservation.State.RELEASED)
        self.assertEqual(graph["promo"].current_uses, 0)
        self.assertEqual(event.source, "checkout_session_reset")
        self.assertNotIn("monobank_pending_attempt_id", request.session)

    def test_terminalization_is_idempotent(self):
        graph = self._graph(
            invoice_expires_at=self.now,
            with_inventory=True,
            with_promo=True,
        )

        from management.services.ig_checkout_terminalization import (
            terminalize_payment_attempt,
        )

        first = terminalize_payment_attempt(
            graph["attempt"].pk,
            terminal_status=PaymentAttempt.Status.EXPIRED,
            reason="invoice_expired",
            source="system_expiry",
            now=self.now,
            require_due=True,
        )
        second = terminalize_payment_attempt(
            graph["attempt"].pk,
            terminal_status=PaymentAttempt.Status.EXPIRED,
            reason="invoice_expired",
            source="system_expiry",
            now=self.now,
            require_due=True,
        )

        self.assertEqual(first.outcome, "terminalized")
        self.assertEqual(second.outcome, "already_terminal")
        self.assertEqual(IgPaymentEvent.objects.filter(deal=graph["deal"]).count(), 1)
        graph["promo"].refresh_from_db()
        self.assertEqual(graph["promo"].current_uses, 0)

    def test_crash_rolls_back_the_whole_boundary_and_replay_finishes(self):
        graph = self._graph(
            invoice_expires_at=self.now,
            with_inventory=True,
            with_promo=True,
        )

        from management.services.ig_checkout_terminalization import (
            expire_due_assisted_attempts,
        )

        with patch(
            "management.services.ig_checkout_terminalization.release_payment_attempt_promo",
            side_effect=RuntimeError("simulated crash"),
        ), patch(
            "management.services.ig_checkout_terminalization.logger.exception"
        ):
            failed = expire_due_assisted_attempts(now=self.now, limit=10)

        graph["attempt"].refresh_from_db()
        graph["proposal"].refresh_from_db()
        graph["reservation"].refresh_from_db()
        graph["promo"].refresh_from_db()
        self.assertEqual(failed["errors"], 1)
        self.assertEqual(graph["attempt"].status, PaymentAttempt.Status.PROCESSING)
        self.assertEqual(graph["proposal"].status, IgCheckoutProposal.Status.INVOICE_CREATED)
        self.assertEqual(graph["reservation"].state, IgCheckoutInventoryReservation.State.ACTIVE)
        self.assertEqual(graph["promo"].current_uses, 1)
        self.assertFalse(IgPaymentEvent.objects.filter(deal=graph["deal"]).exists())

        replay = expire_due_assisted_attempts(now=self.now, limit=10)
        graph["attempt"].refresh_from_db()
        self.assertEqual(replay["expired_attempts"], 1)
        self.assertEqual(graph["attempt"].status, PaymentAttempt.Status.EXPIRED)

    def test_ambiguous_and_paid_attempts_are_excluded(self):
        ambiguous = self._graph(
            invoice_expires_at=self.now,
            ambiguous=True,
        )
        paid = self._graph(
            invoice_expires_at=self.now,
            with_order=True,
        )

        from management.services.ig_checkout_terminalization import (
            expire_due_assisted_attempts,
        )

        result = expire_due_assisted_attempts(now=self.now, limit=10)

        ambiguous["attempt"].refresh_from_db()
        paid["attempt"].refresh_from_db()
        self.assertEqual(result["expired_attempts"], 0)
        self.assertEqual(ambiguous["attempt"].status, PaymentAttempt.Status.PROCESSING)
        self.assertIsNotNone(paid["attempt"].order_id)
        self.assertEqual(paid["attempt"].status, PaymentAttempt.Status.PROCESSING)

    def test_late_verified_success_is_accepted_once_and_routes_to_inventory_review(self):
        graph = self._graph(
            invoice_expires_at=self.now,
            with_inventory=True,
        )

        from management.services.ig_checkout_terminalization import (
            expire_due_assisted_attempts,
        )
        from storefront.views.monobank import _apply_payment_attempt_status

        expire_due_assisted_attempts(now=self.now, limit=10)
        graph["attempt"].refresh_from_db()

        payload = {
            "status": "success",
            "invoiceId": graph["attempt"].monobank_invoice_id,
            "reference": graph["attempt"].reference,
            "ccy": 980,
            "paidAmount": 90000,
        }
        first_order, first_created = _apply_payment_attempt_status(
            graph["attempt"],
            "success",
            payload=payload,
            source="provider_pull",
        )
        second_order, second_created = _apply_payment_attempt_status(
            graph["attempt"],
            "success",
            payload=payload,
            source="provider_pull",
        )

        graph["attempt"].refresh_from_db()
        graph["proposal"].refresh_from_db()
        graph["reservation"].refresh_from_db()
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_order.pk, second_order.pk)
        self.assertEqual(Order.objects.filter(pk=first_order.pk).count(), 1)
        self.assertEqual(graph["attempt"].order_id, first_order.pk)
        self.assertEqual(graph["proposal"].status, IgCheckoutProposal.Status.MANAGER_REVIEW)
        self.assertEqual(
            graph["reservation"].state,
            IgCheckoutInventoryReservation.State.OVERBOOKED_REVIEW,
        )
        self.assertEqual(
            IgPaymentEvent.objects.filter(
                deal=graph["deal"],
                provider_status="success",
            ).count(),
            1,
        )
