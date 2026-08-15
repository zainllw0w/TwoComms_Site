from datetime import timedelta
from decimal import Decimal
import json

from django.test import TestCase
from unittest.mock import Mock, patch
from django.utils import timezone
from django.urls import reverse

from orders.models import Order, PaymentAttempt
from orders.nova_poshta_checkout import build_city_choice_token, build_warehouse_choice_token
from storefront.models import Category, Product, PromoCode, PromoCodeGuestUsage


def _attach_external_ugc_reward(promo, *, suffix):
    from management.ig_bot_models import (
        IgClient,
        IgUgcEvidenceAssessment,
        IgUgcReward,
        IgUgcRewardLifetime,
    )

    client = IgClient.get_or_create_for_sender(f"guest-ugc-{suffix}")
    assessment = IgUgcEvidenceAssessment.objects.create(
        client=client,
        source_message_id=f"guest-story-{suffix}",
        provider_object_key=f"story:guest-{suffix}",
        provider_object_digest=f"{int(promo.pk):064x}",
        provider_event_id=f"guest-story-{suffix}",
        target_username="twocomms",
        evidence_fingerprint=f"guest-evidence-{suffix}",
        decision=IgUgcEvidenceAssessment.Decision.QUALIFIED_AUTO,
        decision_source="auto",
        policy_version="ugc-v1",
        reward_owner_client_id=client.pk,
    )
    reward = IgUgcReward.objects.create(
        client=client,
        evidence_type=IgUgcReward.EvidenceType.STORY_MENTION,
        evidence_fingerprint=f"guest-reward-{suffix}",
        promo_code=promo,
        reward_path="external_ugc",
        decision_source="auto",
        assessment=assessment,
        lifetime_slot_key=f"guest-slot-{suffix}",
    )
    IgUgcRewardLifetime.objects.create(
        client=client,
        identity_digest=f"guest-lifetime-{suffix}",
        reward=reward,
        consumed_at=timezone.now(),
    )
    return reward


