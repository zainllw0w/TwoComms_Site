import hashlib
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from management.models import (
    IgCheckoutAccessToken,
    IgCheckoutInvoiceGeneration,
    IgCheckoutInventoryReservation,
    IgCheckoutProposal,
    IgCheckoutProposalItem,
    IgBotNotification,
    IgClient,
    IgDeal,
    IgFollowUpTask,
    IgPaymentEvent,
    IgPaymentProjection,
    InstagramBotMessage,
)
from management.services.ig_checkout import create_or_update_proposal
from management.services.ig_checkout_policy import (
    PREPAY_200_QUICK_REPLY,
    resolve_payment_policy,
)
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from orders.models import Order, PaymentAttempt
from orders.nova_poshta_checkout import (
    build_city_choice_token,
    build_warehouse_choice_token,
)
from storefront.models import Category, Product, ProductFitOption, PromoCode, PromoCodeUsage


@override_settings(
    IG_ASSISTED_CHECKOUT_V2="enforced",
    IG_ASSISTED_CHECKOUT_V2_CANARY_PERCENT=100,
)
class CheckoutGenerationRuntimeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client_row = IgClient.get_or_create_for_sender(
            "checkout-generation-runtime"
        )
        category = Category.objects.create(
            name="Generation runtime",
            slug="generation-runtime",
        )
        self.product = Product.objects.create(
            title="Generation shirt",
            slug="generation-shirt",
            category=category,
            price=Decimal("900.00"),
            status="published",
        )
        self.fit = ProductFitOption.objects.create(
            product=self.product,
            code="classic",
            label="Classic",
            is_default=True,
            is_active=True,
        )

    def _item(self):
        return {
            "product_id": self.product.pk,
            "qty": 1,
            "fit_option_code": self.fit.code,
            "size": "M",
        }

    def _delivery_payload(self, **values):
        payload = {
            "full_name": "Іван Петренко",
            "phone": "+380501112233",
            "email": "buyer@example.com",
            "city": "Київ",
            "np_settlement_ref": "settlement-ref",
            "np_city_ref": "city-ref",
            "np_city_token": build_city_choice_token({
                "label": "Київ",
                "settlement_ref": "settlement-ref",
                "city_ref": "city-ref",
            }),
            "np_office": "Відділення №12",
            "np_warehouse_ref": "warehouse-ref",
            "np_warehouse_token": build_warehouse_choice_token({
                "label": "Відділення №12",
                "ref": "warehouse-ref",
                "kind": "branch",
                "city_ref": "city-ref",
            }),
        }
        payload.update(values)
        return payload

    def _open(self, proposal):
        raw, token = IgCheckoutAccessToken.issue(proposal=proposal)
        response = self.client.get(
            reverse("ig_checkout_token_entry", kwargs={"token": raw})
        )
        self.assertEqual(response.status_code, 302)
        return response, token

    def _create_invoice(self, proposal, *, invoice_id, payment_choice="online_full"):
        self._open(proposal)
        with patch(
            "storefront.views.monobank._monobank_api_request",
            return_value={
                "invoiceId": invoice_id,
                "pageUrl": f"https://pay.example/{invoice_id}",
            },
        ):
            response = self.client.post(
                reverse(
                    "ig_checkout_proposal",
                    kwargs={"proposal_id": proposal.public_id},
                ),
                self._delivery_payload(payment_choice=payment_choice),
                HTTP_ACCEPT="application/json",
            )
        self.assertEqual(response.status_code, 200, response.content)
        return (
            IgCheckoutInvoiceGeneration.objects.filter(proposal=proposal)
            .order_by("-generation")
            .first()
        )

    def test_canary_proposal_is_12_hours_and_creates_no_stock_or_reminder(self):
        now = timezone.now()
        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="prepayment",
            requested_payment_amount=Decimal("200.00"),
            item_specs=[self._item()],
        )

        self.assertTrue(proposal.assisted_checkout_v2)
        self.assertEqual(proposal.payment_policy, proposal.PaymentPolicy.FULL_ONLY)
        self.assertEqual(proposal.pay_type, proposal.PayType.ONLINE_FULL)
        self.assertEqual(proposal.requested_payment_amount, proposal.quoted_total)
        self.assertGreater(proposal.expires_at, now + timedelta(hours=11, minutes=59))
        self.assertLess(proposal.expires_at, now + timedelta(hours=12, minutes=1))
        self.assertFalse(IgCheckoutInventoryReservation.objects.exists())
        self.assertFalse(
            IgFollowUpTask.objects.filter(
                event_key__startswith="proposal_expired:"
            ).exists()
        )
        entry, _token = self._open(proposal)
        page = self.client.get(entry["Location"])
        self.assertContains(page, "Вибір збережено на 12 годин")
        self.assertContains(page, "повторно перевіряємо актуальну ціну")
        self.assertNotContains(page, "Товари й ціна зафіксовані")

    def test_only_latest_owned_user_question_unlocks_200_cod(self):
        old = InstagramBotMessage.objects.create(
            client=self.client_row,
            sender_id=self.client_row.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Можно 200 грн предоплаты, остальное наложкой?",
        )
        later = InstagramBotMessage.objects.create(
            client=self.client_row,
            sender_id=self.client_row.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Добре",
        )
        rejected = resolve_payment_policy(
            client=self.client_row,
            evidence_message_ids=[old.pk],
        )
        self.assertEqual(rejected.policy, IgCheckoutProposal.PaymentPolicy.FULL_ONLY)

        later.quick_reply_payload = PREPAY_200_QUICK_REPLY
        later.save(update_fields=["quick_reply_payload"])
        allowed = resolve_payment_policy(
            client=self.client_row,
            evidence_message_ids=[later.pk],
        )
        self.assertEqual(
            allowed.policy,
            IgCheckoutProposal.PaymentPolicy.FULL_OR_200_COD,
        )
        self.assertEqual(allowed.evidence_kind, "quick_reply")

    @patch("storefront.views.monobank._monobank_api_request")
    def test_generation_invoice_has_1500_validity_and_stable_series(self, provider):
        provider.return_value = {
            "invoiceId": "v2-invoice-1",
            "pageUrl": "https://pay.example/v2-invoice-1",
        }
        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        self._open(proposal)

        response = self.client.post(
            reverse(
                "ig_checkout_proposal",
                kwargs={"proposal_id": proposal.public_id},
            ),
            self._delivery_payload(payment_choice="online_full"),
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        generation = IgCheckoutInvoiceGeneration.objects.get(
            proposal=proposal,
            generation=1,
        )
        attempt = generation.payment_attempt
        self.assertEqual(generation.generation, 1)
        self.assertEqual(generation.active_slot, 1)
        self.assertEqual(generation.state, generation.State.INVOICE_CREATED)
        self.assertEqual(attempt.checkout_generation, 1)
        self.assertEqual(attempt.checkout_series_key, generation.series_key)
        self.assertEqual(attempt.invoice_payload["request"]["validity"], 1500)
        self.assertEqual(provider.call_count, 1)
        self.assertGreater(generation.expires_at, timezone.now() + timedelta(minutes=24))
        self.assertLess(generation.expires_at, timezone.now() + timedelta(minutes=26))

    @patch("storefront.views.monobank._monobank_api_request")
    def test_deterministic_failure_releases_generation_and_retry_creates_next(self, provider):
        class DeterministicProviderError(RuntimeError):
            ambiguous = False

        provider.side_effect = [
            DeterministicProviderError("rejected before invoice"),
            {
                "invoiceId": "v2-invoice-2",
                "pageUrl": "https://pay.example/v2-invoice-2",
            },
        ]
        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        self._open(proposal)
        url = reverse(
            "ig_checkout_proposal",
            kwargs={"proposal_id": proposal.public_id},
        )
        first = self.client.post(
            url,
            self._delivery_payload(),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(first.status_code, 400)
        second = self.client.post(
            url,
            self._delivery_payload(),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(second.status_code, 200, second.content)

        generations = list(
            IgCheckoutInvoiceGeneration.objects.filter(proposal=proposal)
            .order_by("generation")
        )
        self.assertEqual([row.generation for row in generations], [1, 2])
        self.assertEqual(generations[0].state, generations[0].State.FAILED)
        self.assertIsNone(generations[0].active_slot)
        self.assertEqual(generations[1].state, generations[1].State.INVOICE_CREATED)
        attempts = list(
            PaymentAttempt.objects.filter(
                checkout_series_key=generations[0].series_key
            ).order_by("checkout_generation")
        )
        self.assertEqual(len(attempts), 2)
        self.assertNotEqual(attempts[0].fingerprint, attempts[1].fingerprint)

    def test_forged_200_cod_post_is_rejected_for_full_only_policy(self):
        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        self._open(proposal)
        response = self.client.post(
            reverse(
                "ig_checkout_proposal",
                kwargs={"proposal_id": proposal.public_id},
            ),
            self._delivery_payload(payment_choice="prepay_200_cod"),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "payment_choice")
        self.assertFalse(IgCheckoutInvoiceGeneration.objects.exists())

    def test_direct_200_policy_creates_prepay_200_attempt(self):
        message = InstagramBotMessage.objects.create(
            client=self.client_row,
            sender_id=self.client_row.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Чи можна 200 грн передоплати, а решту післяплатою?",
        )
        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="prepayment",
            requested_payment_amount=Decimal("200.00"),
            item_specs=[self._item()],
            evidence={"message_ids": [message.pk]},
        )
        self.assertEqual(
            proposal.payment_policy,
            proposal.PaymentPolicy.FULL_OR_200_COD,
        )
        generation = self._create_invoice(
            proposal,
            invoice_id="v2-prepay-200",
            payment_choice="prepay_200_cod",
        )
        self.assertEqual(
            generation.payment_attempt.pay_type,
            PaymentAttempt.PayType.PREPAY_200,
        )
        self.assertEqual(generation.payment_attempt.payment_amount, Decimal("200.00"))
        self.assertEqual(
            generation.payment_attempt.invoice_payload["request"]["validity"],
            1500,
        )

    def test_verified_winner_materializes_one_idempotent_order(self):
        from storefront.views.monobank import _apply_payment_attempt_status

        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        generation = self._create_invoice(proposal, invoice_id="v2-winner")
        attempt = generation.payment_attempt
        order, created = _apply_payment_attempt_status(
            attempt,
            "success",
            payload={"paidAmount": 90000},
            source="provider_pull",
        )

        self.assertTrue(created)
        self.assertIsNotNone(order)
        generation.refresh_from_db()
        attempt.refresh_from_db()
        proposal.refresh_from_db()
        self.assertEqual(generation.state, generation.State.PAID_WINNER)
        self.assertEqual(generation.winner_slot, 1)
        self.assertTrue(attempt.checkout_winner_claimed)
        self.assertEqual(attempt.order_id, order.pk)
        self.assertEqual(proposal.winner_invoice_generation_id, generation.pk)
        self.assertEqual(proposal.status, proposal.Status.PAID)
        self.assertTrue(order.checkout_idempotency_key)

        replay, replay_created = _apply_payment_attempt_status(
            attempt,
            "success",
            payload={"paidAmount": 90000},
            source="provider_pull",
        )
        self.assertEqual(replay.pk, order.pk)
        self.assertFalse(replay_created)
        self.assertEqual(Order.objects.count(), 1)

    def test_late_paid_loser_never_creates_second_order_or_downgrades_winner(self):
        from management.services.ig_checkout_generation import (
            terminalize_generation_attempt,
        )
        from storefront.views.monobank import _apply_payment_attempt_status

        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        first = self._create_invoice(proposal, invoice_id="v2-old")
        terminalize_generation_attempt(
            first.payment_attempt_id,
            terminal_status=PaymentAttempt.Status.FAILED,
            reason="provider_failure",
        )
        proposal.refresh_from_db()
        second = self._create_invoice(proposal, invoice_id="v2-new")
        winner_order, _created = _apply_payment_attempt_status(
            second.payment_attempt,
            "success",
            payload={"paidAmount": 90000},
            source="provider_pull",
        )
        loser_order, loser_created = _apply_payment_attempt_status(
            first.payment_attempt,
            "success",
            payload={"paidAmount": 90000},
            source="provider_pull",
        )

        self.assertIsNone(loser_order)
        self.assertFalse(loser_created)
        first.refresh_from_db()
        second.refresh_from_db()
        proposal.refresh_from_db()
        self.assertEqual(first.state, first.State.LATE_PAID_REVIEW)
        self.assertEqual(second.state, second.State.PAID_WINNER)
        self.assertEqual(proposal.winner_invoice_generation_id, second.pk)
        self.assertEqual(proposal.status, proposal.Status.PAID)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(winner_order.pk, Order.objects.get().pk)

    def test_old_negative_callback_cannot_downgrade_paid_winner(self):
        from management.services.ig_checkout_generation import (
            terminalize_generation_attempt,
        )
        from storefront.views.monobank import _apply_payment_attempt_status

        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        first = self._create_invoice(proposal, invoice_id="v2-negative-old")
        terminalize_generation_attempt(
            first.payment_attempt_id,
            terminal_status=PaymentAttempt.Status.FAILED,
            reason="provider_failure",
        )
        proposal.refresh_from_db()
        second = self._create_invoice(proposal, invoice_id="v2-negative-winner")
        _apply_payment_attempt_status(
            second.payment_attempt,
            "success",
            payload={"paidAmount": 90000},
            source="provider_pull",
        )
        _apply_payment_attempt_status(
            first.payment_attempt,
            "expired",
            payload={},
            source="provider_pull",
        )

        proposal.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(proposal.status, proposal.Status.PAID)
        self.assertEqual(proposal.winner_invoice_generation_id, second.pk)
        self.assertEqual(second.state, second.State.PAID_WINNER)

    def test_late_old_success_with_released_stock_enters_review_not_order(self):
        from management.services.ig_checkout_generation import (
            terminalize_generation_attempt,
        )
        from product_catalog.models import ProductInventoryPolicy
        from productcolors.models import Color, ProductColorVariant
        from storefront.views.monobank import _apply_payment_attempt_status

        color = Color.objects.create(name="Generation black", primary_hex="#111111")
        variant = ProductColorVariant.objects.create(
            product=self.product,
            color=color,
            stock=2,
        )
        ProductInventoryPolicy.objects.create(
            product=self.product,
            source=ProductInventoryPolicy.Source.CATALOG_VARIANT,
        )
        item = {**self._item(), "color_variant_id": variant.pk}
        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="online_full",
            item_specs=[item],
        )
        first = self._create_invoice(proposal, invoice_id="v2-stock-old")
        first_reservation = first.inventory_reservations.get()
        terminalize_generation_attempt(
            first.payment_attempt_id,
            terminal_status=PaymentAttempt.Status.FAILED,
            reason="provider_failure",
        )
        first_reservation.refresh_from_db()
        self.assertEqual(first_reservation.state, first_reservation.State.RELEASED)
        proposal.refresh_from_db()
        second = self._create_invoice(proposal, invoice_id="v2-stock-new")

        order, created = _apply_payment_attempt_status(
            first.payment_attempt,
            "success",
            payload={"paidAmount": 90000},
            source="provider_pull",
        )

        self.assertIsNone(order)
        self.assertFalse(created)
        first.refresh_from_db()
        second.refresh_from_db()
        proposal.refresh_from_db()
        variant.refresh_from_db()
        self.assertEqual(first.state, first.State.RESOURCE_REVIEW)
        self.assertIsNone(first.winner_slot)
        self.assertEqual(second.state, second.State.CANCELLED)
        self.assertIsNone(second.active_slot)
        self.assertEqual(proposal.status, proposal.Status.MANAGER_REVIEW)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(variant.stock, 2)

    def test_local_generation_expiry_does_not_expire_12_hour_proposal(self):
        from management.services.ig_checkout_terminalization import (
            terminalize_payment_attempt,
        )

        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        generation = self._create_invoice(proposal, invoice_id="v2-local-expiry")
        expired_at = timezone.now() - timedelta(seconds=1)
        IgCheckoutInvoiceGeneration.objects.filter(pk=generation.pk).update(
            expires_at=expired_at
        )
        PaymentAttempt.objects.filter(pk=generation.payment_attempt_id).update(
            invoice_expires_at=expired_at
        )

        outcome = terminalize_payment_attempt(
            generation.payment_attempt_id,
            terminal_status=PaymentAttempt.Status.EXPIRED,
            reason="invoice_expired",
            source="system_expiry",
            require_due=True,
        )

        self.assertEqual(outcome.outcome, "terminalized")
        generation.refresh_from_db()
        proposal.refresh_from_db()
        self.deal = proposal.deal
        self.deal.refresh_from_db()
        self.assertEqual(generation.state, generation.State.EXPIRED)
        self.assertIsNone(generation.active_slot)
        self.assertIn(proposal.status, {proposal.Status.READY, proposal.Status.VIEWED})
        self.assertGreater(proposal.expires_at, timezone.now() + timedelta(hours=11))
        self.assertEqual(self.deal.active_checkout_proposal_id, proposal.pk)

    def test_provider_create_ambiguity_is_bounded_review_and_never_blind_retried(self):
        from management.services.ig_checkout_generation import (
            resolve_due_generation_ambiguities,
        )

        class AmbiguousTimeout(RuntimeError):
            ambiguous = True

        from product_catalog.models import ProductInventoryPolicy
        from productcolors.models import Color, ProductColorVariant

        user = get_user_model().objects.create_user(username="s2b-ambiguity-owner")
        self.client.force_login(user)
        promo = PromoCode.objects.create(
            code="S2BAMB",
            discount_type="percentage",
            discount_value=Decimal("5.00"),
            max_uses=10,
            one_time_per_user=True,
        )
        color = Color.objects.create(name="Ambiguity black", primary_hex="#222222")
        variant = ProductColorVariant.objects.create(
            product=self.product,
            color=color,
            stock=2,
        )
        ProductInventoryPolicy.objects.create(
            product=self.product,
            source=ProductInventoryPolicy.Source.CATALOG_VARIANT,
        )
        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="online_full",
            item_specs=[{**self._item(), "color_variant_id": variant.pk}],
            allow_promo=True,
        )
        self._open(proposal)
        url = reverse(
            "ig_checkout_proposal",
            kwargs={"proposal_id": proposal.public_id},
        )
        with patch(
            "storefront.views.monobank._monobank_api_request",
            side_effect=AmbiguousTimeout("timeout after dispatch"),
        ) as provider:
            first = self.client.post(
                url,
                self._delivery_payload(promo_code=promo.code),
                HTTP_ACCEPT="application/json",
            )
            second = self.client.post(
                url,
                self._delivery_payload(promo_code=promo.code),
                HTTP_ACCEPT="application/json",
            )
        self.assertEqual(first.status_code, 400)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(provider.call_count, 1)
        generation = IgCheckoutInvoiceGeneration.objects.get(proposal=proposal)
        attempt = generation.payment_attempt
        reservation = generation.inventory_reservations.get()
        self.assertEqual(generation.state, generation.State.PROVIDER_AMBIGUOUS)
        self.assertEqual(generation.active_slot, 1)
        self.assertTrue(generation.provider_request_digest)
        self.assertGreater(generation.ambiguity_review_due_at, generation.expires_at)
        event = generation.events.get(kind="provider_ambiguous")
        self.assertEqual(event.payload["attempt_reference"], attempt.reference)
        self.assertEqual(event.payload["request_digest"], generation.provider_request_digest)
        self.assertTrue(
            IgBotNotification.objects.filter(
                dedupe_key__startswith="ig-checkout-generation-ambiguity:"
            ).exists()
        )

        due = timezone.now() - timedelta(seconds=1)
        IgCheckoutInvoiceGeneration.objects.filter(pk=generation.pk).update(
            ambiguity_review_due_at=due
        )
        outcome = resolve_due_generation_ambiguities(now=timezone.now())
        self.assertEqual(outcome["resolved"], 1)
        generation.refresh_from_db()
        proposal.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(generation.state, generation.State.AMBIGUITY_REVIEW)
        self.assertIsNone(generation.active_slot)
        self.assertEqual(proposal.status, proposal.Status.MANAGER_REVIEW)
        self.assertEqual(attempt.status, PaymentAttempt.Status.FAILED)
        reservation.refresh_from_db()
        promo.refresh_from_db()
        self.assertEqual(reservation.state, reservation.State.RELEASED)
        self.assertEqual(promo.current_uses, 0)

        with patch("storefront.views.monobank._monobank_api_request") as retry:
            blocked = self.client.post(
                url,
                self._delivery_payload(promo_code=promo.code),
                HTTP_ACCEPT="application/json",
            )
        self.assertEqual(blocked.status_code, 400)
        retry.assert_not_called()

    def test_late_pending_status_cannot_downgrade_winner(self):
        from management.services.ig_checkout_generation import (
            apply_generation_provider_status,
        )
        from storefront.views.monobank import _apply_payment_attempt_status

        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        generation = self._create_invoice(proposal, invoice_id="v2-pending-winner")
        order, _created = _apply_payment_attempt_status(
            generation.payment_attempt,
            "success",
            payload={"paidAmount": 90000},
            source="provider_pull",
        )
        apply_generation_provider_status(
            generation.payment_attempt_id,
            "processing",
            payload={},
            source="provider_pull",
        )
        generation.payment_attempt.refresh_from_db()
        generation.refresh_from_db()
        self.assertEqual(generation.payment_attempt.status, PaymentAttempt.Status.CONVERTED)
        self.assertEqual(generation.payment_attempt.order_id, order.pk)
        self.assertEqual(generation.state, generation.State.PAID_WINNER)

    def test_late_provider_create_success_is_reviewed_without_repointing(self):
        from management.services.ig_checkout_generation import (
            terminalize_generation_attempt,
        )

        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        self._open(proposal)
        raced = {}

        def late_success(*_args, **_kwargs):
            generation = IgCheckoutInvoiceGeneration.objects.get(proposal=proposal)
            terminalize_generation_attempt(
                generation.payment_attempt_id,
                terminal_status=PaymentAttempt.Status.FAILED,
                reason="concurrent_terminalization",
            )
            generation.refresh_from_db()
            proposal.refresh_from_db()
            new_attempt = PaymentAttempt.objects.create(
                fingerprint=hashlib.sha256(b"late-provider-new-attempt").hexdigest(),
                full_name="Іван Петренко",
                phone="+380501112233",
                city="Київ",
                np_office="Відділення №12",
                pay_type=PaymentAttempt.PayType.ONLINE_FULL,
                status=PaymentAttempt.Status.PROCESSING,
                cart_snapshot={
                    "checkout_surface": "instagram_proposal",
                    "proposal_id": str(proposal.public_id),
                    "cart": [],
                },
                gross_amount=proposal.catalog_total,
                payable_amount=proposal.quoted_total,
                payment_amount=proposal.quoted_total,
                monobank_invoice_id="v2-newer-payable",
                invoice_url="https://pay.example/v2-newer-payable",
                invoice_expires_at=timezone.now() + timedelta(minutes=25),
                checkout_series_key=generation.series_key,
                checkout_generation=2,
            )
            new_generation = IgCheckoutInvoiceGeneration.objects.create(
                proposal=proposal,
                generation=2,
                series_key=generation.series_key,
                proposal_revision=proposal.revision,
                active_slot=1,
                state=IgCheckoutInvoiceGeneration.State.INVOICE_CREATED,
                payment_amount=proposal.quoted_total,
                payment_attempt=new_attempt,
                provider_invoice_id=new_attempt.monobank_invoice_id,
                provider_call_token=hashlib.sha256(
                    b"late-provider-new-call"
                ).hexdigest(),
                expires_at=new_attempt.invoice_expires_at,
            )
            proposal.current_invoice_generation = new_generation
            proposal.payment_attempt = new_attempt
            proposal.status = proposal.Status.INVOICE_CREATED
            proposal.save(update_fields=[
                "current_invoice_generation", "payment_attempt", "status", "updated_at",
            ])
            raced["generation_id"] = new_generation.pk
            raced["attempt_id"] = new_attempt.pk
            return {
                "invoiceId": "v2-late-create",
                "pageUrl": "https://pay.example/v2-late-create",
            }

        with patch(
            "storefront.views.monobank._monobank_api_request",
            side_effect=late_success,
        ):
            response = self.client.post(
                reverse(
                    "ig_checkout_proposal",
                    kwargs={"proposal_id": proposal.public_id},
                ),
                self._delivery_payload(),
                HTTP_ACCEPT="application/json",
            )
        self.assertEqual(response.status_code, 400)
        generation = IgCheckoutInvoiceGeneration.objects.get(
            proposal=proposal,
            generation=1,
        )
        proposal.refresh_from_db()
        self.assertEqual(generation.state, generation.State.LATE_PROVIDER_REVIEW)
        self.assertIsNone(generation.active_slot)
        self.assertNotEqual(proposal.current_invoice_generation_id, generation.pk)
        self.assertNotEqual(proposal.payment_attempt_id, generation.payment_attempt_id)
        self.assertEqual(generation.provider_invoice_id, "v2-late-create")
        newer = IgCheckoutInvoiceGeneration.objects.get(pk=raced["generation_id"])
        newer_attempt = PaymentAttempt.objects.get(pk=raced["attempt_id"])
        self.assertEqual(newer.state, newer.State.CANCELLED)
        self.assertIsNone(newer.active_slot)
        self.assertEqual(newer_attempt.status, PaymentAttempt.Status.CANCELLED)
        self.assertEqual(proposal.status, proposal.Status.MANAGER_REVIEW)
        self.assertIsNone(proposal.current_invoice_generation_id)
        with patch("storefront.views.monobank._monobank_api_request") as provider:
            blocked = self.client.post(
                reverse(
                    "ig_checkout_proposal",
                    kwargs={"proposal_id": proposal.public_id},
                ),
                self._delivery_payload(),
                HTTP_ACCEPT="application/json",
            )
        self.assertEqual(blocked.status_code, 400)
        provider.assert_not_called()
        status = self.client.get(
            reverse(
                "ig_checkout_status",
                kwargs={"proposal_id": proposal.public_id},
            )
        )
        self.assertEqual(status.json()["ui_state"], "cancellation_ambiguous")

    def test_authenticated_stale_promo_generation_enters_resource_review(self):
        from management.services.ig_checkout_generation import (
            terminalize_generation_attempt,
        )
        from storefront.views.monobank import _apply_payment_attempt_status

        user = get_user_model().objects.create_user(username="s2b-promo-owner")
        self.client.force_login(user)
        promo = PromoCode.objects.create(
            code="S2BAUTH",
            discount_type="percentage",
            discount_value=Decimal("5.00"),
            max_uses=10,
            one_time_per_user=True,
        )
        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="online_full",
            item_specs=[self._item()],
            allow_promo=True,
        )
        self._open(proposal)
        with patch(
            "storefront.views.monobank._monobank_api_request",
            side_effect=[
                {"invoiceId": "promo-old", "pageUrl": "https://pay/promo-old"},
                {"invoiceId": "promo-new", "pageUrl": "https://pay/promo-new"},
            ],
        ):
            url = reverse(
                "ig_checkout_proposal",
                kwargs={"proposal_id": proposal.public_id},
            )
            first_response = self.client.post(
                url,
                self._delivery_payload(promo_code=promo.code),
                HTTP_ACCEPT="application/json",
            )
            self.assertEqual(first_response.status_code, 200)
            first = IgCheckoutInvoiceGeneration.objects.get(
                proposal=proposal,
                generation=1,
            )
            first_owner = first.promo_reservation_generation
            terminalize_generation_attempt(
                first.payment_attempt_id,
                terminal_status=PaymentAttempt.Status.FAILED,
                reason="provider_failure",
            )
            proposal.refresh_from_db()
            second_response = self.client.post(
                url,
                self._delivery_payload(promo_code=promo.code),
                HTTP_ACCEPT="application/json",
            )
            self.assertEqual(second_response.status_code, 200)
        second = IgCheckoutInvoiceGeneration.objects.get(
            proposal=proposal,
            generation=2,
        )
        self.assertTrue(first_owner)
        self.assertTrue(second.promo_reservation_generation)
        self.assertNotEqual(first_owner, second.promo_reservation_generation)

        order, created = _apply_payment_attempt_status(
            first.payment_attempt,
            "success",
            payload={"paidAmount": 90000},
            source="provider_pull",
        )
        self.assertIsNone(order)
        self.assertFalse(created)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.state, first.State.RESOURCE_REVIEW)
        self.assertEqual(second.state, second.State.CANCELLED)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(PromoCodeUsage.objects.filter(promo_code=promo).exists())
        payment_event = IgPaymentEvent.objects.get(deal=proposal.deal)
        from management.models import provider_evidence_signature

        self.assertEqual(
            payment_event.evidence["signature"],
            provider_evidence_signature(
                deal_id=proposal.deal_id,
                client_id=proposal.client_id,
                provider=payment_event.provider,
                source=payment_event.source,
                invoice_id=payment_event.invoice_id,
                provider_status=payment_event.provider_status,
                payload_digest=payment_event.payload_digest,
            ),
        )
        projection = IgPaymentProjection.objects.get(deal=proposal.deal)
        self.assertEqual(projection.truth, proposal.deal.PaymentTruth.CONFIRMED)
        self.assertEqual(projection.last_event_id, payment_event.pk)

    def test_ambiguity_then_manager_order_late_success_never_creates_second_order(self):
        from management.services.ig_checkout_generation import (
            resolve_due_generation_ambiguities,
        )
        from storefront.views.monobank import _apply_payment_attempt_status

        class AmbiguousTimeout(RuntimeError):
            ambiguous = True

        proposal = create_or_update_proposal(
            client=self.client_row,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        self._open(proposal)
        with patch(
            "storefront.views.monobank._monobank_api_request",
            side_effect=AmbiguousTimeout("dispatch timeout"),
        ):
            response = self.client.post(
                reverse(
                    "ig_checkout_proposal",
                    kwargs={"proposal_id": proposal.public_id},
                ),
                self._delivery_payload(),
                HTTP_ACCEPT="application/json",
            )
        self.assertEqual(response.status_code, 400)
        generation = IgCheckoutInvoiceGeneration.objects.get(proposal=proposal)
        IgCheckoutInvoiceGeneration.objects.filter(pk=generation.pk).update(
            ambiguity_review_due_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(
            resolve_due_generation_ambiguities(now=timezone.now())["resolved"],
            1,
        )
        manager_order = Order.objects.create(
            full_name="Manager resolved",
            phone="+380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("900.00"),
            source="manual",
            sale_source="Instagram",
        )
        deal = proposal.deal
        deal.order = manager_order
        deal.status = deal.Status.ORDER_CREATED
        deal.payment_status = "paid"
        deal.save(update_fields=["order", "status", "payment_status", "updated_at"])

        late_order, created = _apply_payment_attempt_status(
            generation.payment_attempt,
            "success",
            payload={"paidAmount": 90000},
            source="provider_pull",
        )
        self.assertIsNone(late_order)
        self.assertFalse(created)
        generation.refresh_from_db()
        generation.payment_attempt.refresh_from_db()
        proposal.refresh_from_db()
        self.assertEqual(generation.state, generation.State.LATE_PAID_REVIEW)
        self.assertIsNone(generation.payment_attempt.order_id)
        self.assertEqual(proposal.status, proposal.Status.MANAGER_REVIEW)
        self.assertEqual(Order.objects.count(), 1)
        payment_event = IgPaymentEvent.objects.get(
            event_key=f"attempt:{generation.payment_attempt_id}:verified"
        )
        self.assertEqual(payment_event.provider_status, "success")
        projection = IgPaymentProjection.objects.get(deal=deal)
        self.assertEqual(projection.last_event_id, payment_event.pk)

        replay_order, replay_created = _apply_payment_attempt_status(
            generation.payment_attempt,
            "success",
            payload={"paidAmount": 90000},
            source="provider_pull",
        )
        self.assertIsNone(replay_order)
        self.assertFalse(replay_created)
        self.assertEqual(Order.objects.count(), 1)
