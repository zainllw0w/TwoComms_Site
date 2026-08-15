import json
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.test import TestCase
from django.urls import reverse

from orders.models import Order, PaymentAttempt
from orders.nova_poshta_checkout import (
    build_city_choice_token,
    build_warehouse_choice_token,
)
from orders.payment_attempts import materialize_payment_attempt
from storefront.models import (
    Category,
    Product,
    PromoCode,
    PromoCodeGroup,
    PromoCodeGuestUsage,
    PromoCodeUsage,
)


class PromoAtomicityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="atomic-promo-buyer",
            email="atomic-promo@example.com",
            password="test-password",
        )
        self.client.force_login(self.user)
        category = Category.objects.create(
            name="Atomic promo category",
            slug="atomic-promo-category",
        )
        self.product = Product.objects.create(
            title="Atomic promo shirt",
            slug="atomic-promo-shirt",
            category=category,
            price=Decimal("900.00"),
            status="published",
        )
        self.snapshot = {
            "cart": [{
                "product_id": self.product.pk,
                "title": self.product.title,
                "qty": 1,
                "size": "M",
                "fit_option_code": "",
                "fit_option_label": "",
                "color_variant_id": None,
                "option_values": {},
                "option_labels": {},
                "unit_price": "900.00",
                "line_total": "900.00",
            }],
            "custom_print_lead_ids": [],
        }

    def _attempt(self, *, fingerprint, promo, state="reserved"):
        return PaymentAttempt.objects.create(
            fingerprint=fingerprint,
            user=self.user,
            full_name="Atomic Buyer",
            phone="+380501112233",
            email="atomic-promo@example.com",
            city="Kyiv",
            np_office="Branch 1",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            cart_snapshot=self.snapshot,
            gross_amount=Decimal("900.00"),
            discount_amount=Decimal("100.00"),
            payable_amount=Decimal("800.00"),
            payment_amount=Decimal("800.00"),
            promo_code=promo,
            event_state={
                "promo_reservation": {
                    "promo_id": promo.pk,
                    "group_id": promo.group_id,
                    "state": state,
                }
            },
        )

    def _invoice_payload(self):
        return {
            "full_name": "Atomic Buyer",
            "phone": "+380501112233",
            "email": "atomic-promo@example.com",
            "city": "Kyiv",
            "np_office": "Branch 1",
            "np_city_token": build_city_choice_token({
                "label": "Kyiv",
                "settlement_ref": "settlement-1",
                "city_ref": "city-1",
            }),
            "np_warehouse_token": build_warehouse_choice_token({
                "label": "Branch 1",
                "ref": "warehouse-1",
                "kind": "branch",
                "city_ref": "city-1",
            }),
            "pay_type": "online_full",
        }

    def _set_cart_promo(self, promo):
        session = self.client.session
        session["cart"] = {
            "line-1": {
                "product_id": self.product.pk,
                "qty": 1,
                "size": "M",
            }
        }
        session["promo_code_id"] = promo.pk
        session.save()

    def _post_invoice(self, provider):
        with patch(
            "storefront.views.monobank._monobank_api_request",
            provider,
        ), patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service"
        ) as facebook, patch(
            "orders.telegram_notifications.TelegramNotifier.send_payment_attempt_notification",
            return_value=True,
        ):
            facebook.return_value.send_add_payment_info_event.return_value = True
            return self.client.post(
                reverse("monobank_create_invoice"),
                data=json.dumps(self._invoice_payload()),
                content_type="application/json",
                secure=True,
            )

    def test_cart_monobank_rejects_active_assisted_reservation_from_same_group(self):
        group = PromoCodeGroup.objects.create(
            name="Cross-channel group",
            one_per_account=True,
        )
        reserved = PromoCode.objects.create(
            code="IGRESERVED",
            discount_type="fixed",
            discount_value=Decimal("100.00"),
            group=group,
            current_uses=1,
        )
        requested = PromoCode.objects.create(
            code="CARTSECOND",
            discount_type="fixed",
            discount_value=Decimal("100.00"),
            group=group,
        )
        self._attempt(fingerprint="ig-active-reservation", promo=reserved)
        self._set_cart_promo(requested)

        provider_mock = Mock(return_value={
            "invoiceId": "must-not-be-created",
            "pageUrl": "https://pay.example/must-not-be-created",
        })
        response = self._post_invoice(provider_mock)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("field"), "promo_code")
        provider_mock.assert_not_called()
        self.assertEqual(PaymentAttempt.objects.count(), 1)

    def test_cart_monobank_rejects_inactive_group_before_provider_io(self):
        group = PromoCodeGroup.objects.create(
            name="Inactive provider guard",
            one_per_account=False,
            is_active=False,
        )
        promo = PromoCode.objects.create(
            code="INACTIVECART",
            discount_type="fixed",
            discount_value=Decimal("100.00"),
            group=group,
        )
        self._set_cart_promo(promo)

        provider = Mock(return_value={
            "invoiceId": "must-not-be-created",
            "pageUrl": "https://pay.example/must-not-be-created",
        })
        response = self._post_invoice(provider)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("field"), "promo_code")
        provider.assert_not_called()
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_immediate_order_usage_cannot_bypass_active_group_reservation(self):
        group = PromoCodeGroup.objects.create(
            name="COD versus invoice group",
            one_per_account=True,
        )
        reserved = PromoCode.objects.create(
            code="PENDINGPAY",
            discount_type="fixed",
            discount_value=Decimal("100.00"),
            group=group,
            current_uses=1,
        )
        requested = PromoCode.objects.create(
            code="CODSECOND",
            discount_type="fixed",
            discount_value=Decimal("100.00"),
            group=group,
        )
        self._attempt(fingerprint="pending-before-cod", promo=reserved)
        order = Order.objects.create(
            user=self.user,
            full_name="Atomic Buyer",
            phone="+380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type="cod",
            total_sum=Decimal("900.00"),
        )

        with self.assertRaises(Exception):
            requested.record_usage(self.user, order)

        self.assertFalse(PromoCodeUsage.objects.filter(order=order).exists())
        requested.refresh_from_db()
        self.assertEqual(requested.current_uses, 0)

    def test_usage_write_failure_keeps_paid_attempt_reservation_blocking(self):
        group = PromoCodeGroup.objects.create(
            name="Usage failure group",
            one_per_account=True,
        )
        promo = PromoCode.objects.create(
            code="USAGEFAIL",
            discount_type="fixed",
            discount_value=Decimal("100.00"),
            group=group,
            current_uses=1,
        )
        attempt = self._attempt(fingerprint="usage-write-failure", promo=promo)

        def reject_usage_write(sender, instance, **kwargs):
            raise RuntimeError("synthetic usage persistence failure")

        dispatch_uid = "test-promo-usage-write-failure"
        pre_save.connect(
            reject_usage_write,
            sender=PromoCodeUsage,
            weak=False,
            dispatch_uid=dispatch_uid,
        )
        try:
            order, created = materialize_payment_attempt(
                attempt.pk,
                status="success",
                payload={"status": "success", "paidAmount": 80000},
                source="test",
            )
        finally:
            pre_save.disconnect(sender=PromoCodeUsage, dispatch_uid=dispatch_uid)

        self.assertTrue(created)
        self.assertIsNotNone(order)
        attempt.refresh_from_db()
        self.assertEqual(
            (attempt.event_state or {}).get("promo_reservation", {}).get("state"),
            "reserved",
        )
        self.assertFalse(PromoCodeUsage.objects.filter(order=order).exists())

        second = PromoCode.objects.create(
            code="AFTERFAIL",
            discount_type="fixed",
            discount_value=Decimal("100.00"),
            group=group,
        )
        self._set_cart_promo(second)
        provider = Mock()
        response = self._post_invoice(provider)
        self.assertEqual(response.status_code, 400)
        provider.assert_not_called()

    def test_guest_usage_write_failure_keeps_paid_attempt_unmaterialized_and_retryable(self):
        """A paid bearer reservation must not become a discounted Order on ledger failure."""
        from storefront.views.monobank import _apply_payment_attempt_status

        promo = PromoCode.objects.create(
            code="GUESTUSAGEFAIL",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            max_uses=1,
            current_uses=1,
            guest_redeemable=True,
        )
        guest_usage = PromoCodeGuestUsage.objects.create(
            promo_code=promo,
            reservation_key="guest-usage-failure-key",
            state=PromoCodeGuestUsage.State.RESERVED,
        )
        attempt = PaymentAttempt.objects.create(
            fingerprint="guest-usage-write-failure",
            user=None,
            session_key="guest-usage-session",
            full_name="Guest Buyer",
            phone="+380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            cart_snapshot=self.snapshot,
            gross_amount=Decimal("900.00"),
            discount_amount=Decimal("90.00"),
            payable_amount=Decimal("810.00"),
            payment_amount=Decimal("810.00"),
            promo_code=promo,
            event_state={
                "promo_reservation": {
                    "promo_id": promo.pk,
                    "state": "reserved",
                    "capacity_reserved": True,
                    "guest_usage_id": guest_usage.pk,
                }
            },
        )

        def reject_guest_usage_write(sender, instance, **kwargs):
            raise RuntimeError("synthetic guest usage persistence failure")

        dispatch_uid = "test-guest-promo-usage-write-failure"
        pre_save.connect(
            reject_guest_usage_write,
            sender=PromoCodeGuestUsage,
            weak=False,
            dispatch_uid=dispatch_uid,
        )
        try:
            order, created = _apply_payment_attempt_status(
                attempt,
                "success",
                payload={"status": "success", "paidAmount": 81000},
                source="test",
            )
        finally:
            pre_save.disconnect(sender=PromoCodeGuestUsage, dispatch_uid=dispatch_uid)

        self.assertIsNone(order)
        self.assertFalse(created)
        self.assertFalse(Order.objects.filter(payment_invoice_id=attempt.monobank_invoice_id).exists())
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, PaymentAttempt.Status.PROCESSING)
        self.assertTrue(
            (attempt.event_state or {}).get("promo_consumption_pending")
        )
        guest_usage.refresh_from_db()
        self.assertEqual(guest_usage.state, PromoCodeGuestUsage.State.RESERVED)
        self.assertIsNone(guest_usage.order_id)

        # The durable marker makes a later provider-pull/webhook retry safe;
        # once the ledger write succeeds, the same paid attempt materializes.
        order, created = _apply_payment_attempt_status(
            attempt,
            "success",
            payload={"status": "success", "paidAmount": 81000},
            source="reconciliation",
        )
        self.assertTrue(created)
        self.assertIsNotNone(order)
        guest_usage.refresh_from_db()
        self.assertEqual(guest_usage.state, PromoCodeGuestUsage.State.CONSUMED)
        self.assertEqual(guest_usage.order_id, order.pk)
        attempt.refresh_from_db()
        self.assertFalse((attempt.event_state or {}).get("promo_consumption_pending"))

    def test_late_success_after_guest_reservation_release_cannot_consume_reissued_capacity(self):
        """A stale paid invoice must not steal a newly re-reserved bearer code."""
        from datetime import timedelta
        from django.utils import timezone
        from orders.promo_reservations import (
            release_payment_attempt_promo,
            reserve_promo_for_checkout,
        )
        from storefront.models import PromoCodeGuestUsage
        from storefront.views.monobank import _apply_payment_attempt_status

        now = timezone.now()
        promo = PromoCode.objects.create(
            code="GUESTSTALE01",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            max_uses=1,
            one_time_per_user=False,
            guest_redeemable=True,
            promo_type="regular",
            valid_from=now - timedelta(minutes=1),
            valid_until=now + timedelta(days=90),
            is_active=True,
        )
        from storefront.tests.test_ugc_guest_promo import _attach_external_ugc_reward

        _attach_external_ugc_reward(promo, suffix="stale-paid-invoice")
        first = reserve_promo_for_checkout(
            code=promo.code, user=None, total_amount=Decimal("900.00")
        )
        attempt = PaymentAttempt.objects.create(
            fingerprint="guest-stale-paid-invoice",
            user=None,
            full_name="Guest Buyer",
            phone="380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.CANCELLED,
            cart_snapshot=self.snapshot,
            gross_amount=Decimal("900.00"),
            discount_amount=Decimal("90.00"),
            payable_amount=Decimal("810.00"),
            payment_amount=Decimal("810.00"),
            promo_code=promo,
            monobank_invoice_id="guest-stale-invoice",
            event_state=first.event_state,
        )
        self.assertTrue(release_payment_attempt_promo(attempt, reason="expired"))

        # The private code is now legitimately reserved by a different invoice.
        reserve_promo_for_checkout(
            code=promo.code, user=None, total_amount=Decimal("900.00")
        )
        self.assertEqual(
            PromoCodeGuestUsage.objects.get(promo_code=promo).state,
            PromoCodeGuestUsage.State.RESERVED,
        )

        _apply_payment_attempt_status(
            attempt,
            "success",
            payload={"status": "success", "invoiceId": attempt.monobank_invoice_id},
            source="provider_pull",
        )

        attempt.refresh_from_db()
        promo.refresh_from_db()
        self.assertEqual(attempt.status, PaymentAttempt.Status.FAILED)
        self.assertIsNone(attempt.order_id)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(promo.current_uses, 1)
        self.assertEqual(
            PromoCodeGuestUsage.objects.get(promo_code=promo).state,
            PromoCodeGuestUsage.State.RESERVED,
        )


class PromoEngineMigrationContractTests(TestCase):
    def test_storefront_has_forward_innodb_health_migration(self):
        migration = (
            Path(__file__).resolve().parents[2]
            / "storefront"
            / "migrations"
            / "0087_promocodegroup_innodb.py"
        )
        self.assertTrue(
            migration.exists(),
            "PromoCodeGroup needs a forward migration because production is MyISAM",
        )
        migration_module = import_module(
            "storefront.migrations.0087_promocodegroup_innodb"
        )
        self.assertFalse(
            migration_module.Migration.atomic,
            "MySQL/MariaDB engine DDL cannot run inside an atomic migration",
        )