class UGCGuestPromoTests(TestCase):
    def test_only_issued_external_ugc_capability_can_be_reserved_anonymously(self):
        from orders.promo_reservations import reserve_promo_for_checkout

        now = timezone.now()
        promo = PromoCode.objects.create(
            code="UGCGUEST01",
            discount_type="percentage",
            discount_value=Decimal("10"),
            max_uses=1,
            one_time_per_user=False,
            guest_redeemable=True,
            promo_type="regular",
            valid_from=now,
            valid_until=now + timedelta(days=90),
            is_active=True,
        )
        _attach_external_ugc_reward(promo, suffix="reserve-valid")
        reservation = reserve_promo_for_checkout(
            code=promo.code,
            user=None,
            total_amount=Decimal("1000"),
        )
        self.assertEqual(reservation.discount, Decimal("100.00"))

    def test_ordinary_anonymous_promo_is_rejected(self):
        from orders.promo_reservations import PromoReservationError, reserve_promo_for_checkout

        promo = PromoCode.objects.create(
            code="ORDINARY01",
            discount_type="percentage",
            discount_value=Decimal("10"),
            max_uses=1,
            one_time_per_user=False,
            promo_type="regular",
            is_active=True,
        )
        with self.assertRaises(PromoReservationError) as ctx:
            reserve_promo_for_checkout(
                code=promo.code,
                user=None,
                total_amount=Decimal("1000"),
            )
        self.assertEqual(ctx.exception.reason, "account_required")

    def test_guest_flag_without_external_reward_is_rejected(self):
        from orders.promo_reservations import (
            PromoReservationError,
            reserve_promo_for_checkout,
        )

        promo = PromoCode.objects.create(
            code="FAKEUGC01",
            discount_type="percentage",
            discount_value=Decimal("10"),
            max_uses=1,
            one_time_per_user=False,
            guest_redeemable=True,
            promo_type="regular",
            is_active=True,
        )

        with self.assertRaises(PromoReservationError) as ctx:
            reserve_promo_for_checkout(
                code=promo.code,
                user=None,
                total_amount=Decimal("1000"),
            )

        self.assertEqual(ctx.exception.reason, "account_required")

    def test_guest_ugc_promo_expires_at_valid_until_boundary(self):
        from unittest.mock import patch

        from orders.promo_reservations import PromoReservationError, reserve_promo_for_checkout

        now = timezone.now()
        promo = PromoCode.objects.create(
            code="UGCBOUNDARY",
            discount_type="percentage",
            discount_value=Decimal("10"),
            max_uses=1,
            one_time_per_user=False,
            guest_redeemable=True,
            promo_type="regular",
            valid_from=now - timedelta(minutes=1),
            valid_until=now,
            is_active=True,
        )
        _attach_external_ugc_reward(promo, suffix="boundary")

        with patch("django.utils.timezone.now", return_value=now):
            with self.assertRaises(PromoReservationError) as ctx:
                reserve_promo_for_checkout(
                    code=promo.code,
                    user=None,
                    total_amount=Decimal("1000"),
                )

        self.assertEqual(ctx.exception.reason, "invalid")
        promo.refresh_from_db()
        self.assertEqual(promo.current_uses, 0)

    def test_external_reward_with_unbounded_promo_is_not_guest_capability(self):
        from orders.promo_reservations import (
            PromoReservationError,
            reserve_promo_for_checkout,
        )

        promo = PromoCode.objects.create(
            code="UGCUNBOUND1",
            discount_type="percentage",
            discount_value=Decimal("10"),
            max_uses=0,
            one_time_per_user=False,
            guest_redeemable=True,
            promo_type="regular",
            is_active=True,
        )
        _attach_external_ugc_reward(promo, suffix="unbounded")

        with self.assertRaises(PromoReservationError) as ctx:
            reserve_promo_for_checkout(
                code=promo.code,
                user=None,
                total_amount=Decimal("1000"),
            )

        self.assertEqual(ctx.exception.reason, "account_required")

    def test_released_guest_capacity_can_be_reserved_again_without_duplicate_ledger_row(self):
        from orders.models import PaymentAttempt
        from orders.promo_reservations import (
            release_payment_attempt_promo,
            reserve_promo_for_checkout,
        )

        now = timezone.now()
        promo = PromoCode.objects.create(
            code="UGCRELEASE01",
            discount_type="percentage",
            discount_value=Decimal("10"),
            max_uses=1,
            one_time_per_user=False,
            guest_redeemable=True,
            promo_type="regular",
            valid_from=now,
            valid_until=now + timedelta(days=90),
            is_active=True,
        )
        _attach_external_ugc_reward(promo, suffix="release")
        first = reserve_promo_for_checkout(
            code=promo.code, user=None, total_amount=Decimal("1000")
        )
        attempt = PaymentAttempt.objects.create(
            fingerprint="guest-release-attempt",
            full_name="Guest",
            phone="380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            promo_code=promo,
            event_state=first.event_state,
            gross_amount=Decimal("1000"),
            payable_amount=Decimal("900"),
            payment_amount=Decimal("900"),
        )
        self.assertTrue(release_payment_attempt_promo(attempt))

        second = reserve_promo_for_checkout(
            code=promo.code, user=None, total_amount=Decimal("1000")
        )
        self.assertEqual(second.promo.pk, promo.pk)
        from storefront.models import PromoCodeGuestUsage
        self.assertEqual(PromoCodeGuestUsage.objects.filter(promo_code=promo).count(), 1)

    def test_stale_release_does_not_release_reissued_guest_reservation(self):
        from orders.promo_reservations import (
            release_payment_attempt_promo,
            reserve_promo_for_checkout,
        )

        now = timezone.now()
        promo = PromoCode.objects.create(
            code="UGCSTALELEASE",
            discount_type="percentage",
            discount_value=Decimal("10"),
            max_uses=1,
            one_time_per_user=False,
            guest_redeemable=True,
            promo_type="regular",
            valid_from=now,
            valid_until=now + timedelta(days=90),
            is_active=True,
        )
        _attach_external_ugc_reward(promo, suffix="stale-release")
        first = reserve_promo_for_checkout(
            code=promo.code, user=None, total_amount=Decimal("1000")
        )
        attempt = PaymentAttempt.objects.create(
            fingerprint="guest-stale-release",
            full_name="Guest",
            phone="380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            promo_code=promo,
            event_state=first.event_state,
            gross_amount=Decimal("1000"),
            payable_amount=Decimal("900"),
            payment_amount=Decimal("900"),
        )
        stale_event_state = dict(attempt.event_state)
        self.assertTrue(release_payment_attempt_promo(attempt, reason="expired"))

        reserve_promo_for_checkout(
            code=promo.code, user=None, total_amount=Decimal("1000")
        )
        # Simulate a terminal worker that persisted an old RESERVED snapshot
        # after the same bearer row had already been reissued.
        PaymentAttempt.objects.filter(pk=attempt.pk).update(
            event_state=stale_event_state,
        )

        self.assertFalse(release_payment_attempt_promo(attempt, reason="late"))
        guest_usage = PromoCodeGuestUsage.objects.get(promo_code=promo)
        promo.refresh_from_db()
        self.assertEqual(guest_usage.state, PromoCodeGuestUsage.State.RESERVED)
        self.assertEqual(promo.current_uses, 1)

    def test_legacy_anonymous_release_without_generation_fails_closed(self):
        from orders.promo_reservations import (
            release_payment_attempt_promo,
            reserve_promo_for_checkout,
        )

        now = timezone.now()
        promo = PromoCode.objects.create(
            code="UGCLEGACYRELEASE",
            discount_type="percentage",
            discount_value=Decimal("10"),
            max_uses=1,
            one_time_per_user=False,
            guest_redeemable=True,
            promo_type="regular",
            valid_from=now,
            valid_until=now + timedelta(days=90),
            is_active=True,
        )
        _attach_external_ugc_reward(promo, suffix="legacy-release")
        reservation = reserve_promo_for_checkout(
            code=promo.code, user=None, total_amount=Decimal("1000")
        )
        reservation_state = dict(reservation.event_state)
        reservation_state["promo_reservation"].pop("guest_usage_id", None)
        reservation_state["promo_reservation"].pop("guest_reservation_key", None)
        attempt = PaymentAttempt.objects.create(
            fingerprint="guest-legacy-release",
            full_name="Guest",
            phone="380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            promo_code=promo,
            event_state=reservation_state,
            gross_amount=Decimal("1000"),
            payable_amount=Decimal("900"),
            payment_amount=Decimal("900"),
        )

        self.assertFalse(release_payment_attempt_promo(attempt, reason="legacy"))
        guest_usage = PromoCodeGuestUsage.objects.get(promo_code=promo)
        promo.refresh_from_db()
        self.assertEqual(guest_usage.state, PromoCodeGuestUsage.State.RESERVED)
        self.assertEqual(promo.current_uses, 1)


class UGCGuestCheckoutViewTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="UGC category", slug="ugc-category")
        self.product = Product.objects.create(
            title="UGC shirt",
            slug="ugc-shirt",
            category=category,
            price=1000,
            status="published",
        )
        session = self.client.session
        session["cart"] = {
            f"{self.product.pk}:M": {
                "product_id": self.product.pk,
                "qty": 1,
                "size": "M",
            }
        }
        session.save()

    def _delivery(self):
        city_ref = "ugc-city-ref"
        warehouse_ref = "ugc-warehouse-ref"
        return {
            "city": "Київ",
            "np_office": "Відділення №1",
            "np_settlement_ref": "spoofed-settlement",
            "np_city_ref": "spoofed-city",
            "np_city_token": build_city_choice_token(
                {"label": "м. Київ", "settlement_ref": "ugc-settlement", "city_ref": city_ref}
            ),
            "np_warehouse_ref": "spoofed-warehouse",
            "np_warehouse_token": build_warehouse_choice_token(
                {
                    "label": "Відділення №1",
                    "ref": warehouse_ref,
                    "kind": "branch",
                    "city_ref": city_ref,
                }
            ),
            "canonical_city": "м. Київ",
            "canonical_np_office": "Відділення №1",
            "canonical_settlement_ref": "ugc-settlement",
            "canonical_city_ref": city_ref,
            "canonical_warehouse_ref": warehouse_ref,
        }

    def _post_cod(self):
        payload = self._delivery()
        payload.update(
            {
                "full_name": "Guest UGC Buyer",
                "phone": "+380501234567",
                "pay_type": "cod",
            }
        )
        return self.client.post(reverse("order_create"), payload, secure=True)

    def _set_promo(self, *, code, guest_redeemable=False):
        promo = PromoCode.objects.create(
            code=code,
            discount_type="percentage",
            discount_value=Decimal("10"),
            max_uses=1,
            one_time_per_user=False,
            guest_redeemable=guest_redeemable,
            valid_from=timezone.now() - timedelta(minutes=1),
            valid_until=timezone.now() + timedelta(days=90),
            is_active=True,
        )
        if guest_redeemable:
            _attach_external_ugc_reward(promo, suffix=code.casefold())
        return promo

    def test_anonymous_apply_accepts_only_explicit_guest_ugc_capability(self):
        promo = self._set_promo(code="UGCVIEW01", guest_redeemable=True)

        response = self.client.post(
            reverse("apply_promo_code"),
            {"promo_code": promo.code},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["promo_code"], promo.code)

    def test_anonymous_apply_keeps_ordinary_promo_account_only(self):
        promo = self._set_promo(code="ORDVIEW01")

        response = self.client.post(
            reverse("apply_promo_code"),
            {"promo_code": promo.code},
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.json()["auth_required"])
        self.assertNotIn("promo_code_id", self.client.session)

    def test_guest_cod_remains_disabled_and_does_not_consume_ugc_capability(self):
        promo = self._set_promo(code="UGCCOD01", guest_redeemable=True)
        response = self.client.post(
            reverse("apply_promo_code"),
            {"promo_code": promo.code},
        )
        self.assertEqual(response.status_code, 200)

        response = self._post_cod()

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(PromoCodeGuestUsage.objects.filter(promo_code=promo).exists())
        promo.refresh_from_db()
        self.assertEqual(promo.current_uses, 0)

    def test_guest_ugc_promo_does_not_stack_with_another_session_promo(self):
        first = self._set_promo(code="UGCSTACK1", guest_redeemable=True)
        second = PromoCode.objects.create(
            code="UGCSTACK2",
            discount_type="percentage",
            discount_value=Decimal("10"),
            max_uses=1,
            one_time_per_user=False,
            guest_redeemable=True,
            valid_from=timezone.now() - timedelta(minutes=1),
            valid_until=timezone.now() + timedelta(days=90),
            is_active=True,
        )
        _attach_external_ugc_reward(second, suffix="stack-second")
        response = self.client.post(
            reverse("apply_promo_code"),
            {"promo_code": second.code},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["promo_code"], second.code)
        self.assertNotEqual(self.client.session.get("promo_code_id"), first.pk)

    def test_public_online_checkout_reserves_guest_ugc_code_atomically(self):
        promo = self._set_promo(code="UGCONLINE1", guest_redeemable=True)
        response = self.client.post(
            reverse("apply_promo_code"),
            {"promo_code": promo.code},
        )
        self.assertEqual(response.status_code, 200)
        payload = self._delivery()
        payload.update(
            {
                "full_name": "Guest Online Buyer",
                "phone": "0991234567",
                "pay_type": "online_full",
            }
        )
        with patch("storefront.views.monobank._monobank_api_request") as provider, \
                patch("storefront.views.monobank.get_facebook_conversions_service") as facebook, \
                patch("storefront.views.monobank.record_lead"), \
                patch("storefront.views.monobank.record_initiate_checkout"), \
                patch("storefront.views.monobank.link_order_to_utm"), \
                patch("orders.telegram_notifications.TelegramNotifier.send_new_order_notification", return_value=True):
            provider.return_value = {
                "invoiceId": "ugc-public-invoice",
                "pageUrl": "https://pay.example/ugc-public-invoice",
            }
            facebook.return_value = Mock()
            response = self.client.post(
                reverse("monobank_create_invoice"),
                data=json.dumps(payload),
                content_type="application/json",
                secure=True,
            )

        self.assertEqual(response.status_code, 200, response.content.decode())
        attempt = PaymentAttempt.objects.get()
        self.assertEqual(attempt.discount_amount, Decimal("100.00"))
        self.assertEqual(attempt.promo_code_id, promo.pk)
        usage = PromoCodeGuestUsage.objects.get(promo_code=promo)
        self.assertEqual(usage.state, PromoCodeGuestUsage.State.RESERVED)
        self.assertEqual(usage.order_id, None)
        self.assertEqual((attempt.event_state or {}).get("promo_reservation", {}).get("state"), "reserved")
