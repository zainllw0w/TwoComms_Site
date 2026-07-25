"""Тести Phase 6 / Task 19 — пост-оплатний потік IG-бота (bot_orders).

Збір даних НП текстом, створення замовлення після оплати, формування посилання
на оплату за тегом [PAYLINK:x]/[PRODUCT:id].
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from management.models import IgClient, IgDeal, IgDealItem, InstagramBotMessage
from management.services import bot_orders
from orders.models import Order


def _paid_deal(igsid, with_np=True):
    c = IgClient.get_or_create_for_sender(igsid)
    d = IgDeal.objects.create(
        client=c, pay_type=IgDeal.PayType.ONLINE_FULL,
        status=IgDeal.Status.PAID, payment_status="paid",
        paid_at=timezone.now(),
        np_full_name=("Іван" if with_np else ""), np_phone=("0931112233" if with_np else ""),
        np_city=("Київ" if with_np else ""), np_office=("Відд 1" if with_np else ""),
        np_settlement_ref=("settlement-ref-1" if with_np else ""),
        np_city_ref=("city-ref-1" if with_np else ""),
        np_warehouse_ref=("warehouse-ref-1" if with_np else ""),
        delivery_status=(IgDeal.DeliveryStatus.VALIDATED if with_np else IgDeal.DeliveryStatus.UNVERIFIED),
        delivery_source=("nova_poshta_directory" if with_np else ""),
    )
    IgDealItem.objects.create(deal=d, title="Худі", qty=1, unit_price=Decimal("950"))
    d.recalc_total()
    return c, d


class FulfillTests(TestCase):
    @patch("management.services.bot_orders.notify_manager")
    def test_fulfill_creates_order_when_ready(self, mock_notify):
        c, d = _paid_deal("o1", with_np=True)
        self.assertTrue(bot_orders.fulfill_if_ready(d))
        d.refresh_from_db()
        self.assertIsNotNone(d.order_id)
        self.assertTrue(mock_notify.called)

    def test_fulfill_false_without_np(self):
        c, d = _paid_deal("o2", with_np=False)
        self.assertFalse(bot_orders.fulfill_if_ready(d))

    def test_fulfill_false_when_not_paid(self):
        c = IgClient.get_or_create_for_sender("o3")
        d = IgDeal.objects.create(
            client=c, status=IgDeal.Status.AWAITING_PAYMENT,
            np_full_name="x", np_phone="0931112233", np_city="Київ", np_office="в1",
        )
        IgDealItem.objects.create(deal=d, title="x", qty=1, unit_price=Decimal("100"))
        d.recalc_total()
        self.assertFalse(bot_orders.fulfill_if_ready(d))

    def test_fulfill_false_for_unverified_paid_stage(self):
        c = IgClient.get_or_create_for_sender("o-forged-paid")
        d = IgDeal.objects.create(
            client=c,
            status=IgDeal.Status.PAID,
            payment_status="unpaid",
            np_full_name="Іван",
            np_phone="0931112233",
            np_city="Київ",
            np_office="Відділення 1",
        )
        IgDealItem.objects.create(deal=d, title="x", qty=1, unit_price=Decimal("100"))
        d.recalc_total()

        self.assertFalse(bot_orders.fulfill_if_ready(d))
        self.assertIsNone(d.order_id)
        with self.assertRaisesMessage(ValueError, "provider-confirmed payment"):
            bot_orders.create_order_from_deal(d)

    def test_manager_only_receipt_order_does_not_record_purchase(self):
        from management.ig_bot_models import IgPaymentConfirmationReview
        from management.services.ig_payment_review import record_review_decision
        from storefront.models import UserAction

        client = IgClient.get_or_create_for_sender("manager-only-order-builder")
        deal = IgDeal.objects.create(
            client=client,
            pay_type=IgDeal.PayType.ONLINE_FULL,
            np_full_name="Іван",
            np_phone="0931112233",
            np_city="Київ",
            np_office="Відділення 1",
            np_settlement_ref="settlement-ref-1",
            np_city_ref="city-ref-1",
            np_warehouse_ref="warehouse-ref-1",
            delivery_status=IgDeal.DeliveryStatus.VALIDATED,
            delivery_source="nova_poshta_directory",
        )
        IgDealItem.objects.create(deal=deal, title="Футболка", qty=1, unit_price=Decimal("950"))
        deal.recalc_total()
        review = IgPaymentConfirmationReview.objects.create(
            client=client,
            deal=deal,
            dedupe_key="manager-only-order-builder-review",
        )
        actor = get_user_model().objects.create_user(
            username="manager-only-order-builder-actor", is_staff=True,
        )
        record_review_decision(review, actor=actor, decision="manager_verified")

        order = bot_orders.create_order_from_deal(deal)

        self.assertEqual(order.payment_status, "unpaid")
        self.assertFalse(
            UserAction.objects.filter(action_type="purchase", order_id=order.pk).exists()
        )


class ExtractNpTests(TestCase):
    @patch("management.services.bot_orders.gemini_generate_text")
    def test_extract_np(self, mock_gen):
        mock_gen.return_value = {"parsed": '{"full_name":"Іван Іванов","phone":"0931112233","city":"Київ","office":"Відділення 5"}'}
        c = IgClient.get_or_create_for_sender("e1")
        InstagramBotMessage.objects.create(sender_id="e1", client=c, role="user", text="Іван Іванов 0931112233 Київ відд 5")
        data = bot_orders.extract_np_data(c)
        self.assertEqual(data["phone"], "0931112233")
        self.assertEqual(data["city"], "Київ")


class CollectAndFulfillTests(TestCase):
    @patch("management.services.bot_orders.notify_manager")
    @patch("management.services.bot_orders.extract_np_data")
    def test_collect_stores_and_creates_order(self, mock_extract, mock_notify):
        mock_extract.return_value = {"full_name": "Іван", "phone": "0931112233", "city": "Київ", "office": "в5"}
        c, d = _paid_deal("c1", with_np=False)
        self.assertFalse(bot_orders.collect_np_and_fulfill(c))
        d.refresh_from_db()
        self.assertEqual(d.np_phone, "0931112233")
        self.assertIsNone(d.order_id)


class OnDealPaidTests(TestCase):
    @patch("management.services.bot_orders.notify_manager")
    def test_on_paid_with_np_creates_order(self, mock_notify):
        c, d = _paid_deal("p1", with_np=True)
        bot_orders.on_deal_paid(d)
        d.refresh_from_db()
        self.assertIsNotNone(d.order_id)

    @patch("management.services.bot_orders.notify_manager")
    def test_on_paid_without_np_notifies_no_order(self, mock_notify):
        c, d = _paid_deal("p2", with_np=False)
        bot_orders.on_deal_paid(d)
        d.refresh_from_db()
        self.assertIsNone(d.order_id)
        self.assertTrue(mock_notify.called)


class CreateDealAndLinkTests(TestCase):
    @patch("management.services.bot_orders.create_payment_link")
    def test_persists_fit_quantity_and_price_provenance_for_real_paylink_writer(self, mock_link):
        mock_link.return_value = {"ok": True, "invoice_url": "https://pay/fit", "invoice_id": "fit"}
        from storefront.models import Category, Product, ProductFitOption, ProductStatus

        cat = Category.objects.create(name="Футболки", slug="tees-fit-writer")
        product = Product.objects.create(
            title="Футболка Харків", slug="kharkiv-fit-writer",
            category=cat, price=790, status=ProductStatus.PUBLISHED,
        )
        ProductFitOption.objects.create(
            product=product, code="oversize", label="Оверсайз", is_active=True,
        )
        client = IgClient.get_or_create_for_sender("fit-writer")

        result = bot_orders.create_deal_and_link(
            client,
            pay_type="full",
            product_id=product.pk,
            qty=2,
            size="XS",
            fit_option_code="oversize",
        )

        self.assertTrue(result["ok"])
        item = IgDeal.objects.get(client=client).items.get()
        self.assertEqual(item.qty, 2)
        self.assertEqual(item.size, "XS")
        self.assertEqual(item.fit_option_code, "oversize")
        self.assertEqual(item.fit_option_label, "Оверсайз")
        self.assertEqual(item.option_values, {"fit": "oversize"})
        self.assertEqual(item.price_source, "catalog")

    @patch("management.services.bot_orders.create_payment_link")
    def test_persists_classic_and_oversize_as_separate_paylink_items(self, mock_link):
        mock_link.return_value = {"ok": True, "invoice_url": "https://pay/multi", "invoice_id": "multi"}
        from storefront.models import Category, Product, ProductFitOption, ProductStatus

        category = Category.objects.create(name="Футболки", slug="tees-multi-fit-writer")
        product = Product.objects.create(
            title="Футболка Харків", slug="kharkiv-multi-fit-writer",
            category=category, price=Decimal("790.00"), status=ProductStatus.PUBLISHED,
        )
        ProductFitOption.objects.create(product=product, code="classic", label="Класичний", is_active=True)
        ProductFitOption.objects.create(product=product, code="oversize", label="Оверсайз", is_active=True)
        client = IgClient.get_or_create_for_sender("multi-fit-writer")

        result = bot_orders.create_deal_and_link(
            client,
            items=[
                {"product_id": product.pk, "qty": 1, "size": "S", "fit_option_code": "classic"},
                {"product_id": product.pk, "qty": 1, "size": "XS", "fit_option_code": "oversize"},
            ],
        )

        self.assertTrue(result["ok"])
        deal = IgDeal.objects.get(client=client)
        self.assertEqual(deal.items.count(), 2)
        self.assertEqual(
            list(deal.items.order_by("id").values_list("fit_option_code", "size", "qty")),
            [("classic", "S", 1), ("oversize", "XS", 1)],
        )
        self.assertEqual(deal.amount, Decimal("1580.00"))

    @patch("management.services.bot_orders.create_payment_link")
    def test_variant_stock_and_effective_price_are_authoritative(self, mock_link):
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import Category, Product, ProductStatus

        mock_link.return_value = {"ok": True, "invoice_url": "https://pay/variant", "invoice_id": "variant"}
        category = Category.objects.create(name="Футболки", slug="tees-variant-authority")
        product = Product.objects.create(
            title="Футболка", slug="variant-authority", category=category,
            price=Decimal("790.00"), status=ProductStatus.PUBLISHED,
        )
        color = Color.objects.create(name="Рожевий", primary_hex="#FF88AA")
        variant = ProductColorVariant.objects.create(
            product=product, color=color, stock=1, price_override=990,
        )
        client = IgClient.get_or_create_for_sender("variant-authority")

        result = bot_orders.create_deal_and_link(client, items=[{
            "product_id": product.pk,
            "color_variant_id": variant.pk,
            "qty": 1,
            "size": "S",
            "fit_option_code": "",
        }])

        self.assertTrue(result["ok"])
        self.assertEqual(IgDeal.objects.get(client=client).items.get().unit_price, Decimal("990.00"))

        second_client = IgClient.get_or_create_for_sender("variant-authority-oos")
        unavailable = bot_orders.create_deal_and_link(second_client, items=[{
            "product_id": product.pk,
            "color_variant_id": variant.pk,
            "qty": 2,
            "size": "S",
            "fit_option_code": "",
        }])
        self.assertEqual(unavailable, {"ok": False, "error": "insufficient_stock"})

    @patch("management.services.bot_orders.create_payment_link")
    def test_duplicate_item_identity_and_global_multi_price_fail_closed(self, mock_link):
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Футболки", slug="tees-duplicate-paylink")
        product = Product.objects.create(
            title="Футболка", slug="duplicate-paylink", category=category,
            price=Decimal("790.00"), status=ProductStatus.PUBLISHED,
        )
        client = IgClient.get_or_create_for_sender("duplicate-paylink")
        items = [
            {"product_id": product.pk, "qty": 1, "size": "S", "fit_option_code": "classic"},
            {"product_id": product.pk, "qty": 1, "size": "S", "fit_option_code": "classic"},
        ]

        duplicate = bot_orders.create_deal_and_link(client, items=items)
        self.assertEqual(duplicate, {"ok": False, "error": "duplicate_items"})
        allocated = bot_orders.create_deal_and_link(
            client,
            items=[
                {"product_id": product.pk, "qty": 1, "size": "S", "fit_option_code": "classic"},
                {"product_id": product.pk, "qty": 1, "size": "M", "fit_option_code": "classic"},
            ],
            negotiated_price=Decimal("1200.00"),
        )
        self.assertEqual(allocated, {"ok": False, "error": "price_allocation_required"})
        mock_link.assert_not_called()

    @patch("management.services.bot_orders.create_payment_link")
    def test_item_count_quantity_and_size_limits_fail_closed(self, mock_link):
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Футболки", slug="tees-paylink-limits")
        product = Product.objects.create(
            title="Футболка", slug="paylink-limits", category=category,
            price=Decimal("790.00"), status=ProductStatus.PUBLISHED,
        )
        client = IgClient.get_or_create_for_sender("paylink-limits")

        too_many = bot_orders.create_deal_and_link(client, items=[
            {"product_id": product.pk, "qty": 1, "size": size, "fit_option_code": ""}
            for size in ("S", "M", "L", "XL", "XXL", "XS", "2XL", "3XL", "4XL", "5XL", "6XL", "7XL", "8XL")
        ])
        self.assertEqual(too_many, {"ok": False, "error": "too_many_items"})
        too_large = bot_orders.create_deal_and_link(client, items=[
            {"product_id": product.pk, "qty": 30, "size": "S", "fit_option_code": ""},
            {"product_id": product.pk, "qty": 30, "size": "M", "fit_option_code": ""},
        ])
        self.assertEqual(too_large, {"ok": False, "error": "aggregate_qty_limit"})
        invalid_size = bot_orders.create_deal_and_link(client, items=[
            {"product_id": product.pk, "qty": 1, "size": "ZZ", "fit_option_code": ""},
        ])
        self.assertEqual(invalid_size, {"ok": False, "error": "invalid_size"})
        mock_link.assert_not_called()

    @patch("management.services.bot_orders.create_payment_link")
    def test_invalid_quantity_fails_closed_without_exception(self, mock_link):
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Футболки", slug="tees-invalid-qty")
        product = Product.objects.create(
            title="Футболка", slug="invalid-qty",
            category=category, price=Decimal("950.00"), status=ProductStatus.PUBLISHED,
        )
        client = IgClient.get_or_create_for_sender("invalid-qty")

        result = bot_orders.create_deal_and_link(client, product_id=product.pk, qty="many")

        self.assertEqual(result, {"ok": False, "error": "invalid_qty"})
        mock_link.assert_not_called()

    @patch("management.services.bot_orders.create_payment_link")
    def test_builds_deal_with_product_and_link(self, mock_link):
        mock_link.return_value = {"ok": True, "invoice_url": "https://pay/x", "invoice_id": "x"}
        from storefront.models import Category, Product, ProductStatus

        cat = Category.objects.create(name="Худі", slug="hudi-cdl")
        p = Product.objects.create(title="Худі Kharkiv", slug="hk-cdl", category=cat, price=950, status=ProductStatus.PUBLISHED)
        c = IgClient.get_or_create_for_sender("dl1")
        res = bot_orders.create_deal_and_link(c, pay_type="full", product_id=p.id, size="M")
        self.assertTrue(res["ok"])
        self.assertEqual(res["invoice_url"], "https://pay/x")
        deal = IgDeal.objects.filter(client=c).first()
        self.assertIsNotNone(deal)
        self.assertEqual(deal.items.count(), 1)
        self.assertEqual(deal.amount, Decimal("950"))

    @patch("management.services.bot_orders.create_payment_link")
    def test_uses_validated_conversation_price_instead_of_catalog_price(self, mock_link):
        mock_link.return_value = {"ok": True, "invoice_url": "https://pay/negotiated", "invoice_id": "negotiated"}
        from storefront.models import Category, Product, ProductStatus

        cat = Category.objects.create(name="Футболки", slug="tees-negotiated")
        p = Product.objects.create(title="Футболка Kharkiv", slug="kharkiv-negotiated", category=cat, price=950, status=ProductStatus.PUBLISHED)
        c = IgClient.get_or_create_for_sender("negotiated-price")
        InstagramBotMessage.objects.create(
            sender_id="negotiated-price", client=c, role="manager",
            text="Можу оформити цю футболку за 2100 грн",
        )
        InstagramBotMessage.objects.create(
            sender_id="negotiated-price", client=c, role="user",
            text="Так, оформлюйте",
        )
        res = bot_orders.create_deal_and_link(
            c, pay_type="full", product_id=p.id, size="M", negotiated_price=Decimal("2100")
        )
        self.assertTrue(res["ok"])
        deal = IgDeal.objects.filter(client=c).first()
        self.assertEqual(deal.items.first().unit_price, Decimal("2100.00"))
        self.assertEqual(deal.items.first().price_source, "conversation_evidence")
        self.assertTrue(deal.items.first().price_evidence_message_ids)
        evidence_ids = deal.items.first().price_evidence_message_ids
        self.assertIn(
            InstagramBotMessage.objects.get(role="manager", client=c).pk,
            evidence_ids,
        )
        self.assertIn(
            InstagramBotMessage.objects.get(role="user", client=c).pk,
            evidence_ids,
        )
        self.assertEqual(deal.amount, Decimal("2100.00"))

    @patch("management.services.bot_orders.create_payment_link")
    def test_rejects_stale_price_when_later_offer_has_different_total(self, mock_link):
        from storefront.models import Category, Product, ProductStatus

        cat = Category.objects.create(name="Футболки", slug="tees-stale-negotiated")
        product = Product.objects.create(
            title="Футболка Kharkiv", slug="kharkiv-stale-negotiated",
            category=cat, price=950, status=ProductStatus.PUBLISHED,
        )
        client = IgClient.get_or_create_for_sender("stale-negotiated-price")
        InstagramBotMessage.objects.create(
            sender_id=client.igsid, client=client, role="user",
            text="Стара розмова: беру за 700 грн",
        )
        InstagramBotMessage.objects.create(
            sender_id=client.igsid, client=client, role="manager",
            text="Актуальна сума разом 900 грн",
        )
        InstagramBotMessage.objects.create(
            sender_id=client.igsid, client=client, role="user",
            text="Так, оформлюйте",
        )
        result = bot_orders.create_deal_and_link(
            client, pay_type="full", product_id=product.pk,
            negotiated_price=Decimal("700"),
        )
        self.assertEqual(result, {"ok": False, "error": "invalid_negotiated_price"})
        mock_link.assert_not_called()

    @patch("management.services.bot_orders.create_payment_link")
    def test_prepayment_amount_never_becomes_merchandise_unit_price(self, mock_link):
        mock_link.return_value = {"ok": True, "invoice_url": "https://pay/catalog", "invoice_id": "catalog"}
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Футболки", slug="tees-prepayment-price")
        product = Product.objects.create(
            title="Футболка", slug="prepayment-is-not-price", category=category,
            price=950, status=ProductStatus.PUBLISHED,
        )
        client = IgClient.get_or_create_for_sender("prepayment-is-not-price")
        InstagramBotMessage.objects.create(
            sender_id=client.igsid, client=client, role="user",
            text="Оплатила передоплату 200 грн, ось чек",
        )

        result = bot_orders.create_deal_and_link(client, product_id=product.pk)

        self.assertTrue(result["ok"])
        self.assertEqual(IgDeal.objects.get(client=client).items.get().unit_price, Decimal("950.00"))

    @patch("management.services.bot_orders.create_payment_link")
    def test_accepted_manager_price_applies_without_model_price_tag(self, mock_link):
        mock_link.return_value = {"ok": True, "invoice_url": "https://pay/offer", "invoice_id": "offer"}
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Футболки", slug="tees-manager-offer")
        product = Product.objects.create(
            title="Футболка", slug="manager-offer", category=category,
            price=950, status=ProductStatus.PUBLISHED,
        )
        client = IgClient.get_or_create_for_sender("manager-offer")
        InstagramBotMessage.objects.create(
            sender_id=client.igsid, client=client, role="manager",
            text="Можу віддати за 790 грн",
        )
        InstagramBotMessage.objects.create(
            sender_id=client.igsid, client=client, role="user",
            text="Так, оформлюйте",
        )

        result = bot_orders.create_deal_and_link(client, product_id=product.pk)

        self.assertTrue(result["ok"])
        self.assertEqual(IgDeal.objects.get(client=client).items.get().unit_price, Decimal("790.00"))

    @patch("management.services.bot_orders.create_payment_link")
    def test_new_catalog_price_epoch_does_not_reuse_discounted_invoice(self, mock_link):
        mock_link.return_value = {"ok": True, "invoice_url": "https://pay/new", "invoice_id": "new"}
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Футболки", slug="tees-price-epoch")
        product = Product.objects.create(
            title="Футболка", slug="price-epoch", category=category,
            price=950, status=ProductStatus.PUBLISHED,
        )
        client = IgClient.get_or_create_for_sender("price-epoch")
        old_deal = IgDeal.objects.create(
            client=client,
            pay_type=IgDeal.PayType.ONLINE_FULL,
            invoice_id="old-discount",
            invoice_url="https://pay/old-discount",
        )
        IgDealItem.objects.create(
            deal=old_deal, product=product, title=product.title,
            qty=1, unit_price=Decimal("790.00"),
        )
        old_deal.recalc_total()
        InstagramBotMessage.objects.create(
            sender_id=client.igsid, client=client, role="manager",
            text="Попередня знижка вже не діє, актуальна ціна 950 грн",
        )
        InstagramBotMessage.objects.create(
            sender_id=client.igsid, client=client, role="user",
            text="Добре, оформлюйте",
        )

        result = bot_orders.create_deal_and_link(client, product_id=product.pk)

        self.assertTrue(result["ok"])
        self.assertEqual(IgDeal.objects.filter(client=client).count(), 2)
        self.assertEqual(IgDeal.objects.filter(client=client).order_by("-id").first().items.get().unit_price, Decimal("950.00"))
