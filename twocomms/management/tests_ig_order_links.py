from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from orders.models import Order


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "management.twocomms.shop"],
)
class InstagramOrderLinkTests(TestCase):
    def setUp(self):
        from management.ig_bot_models import IgClient, IgDeal, IgDealItem, IgPaymentConfirmationReview
        from management.services.ig_payment_review import record_review_decision

        self.actor = get_user_model().objects.create_user(
            username="ig-order-link-manager",
            password="test-password",
            is_staff=True,
            is_superuser=True,
        )
        self.client = IgClient.get_or_create_for_sender(
            "ig-order-link-client",
            defaults={"username": "buyer", "display_name": "Buyer"},
        )
        self.deal = IgDeal.objects.create(client=self.client, amount=Decimal("2100.00"))
        self.review = IgPaymentConfirmationReview.objects.create(
            client=self.client,
            deal=self.deal,
            dedupe_key="ig-order-link-review",
            watermark_message_id=91,
        )
        record_review_decision(
            self.review,
            actor=self.actor,
            decision="manager_verified",
        )
        self.order = self._order(total="2100.00")

    def _order(self, *, total="2100.00"):
        return Order.objects.create(
            full_name="Яна Ніколаєнко",
            phone="380502034719",
            city="Харків",
            np_office="Відділення №1",
            total_sum=Decimal(total),
            source="manual",
            sale_source="Instagram",
        )

    def _link(self, review=None, order=None, override_reason=""):
        from management.services.ig_order_links import link_existing_order_to_review

        return link_existing_order_to_review(
            review or self.review,
            order_identifier=(order or self.order).order_number,
            actor=self.actor,
            override_reason=override_reason,
        )

    def test_exact_order_number_link_is_idempotent_and_attributed(self):
        from management.ig_bot_models import IgOrderAttribution, IgOrderLinkEvent

        first = self._link()
        second = self._link()

        self.assertEqual(first.pk, self.order.pk)
        self.assertEqual(second.pk, self.order.pk)
        self.review.refresh_from_db()
        self.deal.refresh_from_db()
        self.assertEqual(self.review.order_id, self.order.pk)
        self.assertEqual(self.deal.order_id, self.order.pk)
        attribution = IgOrderAttribution.objects.get(order=self.order)
        self.assertEqual(attribution.client, self.client)
        self.assertEqual(attribution.creation_mode, "linked_existing")
        self.assertEqual(attribution.payment_source, "manager_verified")
        self.assertFalse(hasattr(attribution, "igsid_snapshot"))
        self.assertFalse(hasattr(attribution, "username_snapshot"))
        self.assertTrue(attribution.identity_digest)
        self.assertEqual(attribution.evidence_watermark_message_id, 91)
        self.assertEqual(IgOrderLinkEvent.objects.filter(order=self.order).count(), 1)

    def test_payment_review_action_can_link_exact_existing_order(self):
        web_client = Client()
        web_client.force_login(self.actor)

        response = web_client.post(
            reverse("management_bot_payment_review_action_api", args=[self.review.pk]),
            {"action": "link_order", "order_identifier": self.order.order_number},
            secure=True,
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["order_id"], self.order.pk)
        self.assertEqual(
            response.json()["order_url"],
            f"https://twocomms.shop/admin-panel/?section=orders&edit_order={self.order.pk}",
        )
        self.review.refresh_from_db()
        self.assertEqual(self.review.order_id, self.order.pk)

    def test_one_instagram_client_can_have_many_attributed_orders(self):
        from management.ig_bot_models import IgDeal, IgOrderAttribution, IgPaymentConfirmationReview
        from management.services.ig_payment_review import record_review_decision

        other_deal = IgDeal.objects.create(client=self.client, amount=Decimal("900.00"))
        other_review = IgPaymentConfirmationReview.objects.create(
            client=self.client,
            deal=other_deal,
            dedupe_key="ig-order-link-review-two",
            watermark_message_id=92,
        )
        record_review_decision(
            other_review,
            actor=self.actor,
            decision="manager_verified",
        )
        other_order = self._order(total="900.00")

        self._link()
        self._link(other_review, other_order)

        self.assertEqual(
            IgOrderAttribution.objects.filter(client=self.client).count(),
            2,
        )

    def test_cross_client_existing_order_link_is_rejected(self):
        from management.ig_bot_models import IgClient, IgDeal, IgDealItem, IgPaymentConfirmationReview
        from management.services.ig_payment_review import record_review_decision

        self._link()
        other_client = IgClient.get_or_create_for_sender("ig-order-link-other")
        other_deal = IgDeal.objects.create(client=other_client, amount=Decimal("2100.00"))
        other_review = IgPaymentConfirmationReview.objects.create(
            client=other_client,
            deal=other_deal,
            dedupe_key="ig-order-link-cross-client",
        )
        record_review_decision(
            other_review,
            actor=self.actor,
            decision="manager_verified",
        )

        with self.assertRaisesMessage(ValueError, "іншого Instagram-клієнта"):
            self._link(other_review, self.order)

        other_review.refresh_from_db()
        other_deal.refresh_from_db()
        self.assertIsNone(other_review.order_id)
        self.assertIsNone(other_deal.order_id)

    def test_multiple_review_episodes_can_reference_same_order_for_same_client(self):
        from management.ig_bot_models import IgOrderAttribution, IgOrderLinkEvent, IgPaymentConfirmationReview
        from management.services.ig_payment_review import record_review_decision

        followup_review = IgPaymentConfirmationReview.objects.create(
            client=self.client,
            dedupe_key="ig-order-link-followup-review",
            watermark_message_id=93,
        )
        record_review_decision(
            followup_review,
            actor=self.actor,
            decision="manager_verified",
        )

        self._link()
        self._link(followup_review, self.order)

        self.review.refresh_from_db()
        followup_review.refresh_from_db()
        self.assertEqual(self.review.order_id, self.order.pk)
        self.assertEqual(followup_review.order_id, self.order.pk)
        self.assertEqual(IgOrderAttribution.objects.filter(order=self.order).count(), 1)
        self.assertEqual(IgOrderLinkEvent.objects.filter(order=self.order).count(), 2)

    def test_another_deal_for_same_client_cannot_claim_already_attributed_order(self):
        from management.ig_bot_models import IgDeal, IgPaymentConfirmationReview
        from management.services.ig_payment_review import record_review_decision

        self._link()
        second_deal = IgDeal.objects.create(
            client=self.client,
            amount=Decimal("2100.00"),
            order=self.order,
        )
        second_review = IgPaymentConfirmationReview.objects.create(
            client=self.client,
            deal=second_deal,
            dedupe_key="ig-order-link-same-client-second-deal",
        )
        record_review_decision(second_review, actor=self.actor, decision="manager_verified")

        from management.services.ig_order_links import link_existing_order_to_review
        with self.assertRaisesMessage(ValueError, "іншою угодою"):
            link_existing_order_to_review(
                second_review,
                order_identifier=self.order.order_number,
                actor=self.actor,
            )

        second_review.refresh_from_db()
        self.assertIsNone(second_review.order_id)

    def test_override_link_replay_is_idempotent_without_repeating_reason(self):
        from management.ig_bot_models import IgOrderLinkEvent
        from management.services.ig_order_links import link_existing_order_to_review

        self.order.total_sum = Decimal("1900.00")
        self.order.save(update_fields=["total_sum"])
        first = link_existing_order_to_review(
            self.review,
            order_identifier=self.order.order_number,
            actor=self.actor,
            override_reason="Погоджена менеджером знижка",
        )
        second = link_existing_order_to_review(
            self.review,
            order_identifier=self.order.order_number,
            actor=self.actor,
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(IgOrderLinkEvent.objects.filter(order=self.order).count(), 1)

    def test_review_must_still_be_confirmed_when_linking(self):
        from management.ig_bot_models import IgPaymentConfirmationReview

        IgPaymentConfirmationReview.objects.filter(pk=self.review.pk).update(
            status=IgPaymentConfirmationReview.Status.PENDING,
        )

        with self.assertRaisesMessage(ValueError, "підтверджена"):
            self._link()

    def test_same_deal_existing_order_cannot_be_overwritten(self):
        original = self._order(total="2100.00")
        self.deal.order = original
        self.deal.save(update_fields=["order", "updated_at"])

        with self.assertRaisesMessage(ValueError, "іншого замовлення"):
            self._link()

        self.deal.refresh_from_db()
        self.review.refresh_from_db()
        self.assertEqual(self.deal.order_id, original.pk)
        self.assertIsNone(self.review.order_id)
        self.assertFalse(hasattr(self.order, "instagram_attribution"))

    def test_link_event_history_is_append_only_via_orm(self):
        from management.ig_bot_models import IgOrderLinkEvent

        self._link()
        event = IgOrderLinkEvent.objects.get(order=self.order)
        event.reason_code = "manual_review"

        with self.assertRaisesMessage(ValueError, "append-only"):
            event.save()
        with self.assertRaisesMessage(ValueError, "append-only"):
            event.delete()
        with self.assertRaisesMessage(ValueError, "append-only"):
            IgOrderLinkEvent.objects.filter(pk=event.pk).update(reason_code="manual_review")
        with self.assertRaisesMessage(ValueError, "append-only"):
            IgOrderLinkEvent.objects.filter(pk=event.pk).delete()

    def test_phone_mismatch_snapshot_contains_no_phone_digits(self):
        from management.ig_bot_models import IgOrderLinkEvent
        from management.services.ig_order_links import link_existing_order_to_review

        self.deal.np_phone = "380671112233"
        self.deal.save(update_fields=["np_phone", "updated_at"])
        link_existing_order_to_review(
            self.review,
            order_identifier=self.order.order_number,
            actor=self.actor,
            override_reason="Телефон перевірено вручну",
        )

        snapshot = IgOrderLinkEvent.objects.get(order=self.order).mismatch_snapshot
        self.assertEqual(snapshot["phone"], {"mismatch": True})

    def test_one_sided_item_snapshot_requires_override(self):
        from management.ig_bot_models import IgDealItem
        from management.services.ig_order_links import link_existing_order_to_review

        IgDealItem.objects.create(
            deal=self.deal,
            title="Футболка Харків",
            qty=1,
            unit_price=Decimal("2100.00"),
        )

        with self.assertRaisesMessage(ValueError, "не збігаються"):
            link_existing_order_to_review(
                self.review,
                order_identifier=self.order.order_number,
                actor=self.actor,
            )

        link_existing_order_to_review(
            self.review,
            order_identifier=self.order.order_number,
            actor=self.actor,
            override_reason="Позиції перевірено вручну",
        )

    def test_linked_existing_attribution_preserves_deal_price_evidence(self):
        from management.ig_bot_models import IgDealItem, IgOrderAttribution

        IgDealItem.objects.create(
            deal=self.deal,
            title="Футболка Харків",
            size="XS",
            fit_option_code="oversize",
            fit_option_label="Оверсайз",
            option_values={"fit": "oversize"},
            option_labels={"fit": "Оверсайз"},
            qty=1,
            unit_price=Decimal("2100.00"),
            price_source="conversation_evidence",
            price_evidence_message_ids=[811, 813],
        )

        self._link(override_reason="Позиції перевірено вручну")

        attribution = IgOrderAttribution.objects.get(order=self.order)
        self.assertEqual(attribution.item_provenance[0]["price_source"], "conversation_evidence")
        self.assertEqual(attribution.item_provenance[0]["price_evidence_message_ids"], [811, 813])
        self.assertEqual(attribution.price_evidence_message_ids, [811, 813])

    def test_order_attribution_is_append_only_via_orm(self):
        from management.ig_bot_models import IgOrderAttribution

        self._link()
        attribution = IgOrderAttribution.objects.get(order=self.order)
        attribution.payment_source = "unknown"

        with self.assertRaisesMessage(ValueError, "append-only"):
            attribution.save()
        with self.assertRaisesMessage(ValueError, "append-only"):
            attribution.delete()
        with self.assertRaisesMessage(ValueError, "append-only"):
            IgOrderAttribution.objects.filter(pk=attribution.pk).update(payment_source="unknown")
        with self.assertRaisesMessage(ValueError, "append-only"):
            IgOrderAttribution.objects.filter(pk=attribution.pk).delete()

    def test_dashboard_exposes_override_reason_for_existing_order_link(self):
        web_client = Client()
        web_client.force_login(self.actor)

        response = web_client.get(reverse("management_bot"), secure=True)

        self.assertContains(response, "Причина розбіжності")
        self.assertContains(response, "override_reason")

    def test_order_primary_key_or_partial_number_is_not_an_exact_identifier(self):
        from management.services.ig_order_links import link_existing_order_to_review

        for invalid in (str(self.order.pk), self.order.order_number[:-1], "missing-order"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesMessage(ValueError, "точним номером"):
                    link_existing_order_to_review(
                        self.review,
                        order_identifier=invalid,
                        actor=self.actor,
                    )

    def test_legacy_cross_client_deal_link_is_rejected(self):
        from management.ig_bot_models import IgClient, IgDeal, IgOrderAttribution, IgOrderLinkEvent

        other_client = IgClient.get_or_create_for_sender("legacy-cross-client-deal")
        IgDeal.objects.create(
            client=other_client,
            order=self.order,
            amount=Decimal("2100.00"),
        )

        with self.assertRaisesMessage(ValueError, "іншого Instagram-клієнта"):
            self._link()

        self.review.refresh_from_db()
        self.assertIsNone(self.review.order_id)
        self.assertFalse(IgOrderAttribution.objects.filter(order=self.order).exists())
        self.assertFalse(IgOrderLinkEvent.objects.filter(order=self.order).exists())

    def test_existing_order_fields_and_items_are_not_mutated_by_link(self):
        from orders.models import OrderItem

        OrderItem.objects.create(
            order=self.order,
            title="Існуюча позиція",
            size="M",
            qty=2,
            unit_price=Decimal("1050.00"),
            line_total=Decimal("2100.00"),
        )
        before_order = {
            field: getattr(self.order, field)
            for field in (
                "full_name", "phone", "city", "np_office", "total_sum",
                "payment_status", "payment_provider", "payment_payload",
                "source", "sale_source",
            )
        }
        before_items = list(
            self.order.items.order_by("id").values(
                "product_id", "color_variant_id", "title", "size", "qty",
                "unit_price", "line_total", "fit_option_code", "option_values",
            )
        )

        from management.services.ig_order_links import link_existing_order_to_review
        link_existing_order_to_review(
            self.review,
            order_identifier=self.order.order_number,
            actor=self.actor,
            override_reason="Позиції перевірено вручну",
        )

        self.order.refresh_from_db()
        self.assertEqual(
            {field: getattr(self.order, field) for field in before_order},
            before_order,
        )
        self.assertEqual(
            list(self.order.items.order_by("id").values(*before_items[0].keys())),
            before_items,
        )


class InstagramAutomaticOrderProvenanceTests(TestCase):
    def test_manager_verified_builder_order_remains_provider_unpaid(self):
        from management.ig_bot_models import IgClient, IgDeal, IgDealItem, IgPaymentConfirmationReview
        from management.services.ig_payment_review import record_review_decision
        from orders.services.order_builder import create_order_from_deal

        actor = get_user_model().objects.create_user(
            username="ig-manager-builder", password="test-password", is_staff=True
        )
        client = IgClient.get_or_create_for_sender("ig-manager-builder-client")
        deal = IgDeal.objects.create(
            client=client,
            amount=Decimal("790.00"),
            pay_type=IgDeal.PayType.ONLINE_FULL,
            np_full_name="Яна Ніколаєнко",
            np_phone="380502034719",
            np_city="Харків",
            np_office="Відділення №1",
        )
        IgDealItem.objects.create(deal=deal, title="Футболка", qty=1, unit_price=Decimal("790.00"))
        deal.recalc_total()
        review = IgPaymentConfirmationReview.objects.create(
            client=client, deal=deal, dedupe_key="ig-manager-builder-review"
        )
        record_review_decision(review, actor=actor, decision="manager_verified")

        order = create_order_from_deal(deal, created_by=actor)

        self.assertEqual(order.payment_status, "unpaid")
        self.assertFalse(order.payment_payload.get("provider_payment_confirmed", False))
        self.assertEqual(order.instagram_attribution.creation_mode, "manager_review")
        self.assertEqual(order.instagram_attribution.payment_source, "manager_verified")
        self.assertEqual(order.payment_provider, "")

    def test_manager_review_attribution_preserves_deal_price_evidence(self):
        from management.ig_bot_models import IgClient, IgDeal, IgDealItem, IgPaymentConfirmationReview
        from management.services.ig_payment_review import record_review_decision
        from orders.services.order_builder import create_order_from_deal

        actor = get_user_model().objects.create_user(
            username="ig-manager-price-evidence", password="test-password", is_staff=True
        )
        client = IgClient.get_or_create_for_sender("ig-manager-price-evidence-client")
        deal = IgDeal.objects.create(
            client=client,
            amount=Decimal("790.00"),
            np_full_name="Яна Ніколаєнко",
            np_phone="380502034719",
            np_city="Харків",
            np_office="Відділення №1",
        )
        IgDealItem.objects.create(
            deal=deal,
            title="Футболка Харків",
            qty=1,
            unit_price=Decimal("790.00"),
            price_source="conversation_evidence",
            price_evidence_message_ids=[821, 823],
        )
        review = IgPaymentConfirmationReview.objects.create(
            client=client, deal=deal, dedupe_key="ig-manager-price-evidence-review"
        )
        record_review_decision(review, actor=actor, decision="manager_verified")

        order = create_order_from_deal(deal, created_by=actor)

        attribution = order.instagram_attribution
        self.assertEqual(attribution.item_provenance[0]["price_source"], "conversation_evidence")
        self.assertEqual(attribution.item_provenance[0]["price_evidence_message_ids"], [821, 823])
        self.assertEqual(attribution.price_evidence_message_ids, [821, 823])

    def test_legacy_provider_transition_is_classified_as_automatic_provider_attempt(self):
        from django.utils import timezone
        from management.ig_bot_models import IgClient, IgDeal, IgDealItem
        from orders.services.order_builder import create_order_from_deal

        client = IgClient.get_or_create_for_sender("ig-legacy-provider-auto")
        deal = IgDeal.objects.create(
            client=client,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=timezone.now(),
            payment_truth=IgDeal.PaymentTruth.UNVERIFIED,
            amount=Decimal("790.00"),
            np_full_name="Яна Ніколаєнко",
            np_phone="380502034719",
            np_city="Харків",
            np_office="Відділення №1",
        )
        IgDealItem.objects.create(
            deal=deal, title="Legacy футболка", qty=1, unit_price=Decimal("790.00")
        )

        order = create_order_from_deal(deal)

        self.assertFalse(order.payment_payload["provider_payment_confirmed"])
        self.assertTrue(order.payment_payload["legacy_payment_transition"])
        self.assertEqual(order.instagram_attribution.creation_mode, "provider_auto")
        self.assertEqual(order.instagram_attribution.payment_source, "provider_attempt")

    @patch("orders.services.order_builder._ensure_purchase_action")
    def test_existing_deal_order_without_payment_authority_is_rejected(self, ensure_purchase):
        from management.ig_bot_models import IgClient, IgDeal, IgOrderAttribution
        from orders.services.order_builder import create_order_from_deal

        client = IgClient.get_or_create_for_sender("ig-existing-order-no-authority")
        existing_order = Order.objects.create(
            full_name="Legacy", phone="380501234567", total_sum=Decimal("790.00")
        )
        deal = IgDeal.objects.create(
            client=client,
            order=existing_order,
            amount=Decimal("790.00"),
        )

        with self.assertRaisesMessage(ValueError, "source-qualified"):
            create_order_from_deal(deal)

        ensure_purchase.assert_not_called()
        self.assertFalse(IgOrderAttribution.objects.filter(order=existing_order).exists())

    def test_legacy_confirmed_review_without_decision_cannot_create_order(self):
        from management.ig_bot_models import IgClient, IgDeal, IgPaymentConfirmationReview
        from orders.services.order_builder import create_order_from_deal

        client = IgClient.get_or_create_for_sender("ig-legacy-review-client")
        deal = IgDeal.objects.create(
            client=client,
            amount=Decimal("790.00"),
            np_full_name="Яна Ніколаєнко",
            np_phone="380502034719",
            np_city="Харків",
            np_office="Відділення №1",
        )
        IgPaymentConfirmationReview.objects.create(
            client=client,
            deal=deal,
            dedupe_key="legacy-confirmed-without-decision",
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
        )

        with self.assertRaisesMessage(ValueError, "source-qualified"):
            create_order_from_deal(deal)

        self.assertIsNone(deal.__class__.objects.get(pk=deal.pk).order_id)

    def test_provider_order_preserves_fit_and_negotiated_price_provenance(self):
        from management.ig_bot_models import (
            IgClient,
            IgDeal,
            IgDealItem,
            IgOrderAttribution,
            IgPaymentProjection,
        )
        from orders.services.order_builder import create_order_from_deal

        client = IgClient.get_or_create_for_sender(
            "ig-provider-order-client",
            defaults={"username": "provider_buyer"},
        )
        deal = IgDeal.objects.create(
            client=client,
            amount=Decimal("790.00"),
            pay_type=IgDeal.PayType.ONLINE_FULL,
            np_full_name="Яна Ніколаєнко",
            np_phone="380502034719",
            np_city="Харків",
            np_office="Відділення №1",
        )
        IgDealItem.objects.create(
            deal=deal,
            title="Футболка Харків",
            size="XS",
            fit_option_code="oversize",
            fit_option_label="Оверсайз",
            option_values={"fit": "oversize"},
            option_labels={"fit": "Оверсайз"},
            qty=1,
            unit_price=Decimal("790.00"),
            price_source="conversation_evidence",
            price_evidence_message_ids=[501, 503],
        )
        IgPaymentProjection.objects.create(
            client=client,
            deal=deal,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("790.00"),
        )

        order = create_order_from_deal(deal)

        item = order.items.get()
        self.assertEqual(item.fit_option_code, "oversize")
        self.assertEqual(item.fit_option_label, "Оверсайз")
        self.assertEqual(item.option_values, {"fit": "oversize"})
        self.assertEqual(item.unit_price, Decimal("790.00"))
        attribution = IgOrderAttribution.objects.get(order=order)
        self.assertEqual(attribution.creation_mode, "provider_auto")
        self.assertEqual(attribution.payment_source, "provider_projection")
        self.assertEqual(
            attribution.item_provenance[0]["price_source"],
            "conversation_evidence",
        )
        self.assertEqual(
            attribution.item_provenance[0]["price_evidence_message_ids"],
            [501, 503],
        )

    def test_provider_order_keeps_classic_and_oversize_as_distinct_lines(self):
        from management.ig_bot_models import (
            IgClient,
            IgDeal,
            IgDealItem,
            IgPaymentProjection,
        )
        from orders.services.order_builder import create_order_from_deal

        client = IgClient.get_or_create_for_sender("ig-provider-two-fits")
        deal = IgDeal.objects.create(
            client=client,
            amount=Decimal("1580.00"),
            pay_type=IgDeal.PayType.ONLINE_FULL,
            np_full_name="Яна Ніколаєнко",
            np_phone="380502034719",
            np_city="Харків",
            np_office="Відділення №1",
        )
        IgDealItem.objects.create(
            deal=deal, title="Футболка Харків", size="S",
            fit_option_code="classic", fit_option_label="Класична",
            option_values={"fit": "classic"}, option_labels={"fit": "Класична"},
            qty=1, unit_price=Decimal("790.00"), price_source="catalog",
        )
        IgDealItem.objects.create(
            deal=deal, title="Футболка Харків", size="XS",
            fit_option_code="oversize", fit_option_label="Оверсайз",
            option_values={"fit": "oversize"}, option_labels={"fit": "Оверсайз"},
            qty=1, unit_price=Decimal("790.00"), price_source="conversation_evidence",
            price_evidence_message_ids=[701, 703],
        )
        IgPaymentProjection.objects.create(
            client=client,
            deal=deal,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("1580.00"),
        )

        order = create_order_from_deal(deal)

        self.assertEqual(
            list(order.items.order_by("id").values_list("fit_option_code", "size", "qty")),
            [("classic", "S", 1), ("oversize", "XS", 1)],
        )
        self.assertEqual(
            [item["fit_option_code"] for item in order.instagram_attribution.item_provenance],
            ["classic", "oversize"],
        )
