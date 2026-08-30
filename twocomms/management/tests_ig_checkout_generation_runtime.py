import hashlib
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

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
    IgClient,
    IgDeal,
    IgFollowUpTask,
    InstagramBotMessage,
)
from management.services.ig_checkout import create_or_update_proposal
from management.services.ig_checkout_policy import (
    PREPAY_200_QUICK_REPLY,
    resolve_payment_policy,
)
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from orders.models import PaymentAttempt
from orders.nova_poshta_checkout import (
    build_city_choice_token,
    build_warehouse_choice_token,
)
from storefront.models import Category, Product, ProductFitOption


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
        generation = IgCheckoutInvoiceGeneration.objects.get(proposal=proposal)
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
