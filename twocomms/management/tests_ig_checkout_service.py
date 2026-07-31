from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgCheckoutProposal,
    IgClient,
    IgDeal,
    IgDealItem,
    InstagramBotMessage,
)
from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductFitOption, ProductStatus


class InstagramCheckoutConfigurationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Футболки", slug="ig-checkout-shirts")
        self.shirt = Product.objects.create(
            title="Футболка Київ",
            slug="ig-checkout-shirt",
            category=self.category,
            price=950,
            status=ProductStatus.PUBLISHED,
        )
        self.classic = ProductFitOption.objects.create(
            product=self.shirt,
            code="classic",
            label="Класичний",
            is_active=True,
        )
        self.oversize = ProductFitOption.objects.create(
            product=self.shirt,
            code="oversize",
            label="Оверсайз",
            is_active=True,
        )
        blue = Color.objects.create(name="Синій", primary_hex="#2255AA")
        black = Color.objects.create(name="Чорний", primary_hex="#111111")
        self.blue = ProductColorVariant.objects.create(
            product=self.shirt,
            color=blue,
            stock=5,
            sku="TEE-BLUE",
        )
        self.black = ProductColorVariant.objects.create(
            product=self.shirt,
            color=black,
            stock=5,
            sku="TEE-BLACK",
        )
        self.client = IgClient.get_or_create_for_sender("ig-checkout-service")

    def _valid_item(self, **overrides):
        item = {
            "product_id": self.shirt.pk,
            "color_variant_id": self.blue.pk,
            "qty": 1,
            "size": "M",
            "fit_option_code": "classic",
        }
        item.update(overrides)
        return item

    def test_tshirt_requires_fit_size_and_color(self):
        from management.services.ig_checkout import (
            CheckoutConfigurationError,
            validate_checkout_items,
        )

        with self.assertRaises(CheckoutConfigurationError) as ctx:
            validate_checkout_items(
                client=self.client,
                item_specs=[{"product_id": self.shirt.pk, "qty": 1}],
                evidence={},
            )
        self.assertEqual(ctx.exception.missing_fields, {"size", "fit", "color"})

    def test_wrong_variant_inactive_fit_and_invalid_size_fail_closed(self):
        from management.services.ig_checkout import (
            CheckoutConfigurationError,
            validate_checkout_items,
        )

        other = Product.objects.create(
            title="Інша футболка",
            slug="ig-checkout-other-shirt",
            category=self.category,
            price=790,
            status=ProductStatus.PUBLISHED,
        )
        other_color = Color.objects.create(name="Білий", primary_hex="#FFFFFF")
        wrong_variant = ProductColorVariant.objects.create(
            product=other,
            color=other_color,
            stock=2,
        )
        self.oversize.is_active = False
        self.oversize.save(update_fields=["is_active"])

        cases = (
            (self._valid_item(color_variant_id=wrong_variant.pk), "invalid_color"),
            (self._valid_item(fit_option_code="oversize"), "invalid_fit"),
            (self._valid_item(size="NOT-A-SIZE"), "invalid_size"),
        )
        for item, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(CheckoutConfigurationError) as ctx:
                    validate_checkout_items(
                        client=self.client,
                        item_specs=[item],
                        evidence={},
                    )
                self.assertEqual(ctx.exception.code, code)

    def test_unpublished_and_insufficient_stock_fail_closed(self):
        from management.services.ig_checkout import (
            CheckoutConfigurationError,
            validate_checkout_items,
        )

        self.shirt.status = ProductStatus.DRAFT
        self.shirt.save(update_fields=["status"])
        with self.assertRaises(CheckoutConfigurationError) as unpublished:
            validate_checkout_items(
                client=self.client,
                item_specs=[self._valid_item()],
                evidence={},
            )
        self.assertEqual(unpublished.exception.code, "unpublished_product")

        self.shirt.status = ProductStatus.PUBLISHED
        self.shirt.save(update_fields=["status"])
        with self.assertRaises(CheckoutConfigurationError) as stock:
            validate_checkout_items(
                client=self.client,
                item_specs=[self._valid_item(qty=6)],
                evidence={},
            )
        self.assertEqual(stock.exception.code, "insufficient_stock")

    def test_multi_item_quote_preserves_fit_size_color_and_exact_total(self):
        from management.services.ig_checkout import create_or_update_proposal

        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[
                self._valid_item(color_variant_id=self.blue.pk, size="M", fit_option_code="classic"),
                self._valid_item(color_variant_id=self.black.pk, size="L", fit_option_code="oversize"),
            ],
        )

        self.assertEqual(proposal.items.count(), 2)
        self.assertEqual(proposal.catalog_total, Decimal("1900.00"))
        self.assertEqual(proposal.quoted_total, Decimal("1900.00"))
        self.assertEqual(
            list(
                proposal.items.order_by("position").values_list(
                    "color_label", "fit_code", "size", "quantity"
                )
            ),
            [
                ("Синій", "classic", "M", 1),
                ("Чорний", "oversize", "L", 1),
            ],
        )

    def test_negotiated_total_is_order_discount_not_invented_line_price(self):
        from management.services.ig_checkout import create_or_update_proposal

        offer = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role="manager",
            text="За дві футболки разом 1700 грн",
        )
        accepted = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role="user",
            text="Так, оформлюйте",
        )
        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[
                self._valid_item(color_variant_id=self.blue.pk, size="M"),
                self._valid_item(color_variant_id=self.black.pk, size="L", fit_option_code="oversize"),
            ],
            negotiated_total=Decimal("1700.00"),
            evidence={"message_ids": [offer.pk, accepted.pk]},
        )

        self.assertEqual(proposal.catalog_total, Decimal("1900.00"))
        self.assertEqual(proposal.negotiated_discount, Decimal("200.00"))
        self.assertEqual(proposal.quoted_total, Decimal("1700.00"))
        self.assertEqual(
            sum(item.quoted_line_total for item in proposal.items.all()),
            Decimal("1900.00"),
        )
        proposal.deal.refresh_from_db()
        self.assertEqual(proposal.deal.amount, Decimal("1700.00"))

    def test_identical_replay_reuses_proposal_and_revision(self):
        from management.services.ig_checkout import create_or_update_proposal

        kwargs = {
            "client": self.client,
            "pay_type": "online_full",
            "item_specs": [self._valid_item()],
        }
        first = create_or_update_proposal(**kwargs)
        second = create_or_update_proposal(**kwargs)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(second.revision, 1)
        self.assertEqual(second.revisions.count(), 1)
        self.assertEqual(IgDeal.objects.filter(client=self.client).count(), 1)

    def test_identical_replay_after_expiry_issues_fresh_proposal(self):
        from management.services.ig_checkout import create_or_update_proposal

        kwargs = {
            "client": self.client,
            "pay_type": "online_full",
            "item_specs": [self._valid_item()],
        }
        first = create_or_update_proposal(**kwargs)
        first.expires_at = timezone.now() - timedelta(seconds=1)
        first.save(update_fields=["expires_at", "updated_at"])

        second = create_or_update_proposal(**kwargs)

        first.refresh_from_db()
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(first.status, IgCheckoutProposal.Status.EXPIRED)
        self.assertEqual(second.revision, 1)
        self.assertEqual(second.deal.active_checkout_proposal_id, second.pk)

    def test_allow_promo_policy_is_part_of_proposal_digest(self):
        from management.services.ig_checkout import create_or_update_proposal

        base = {
            "client": self.client,
            "pay_type": "online_full",
            "item_specs": [self._valid_item()],
        }
        first = create_or_update_proposal(**base, allow_promo=False)
        second = create_or_update_proposal(**base, allow_promo=True)

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(second.revision, 2)
        self.assertNotEqual(second.items_digest, first.items_digest)

    def test_ai_model_message_cannot_authorize_negotiated_price(self):
        from management.services.ig_checkout import (
            CheckoutConfigurationError,
            create_or_update_proposal,
        )

        offer = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role="model",
            text="За футболку 800 грн",
        )
        accepted = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role="user",
            text="Так, оформлюйте",
        )
        with self.assertRaises(CheckoutConfigurationError) as ctx:
            create_or_update_proposal(
                client=self.client,
                pay_type="online_full",
                item_specs=[self._valid_item()],
                negotiated_total=Decimal("800.00"),
                evidence={"message_ids": [offer.pk, accepted.pk]},
            )
        self.assertEqual(ctx.exception.code, "invalid_price_evidence")

    def test_revision_updates_proposal_deal_items_and_episode_atomically(self):
        from management.services.ig_checkout import create_or_update_proposal

        first = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._valid_item()],
        )
        second = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._valid_item(color_variant_id=self.black.pk, size="L")],
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(second.revision, 2)
        self.assertEqual(second.revisions.count(), 2)
        self.assertEqual(second.items.get().color_variant_id, self.black.pk)
        self.assertEqual(second.deal.items.get().color_variant_id, self.black.pk)
        second.commercial_episode.refresh_from_db()
        self.assertEqual(
            second.commercial_episode.product_snapshot[0]["color_variant_id"],
            self.black.pk,
        )
        self.assertEqual(
            second.commercial_episode.price_snapshot["negotiated_total"],
            "950.00",
        )

    def test_revision_failure_rolls_back_deal_and_proposal_together(self):
        from management.models import IgCheckoutRevision
        from management.services.ig_checkout import create_or_update_proposal

        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._valid_item()],
        )
        with patch.object(
            IgCheckoutRevision.objects,
            "create",
            side_effect=RuntimeError("revision write failed"),
        ):
            with self.assertRaisesMessage(RuntimeError, "revision write failed"):
                create_or_update_proposal(
                    client=self.client,
                    pay_type="online_full",
                    item_specs=[self._valid_item(color_variant_id=self.black.pk, size="L")],
                )

        proposal.refresh_from_db()
        self.assertEqual(proposal.revision, 1)
        self.assertEqual(proposal.items.get().color_variant_id, self.blue.pk)
        self.assertEqual(IgDealItem.objects.get(deal=proposal.deal).color_variant_id, self.blue.pk)

    def test_invoice_created_proposal_cannot_be_mutated(self):
        from management.services.ig_checkout import (
            CheckoutConfigurationError,
            create_or_update_proposal,
        )

        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._valid_item()],
        )
        proposal.status = IgCheckoutProposal.Status.INVOICE_CREATED
        proposal.save(update_fields=["status", "updated_at"])

        with self.assertRaises(CheckoutConfigurationError) as ctx:
            create_or_update_proposal(
                client=self.client,
                pay_type="online_full",
                item_specs=[self._valid_item(color_variant_id=self.black.pk)],
            )
        self.assertEqual(ctx.exception.code, "proposal_locked")


class InstagramCheckoutLinkBoundaryTests(TestCase):
    def setUp(self):
        from storefront.models import Category, ProductStatus

        category = Category.objects.create(name="IG offer", slug="ig-offer-link")
        self.product = Product.objects.create(
            title="Худі для offer",
            slug="ig-offer-hoodie",
            category=category,
            price=Decimal("950.00"),
            status=ProductStatus.PUBLISHED,
        )
        self.client = IgClient.get_or_create_for_sender("ig-offer-link")

    @patch("storefront.views.monobank._monobank_api_request")
    def test_bot_deal_path_returns_first_party_offer_without_monobank_call(self, provider):
        from management.services import bot_orders

        result = bot_orders.create_deal_and_link(
            self.client,
            pay_type="full",
            product_id=self.product.pk,
            size="M",
        )

        self.assertTrue(result["ok"], result)
        self.assertIn("/offer/a/", result["invoice_url"])
        self.assertEqual(result["invoice_url"], result["proposal_url"])
        provider.assert_not_called()
        deal = IgDeal.objects.get(client=self.client)
        self.assertEqual(deal.invoice_id, "")
        self.assertEqual(deal.invoice_url, "")
        self.assertIsNotNone(deal.active_checkout_proposal_id)
        proposal = deal.active_checkout_proposal
        self.assertEqual(proposal.status, IgCheckoutProposal.Status.READY)
        self.assertEqual(proposal.items.count(), 1)
