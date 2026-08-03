from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
import uuid
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from management.models import IgClient, InstagramBotMessage, InstagramBotSettings
from management.services import instagram_bot


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "management.twocomms.shop", "localhost"],
    SECURE_SSL_REDIRECT=False,
)
class IgFunnelAnalyticsApiTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            "funnel-analytics-staff",
            password="test",
            is_staff=True,
        )
        self.client.force_login(self.staff)

    def test_stats_exposes_event_cohort_instead_of_only_stage_snapshot(self):
        from management.models import IgFunnelStepEvent
        from management.services.ig_funnel_analytics import record_client_step_event

        lead = IgClient.get_or_create_for_sender("ig-funnel-cohort")
        lead.touch_inbound()
        lead.set_stage(IgClient.Stage.QUALIFYING, reason="bot:first_reply")
        lead.refresh_from_db()
        record_client_step_event(
            lead,
            event_type=IgFunnelStepEvent.Type.BOT_REPLIED_FIRST,
            event_key=f"test:first-reply:{lead.pk}",
            actor="bot",
            stage=lead.stage,
        )

        payload = self.client.get(reverse("management_bot_stats_api") + "?days=7").json()

        self.assertTrue(payload["success"])
        self.assertIn("funnel", payload)
        self.assertEqual(payload["funnel"][0]["step"], "conversation_started")
        self.assertEqual(payload["funnel"][0]["entered"], 1)
        self.assertEqual(payload["funnel"][0]["advanced"], 1)

    def test_stats_uses_occurred_at_and_adjacent_ranges_are_additive(self):
        from management.models import IgFunnelStepEvent
        from management.services.ig_funnel_analytics import (
            build_funnel_analytics,
            record_client_step_event,
        )

        kyiv = ZoneInfo("Europe/Kyiv")
        first_at = timezone.make_aware(datetime(2026, 7, 30, 12, 0), kyiv)
        second_at = timezone.make_aware(datetime(2026, 7, 31, 12, 0), kyiv)
        for sender, occurred_at in (("ig-range-a", first_at), ("ig-range-b", second_at)):
            client = IgClient.get_or_create_for_sender(sender)
            client.touch_inbound()
            record_client_step_event(
                client,
                event_type=IgFunnelStepEvent.Type.BOT_REPLIED_FIRST,
                event_key=f"range:first-reply:{sender}",
                occurred_at=occurred_at,
            )

        first = build_funnel_analytics(first_at, first_at + timedelta(days=1))
        second = build_funnel_analytics(second_at, second_at + timedelta(days=1))
        combined = build_funnel_analytics(first_at, second_at + timedelta(days=1))
        self.assertEqual(first["steps"][1]["entered"], 1)
        self.assertEqual(second["steps"][1]["entered"], 1)
        self.assertEqual(combined["steps"][1]["entered"], 2)

    def test_drop_off_classification_distinguishes_unreachable_from_customer_silence(self):
        from management.services.ig_funnel_analytics import classify_drop_off

        kyiv = ZoneInfo("Europe/Kyiv")
        last_inbound = timezone.make_aware(datetime(2026, 7, 27, 10, 0), kyiv)
        now = timezone.make_aware(datetime(2026, 7, 28, 10, 30), kyiv)
        self.assertEqual(
            classify_drop_off(
                delivery_status="send_blocked",
                stage="checkout",
                last_inbound_at=last_inbound,
                now=now,
            )["kind"],
            "unreachable",
        )
        self.assertEqual(
            classify_drop_off(
                delivery_status="",
                stage="checkout",
                last_inbound_at=last_inbound,
                now=now,
            )["kind"],
            "silence",
        )

    def test_checkout_drop_off_is_counted_against_paylink_step(self):
        from management.models import IgFunnelDropOff, IgFunnelStepEvent
        from management.services.ig_funnel_analytics import (
            build_funnel_analytics,
            record_client_step_event,
        )

        client = IgClient.get_or_create_for_sender("ig-checkout-drop-off")
        record_client_step_event(
            client,
            event_type=IgFunnelStepEvent.Type.PAYLINK_ISSUED,
            event_key="drop-map:paylink-issued",
            stage=IgClient.Stage.CHECKOUT,
        )
        record_client_step_event(
            client,
            event_type=IgFunnelStepEvent.Type.DROP_OFF,
            event_key="drop-map:drop-off",
            stage=IgClient.Stage.CHECKOUT,
            evidence={
                "kind": IgFunnelDropOff.Kind.SILENCE,
                "stage_at_drop": IgClient.Stage.CHECKOUT,
            },
        )

        rows = {
            row["step"]: row
            for row in build_funnel_analytics()["steps"]
        }
        self.assertEqual(rows[IgFunnelStepEvent.Type.PAYLINK_ISSUED]["drop_off"], 1)

    def test_conversation_started_preserves_durable_source_event_key(self):
        from management.models import IgFunnelStepEvent
        from management.services.ig_funnel_analytics import record_client_step_event

        client = IgClient.get_or_create_for_sender("ig-conversation-key")
        event = record_client_step_event(
            client,
            event_type=IgFunnelStepEvent.Type.CONVERSATION_STARTED,
            event_key="inbound-message:1789000001",
        )

        self.assertEqual(event.event_key, "inbound-message:1789000001")

    def test_durable_inbound_records_one_conversation_fact_from_message(self):
        from management.models import IgFunnelStepEvent

        settings = InstagramBotSettings.load()
        settings.is_enabled = True
        settings.allowed_senders = ""
        settings.save()
        occurred_at = timezone.make_aware(
            datetime(2026, 8, 3, 12, 15),
            ZoneInfo("Europe/Kyiv"),
        )

        self.assertTrue(instagram_bot.enqueue_inbound(
            settings,
            sender_id="ig-funnel-inbound",
            text="Вітаю",
            mid="funnel-inbound-mid",
            received_at=occurred_at,
        ))
        self.assertFalse(instagram_bot.enqueue_inbound(
            settings,
            sender_id="ig-funnel-inbound",
            text="Вітаю",
            mid="funnel-inbound-mid",
            received_at=occurred_at,
        ))

        message = InstagramBotMessage.objects.get(mid="funnel-inbound-mid")
        event = IgFunnelStepEvent.objects.get(
            episode__client=message.client,
            event_type=IgFunnelStepEvent.Type.CONVERSATION_STARTED,
        )
        self.assertEqual(event.event_key, f"ig-inbound:{message.pk}")
        self.assertEqual(event.occurred_at, occurred_at)
        self.assertEqual(event.evidence["message_id"], message.pk)

    def test_durable_inbound_recovers_open_silence_drop_off(self):
        from management.models import IgFunnelDropOff, IgFunnelStepEvent
        from management.services.ig_funnel_analytics import record_client_step_event

        settings = InstagramBotSettings.load()
        settings.is_enabled = True
        settings.allowed_senders = ""
        settings.save()
        client = IgClient.get_or_create_for_sender("ig-inbound-recovery")
        drop_event = record_client_step_event(
            client,
            event_type=IgFunnelStepEvent.Type.DROP_OFF,
            event_key="inbound-recovery:drop",
            stage=IgClient.Stage.QUALIFYING,
            evidence={"kind": IgFunnelDropOff.Kind.SILENCE},
        )
        recovered_at = timezone.make_aware(
            datetime(2026, 8, 3, 13, 0),
            ZoneInfo("Europe/Kyiv"),
        )

        self.assertTrue(instagram_bot.enqueue_inbound(
            settings,
            sender_id=client.igsid,
            text="Я повернулась",
            mid="inbound-recovery-mid",
            received_at=recovered_at,
        ))

        drop_off = IgFunnelDropOff.objects.get(step_event=drop_event)
        self.assertEqual(drop_off.recovered_at, recovered_at)
        self.assertEqual(drop_off.recovery_event.evidence["message_id"],
                         InstagramBotMessage.objects.get(mid="inbound-recovery-mid").pk)

    def test_first_bot_reply_is_once_per_open_episode_and_keeps_reply_evidence(self):
        from django.db import transaction

        from management.models import IgFunnelStepEvent
        from management.services.ig_funnel_analytics import (
            record_first_bot_reply_in_transaction,
        )

        client = IgClient.get_or_create_for_sender("ig-first-reply")
        with transaction.atomic():
            locked = IgClient.objects.select_for_update().get(pk=client.pk)
            first = record_first_bot_reply_in_transaction(
                locked,
                occurred_at=timezone.now(),
                reply_message_id=701,
                source_message_id=601,
            )
            second = record_first_bot_reply_in_transaction(
                locked,
                occurred_at=timezone.now(),
                reply_message_id=702,
                source_message_id=602,
            )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.event_type, IgFunnelStepEvent.Type.BOT_REPLIED_FIRST)
        self.assertEqual(first.evidence["reply_message_id"], 701)
        self.assertEqual(
            IgFunnelStepEvent.objects.filter(
                episode__client=client,
                event_type=IgFunnelStepEvent.Type.BOT_REPLIED_FIRST,
            ).count(),
            1,
        )

    def test_finalize_paylink_keeps_structured_proposal_identity_for_delivery_fact(self):
        from management.services import instagram_bot
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Paylink", slug="funnel-paylink")
        product = Product.objects.create(
            title="Paylink product",
            slug="funnel-paylink-product",
            category=category,
            price=1090,
            status=ProductStatus.PUBLISHED,
        )
        client = IgClient.get_or_create_for_sender("ig-paylink-metadata")
        proposal_id = str(uuid.uuid4())
        control = {
            "paylink": "full",
            "product": str(product.pk),
            "qty": "1",
            "size": "M",
        }
        with patch(
            "management.services.bot_orders.create_checkout_proposal_link",
            return_value={
                "ok": True,
                "invoice_url": "https://twocomms.shop/ig/o/token/",
                "proposal_id": proposal_id,
                "order_summary": {},
            },
        ):
            instagram_bot.finalize_paylink(
                "Оформлю пропозицію",
                control,
                client,
                client.igsid,
                trigger_text="Хочу оплатити",
            )

        self.assertEqual(control["_funnel_proposal_id"], proposal_id)

    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    @patch("management.services.instagram_bot.send_sender_action")
    def test_confirmed_proposal_delivery_records_paylink_issued(
        self,
        _sender_action,
        _send_text,
    ):
        from management.models import IgCheckoutProposal, IgFunnelStepEvent
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Delivery", slug="funnel-delivery")
        product = Product.objects.create(
            title="Delivery product",
            slug="funnel-delivery-product",
            category=category,
            price=1090,
            status=ProductStatus.PUBLISHED,
        )
        settings = InstagramBotSettings.load()
        settings.is_enabled = True
        settings.ai_enabled = True
        settings.allowed_senders = ""
        settings.save()
        client = IgClient.get_or_create_for_sender("ig-paylink-delivered")
        client.profile_fetched_at = timezone.now()
        client.save(update_fields=["profile_fetched_at", "updated_at"])
        row = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Хочу оплатити",
            status=InstagramBotMessage.Status.PROCESSING,
        )
        reply = (
            f"Оформлю вашу пропозицію [PAYLINK:full] [PRODUCT:{product.pk}] [QTY:1] [SIZE:M]"
        )
        from management.services import bot_orders

        def confirmed_proposal_link(client, **kwargs):
            proposal = bot_orders.create_checkout_proposal(client, **kwargs)
            return {
                "ok": True,
                "invoice_url": "https://twocomms.shop/ig/o/confirmed/",
                "proposal_id": str(proposal.public_id),
                "proposal_pk": proposal.pk,
                "order_summary": {},
            }

        with patch("management.services.instagram_bot.gemini_generate", return_value=reply), patch(
            "management.services.bot_sales_classifier.ensure_rule_classification",
            return_value=None,
        ), patch(
            "management.services.instagram_bot.finalize_paylink",
            wraps=instagram_bot.finalize_paylink,
        ), patch(
            "management.services.bot_orders.create_checkout_proposal_link",
            side_effect=confirmed_proposal_link,
        ) as create_link:
            self.assertTrue(instagram_bot._process_one(settings, row))

        self.assertEqual(create_link.call_count, 1)
        proposal = IgCheckoutProposal.objects.get(client=client)
        event = IgFunnelStepEvent.objects.get(
            episode__client=client,
            event_type=IgFunnelStepEvent.Type.PAYLINK_ISSUED,
        )
        self.assertEqual(event.evidence["proposal_id"], proposal.pk)
        self.assertTrue(event.evidence["proposal_id"])
        self.assertTrue(event.evidence["reply_message_id"])

    def test_token_entry_records_paylink_viewed_in_same_transition(self):
        from management.models import (
            IgCheckoutAccessToken,
            IgCheckoutProposal,
            IgDeal,
            IgFunnelStepEvent,
        )
        from management.services.ig_commercial_episodes import ensure_episode_for_deal

        client = IgClient.get_or_create_for_sender("ig-paylink-viewed")
        deal = IgDeal.objects.create(client=client, amount=Decimal("1090.00"))
        episode = ensure_episode_for_deal(deal)
        proposal = IgCheckoutProposal.objects.create(
            client=client,
            deal=deal,
            commercial_episode=episode,
            catalog_total=Decimal("1090.00"),
            quoted_total=Decimal("1090.00"),
            requested_payment_amount=Decimal("1090.00"),
            items_digest="viewed-test",
            expires_at=timezone.now() + timedelta(minutes=25),
        )
        raw_token, _access_token = IgCheckoutAccessToken.issue(
            proposal=proposal,
            kind=IgCheckoutAccessToken.Kind.BOT,
        )

        with self.settings(ROOT_URLCONF="twocomms.urls"):
            response = self.client.get(
                reverse("ig_checkout_token_entry", kwargs={"token": raw_token})
            )

        self.assertEqual(response.status_code, 302)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, IgCheckoutProposal.Status.VIEWED)
        event = IgFunnelStepEvent.objects.get(
            episode=episode,
            event_type=IgFunnelStepEvent.Type.PAYLINK_VIEWED,
        )
        self.assertEqual(event.evidence["proposal_id"], proposal.pk)

    def test_verified_provider_payment_records_one_payment_confirmed_fact(self):
        from management.models import IgDeal, IgFunnelStepEvent
        from management.services import bot_payments
        from management.services.ig_commercial_episodes import ensure_episode_for_deal

        client = IgClient.get_or_create_for_sender("ig-payment-confirmed")
        deal = IgDeal.objects.create(
            client=client,
            amount=Decimal("950.00"),
            invoice_id="funnel-payment-invoice",
        )
        episode = ensure_episode_for_deal(deal)
        payload = {
            "status": "success",
            "invoiceId": "funnel-payment-invoice",
            "amount": 95000,
            "finalAmount": 95000,
            "modifiedDate": "2026-08-03T10:00:00Z",
        }
        with patch("management.services.bot_payments._on_deal_paid"):
            bot_payments.apply_payment_status(deal, "success", payload=payload)
            bot_payments.apply_payment_status(deal, "success", payload=payload)

        events = IgFunnelStepEvent.objects.filter(
            episode=episode,
            event_type=IgFunnelStepEvent.Type.PAYMENT_CONFIRMED,
        )
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().evidence["invoice_id"], "funnel-payment-invoice")

    def test_order_truth_records_order_ttn_and_delivery_once(self):
        from management.models import IgDeal, IgFunnelStepEvent
        from management.services.ig_commercial_episodes import (
            bind_episode_order,
            ensure_episode_for_deal,
            sync_episode_fulfillment,
        )
        from orders.models import Order

        client = IgClient.get_or_create_for_sender("ig-order-funnel")
        deal = IgDeal.objects.create(client=client, amount=Decimal("950.00"))
        episode = ensure_episode_for_deal(deal)
        order = Order.objects.create(
            full_name="Funnel Test",
            phone="380501112233",
            city="Київ",
            np_office="Відділення №1",
            total_sum=Decimal("950.00"),
            status="new",
            source="manual",
            sale_source="Instagram",
        )

        bind_episode_order(episode, order, creation_mode="funnel_test")
        self.assertEqual(
            IgFunnelStepEvent.objects.filter(
                episode=episode,
                event_type=IgFunnelStepEvent.Type.ORDER_CREATED,
            ).count(),
            1,
        )

        order.tracking_number = "20450000000011"
        order.shipment_status_updated = timezone.now()
        order.save(update_fields=["tracking_number", "shipment_status_updated"])
        sync_episode_fulfillment(order)
        self.assertEqual(
            IgFunnelStepEvent.objects.filter(
                episode=episode,
                event_type=IgFunnelStepEvent.Type.TTN_CREATED,
            ).count(),
            1,
        )

        order.status = "done"
        order.shipment_status = "Отримано"
        order.shipment_status_updated = timezone.now()
        order.save(update_fields=["status", "shipment_status", "shipment_status_updated"])
        sync_episode_fulfillment(order)
        sync_episode_fulfillment(order)
        self.assertEqual(
            IgFunnelStepEvent.objects.filter(
                episode=episode,
                event_type=IgFunnelStepEvent.Type.DELIVERED,
            ).count(),
            1,
        )

    def test_backfill_reads_production_order_timestamp_fields(self):
        from management.services.ig_commercial_episodes import (
            bind_episode_order,
            ensure_episode_for_deal,
        )
        from management.services.ig_funnel_analytics import backfill_reconstructible_funnel_events
        from management.models import IgDeal
        from orders.models import Order

        client = IgClient.get_or_create_for_sender("ig-backfill-order-fields")
        deal = IgDeal.objects.create(client=client, amount=Decimal("950.00"))
        episode = ensure_episode_for_deal(deal)
        order = Order.objects.create(
            full_name="Backfill Test",
            phone="380501112233",
            city="Київ",
            np_office="Відділення №1",
            total_sum=Decimal("950.00"),
            status="done",
            tracking_number="20450000000011",
            source="manual",
            sale_source="Instagram",
        )
        bind_episode_order(episode, order, creation_mode="backfill_test")

        result = backfill_reconstructible_funnel_events(limit=100)

        self.assertEqual(result["candidates"], 3)
        self.assertFalse(result["applied"])

    def test_complete_variant_selection_records_configuration_evidence(self):
        from management.models import IgFunnelStepEvent
        from management.services.instagram_bot import persist_control_selection
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Variant", slug="funnel-variant")
        product = Product.objects.create(
            title="Variant product",
            slug="funnel-variant-product",
            category=category,
            price=1090,
            status=ProductStatus.PUBLISHED,
        )
        client = IgClient.get_or_create_for_sender("ig-variant-selected")

        changed = persist_control_selection(
            client,
            {
                "product": str(product.pk),
                "fit": "oversize",
                "size": "M",
                "qty": "1",
            },
            source_message_id=801,
        )

        self.assertIn("fit", changed)
        event = IgFunnelStepEvent.objects.get(
            episode__client=client,
            event_type=IgFunnelStepEvent.Type.VARIANT_SELECTED,
        )
        self.assertEqual(event.evidence["product_id"], product.pk)
        self.assertEqual(event.evidence["fit_option_code"], "oversize")
        self.assertEqual(event.evidence["size"], "M")

    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    @patch("management.services.instagram_bot.send_sender_action")
    def test_confirmed_exact_catalog_quote_records_price_fact(
        self,
        _sender_action,
        _send_text,
    ):
        from management.models import IgFunnelStepEvent
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Price", slug="funnel-price")
        product = Product.objects.create(
            title="Price product",
            slug="funnel-price-product",
            category=category,
            price=1090,
            status=ProductStatus.PUBLISHED,
        )
        settings = InstagramBotSettings.load()
        settings.is_enabled = True
        settings.ai_enabled = True
        settings.allowed_senders = ""
        settings.save()
        client = IgClient.get_or_create_for_sender("ig-price-quoted")
        client.profile_fetched_at = timezone.now()
        client.save(update_fields=["profile_fetched_at", "updated_at"])
        row = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Скільки коштує?",
            status=InstagramBotMessage.Status.PROCESSING,
        )
        reply = f"Ціна 1090 грн [PRICE_QUOTED:1090] [PRODUCT:{product.pk}]"
        with patch("management.services.instagram_bot.gemini_generate", return_value=reply), patch(
            "management.services.bot_sales_classifier.ensure_rule_classification",
            return_value=None,
        ):
            self.assertTrue(instagram_bot._process_one(settings, row))

        event = IgFunnelStepEvent.objects.get(
            episode__client=client,
            event_type=IgFunnelStepEvent.Type.PRICE_QUOTED,
        )
        self.assertEqual(event.evidence["amount"], "1090.00")
        self.assertEqual(event.evidence["product_id"], product.pk)
        self.assertEqual(event.evidence["price_source"], "catalog")

    def test_objection_lifecycle_records_raised_fact_from_inbound_message_once(self):
        from management.models import IgFunnelStepEvent, IgObjection, InstagramBotMessage
        from management.services.ig_objections import observe_inbound_objection

        client = IgClient.get_or_create_for_sender("ig-objection-raised")
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Для мене це дорого",
            status=InstagramBotMessage.Status.DONE,
        )

        observe_inbound_objection(
            client,
            message,
            IgObjection.Type.PRICE,
            readiness=40,
        )
        observe_inbound_objection(
            client,
            message,
            IgObjection.Type.PRICE,
            readiness=40,
        )

        event = IgFunnelStepEvent.objects.get(
            episode__client=client,
            event_type=IgFunnelStepEvent.Type.OBJECTION_RAISED,
        )
        self.assertEqual(event.evidence["objection_type"], IgObjection.Type.PRICE)
        self.assertEqual(event.evidence["message_id"], message.pk)
        self.assertEqual(
            IgFunnelStepEvent.objects.filter(
                episode__client=client,
                event_type=IgFunnelStepEvent.Type.OBJECTION_RAISED,
            ).count(),
            1,
        )

    def test_verified_objection_attempt_records_handled_fact(self):
        from management.models import IgFunnelStepEvent, IgObjection, InstagramBotMessage
        from management.services.ig_objections import (
            observe_inbound_objection,
            record_reply_attempt,
        )

        client = IgClient.get_or_create_for_sender("ig-objection-handled")
        inbound = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Це дорого",
            status=InstagramBotMessage.Status.DONE,
        )
        observe_inbound_objection(
            client,
            inbound,
            IgObjection.Type.PRICE,
            readiness=40,
        )
        reply = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.MODEL,
            text="У нас міцна тканина та якісний DTF принт.",
            status=InstagramBotMessage.Status.DONE,
        )

        record_reply_attempt(
            client,
            reply,
            {"objhandle": "price:value_breakdown"},
            reply.text,
        )

        event = IgFunnelStepEvent.objects.get(
            episode__client=client,
            event_type=IgFunnelStepEvent.Type.OBJECTION_HANDLED,
        )
        self.assertTrue(event.evidence["verified"])
        self.assertEqual(event.evidence["reply_message_id"], reply.pk)

    def test_silence_hours_use_kyiv_working_time_not_wall_clock(self):
        from management.services.ig_funnel_analytics import working_hours_between

        kyiv = ZoneInfo("Europe/Kyiv")
        friday_evening = timezone.make_aware(datetime(2026, 7, 31, 21, 30), kyiv)
        monday_morning = timezone.make_aware(datetime(2026, 8, 3, 11, 0), kyiv)
        self.assertEqual(
            working_hours_between(friday_evening, monday_morning),
            Decimal("1.00"),
        )

    def test_new_inbound_recovers_existing_recoverable_drop_off_once(self):
        from management.models import IgFunnelDropOff, IgFunnelStepEvent
        from management.services.ig_funnel_analytics import record_client_step_event

        client = IgClient.get_or_create_for_sender("ig-recovery")
        first = record_client_step_event(
            client,
            event_type=IgFunnelStepEvent.Type.DROP_OFF,
            event_key="recovery:drop-off",
            evidence={"kind": IgFunnelDropOff.Kind.SILENCE},
        )
        self.assertIsNotNone(first.drop_off)
        recovered = record_client_step_event(
            client,
            event_type=IgFunnelStepEvent.Type.BOT_REPLIED_FIRST,
            event_key="recovery:first-reply",
        )
        self.assertEqual(recovered.event_type, IgFunnelStepEvent.Type.BOT_REPLIED_FIRST)
        drop_off = IgFunnelDropOff.objects.get(step_event=first)
        self.assertIsNotNone(drop_off.recovered_at)
        self.assertEqual(drop_off.recovery_event.event_type, IgFunnelStepEvent.Type.RECOVERED)
        self.assertEqual(
            IgFunnelStepEvent.objects.filter(
                event_type=IgFunnelStepEvent.Type.RECOVERED,
            ).count(),
            1,
        )
        record_client_step_event(
            client,
            event_type=IgFunnelStepEvent.Type.BOT_REPLIED_FIRST,
            event_key="recovery:first-reply",
        )
        self.assertEqual(
            IgFunnelStepEvent.objects.filter(
                event_type=IgFunnelStepEvent.Type.RECOVERED,
            ).count(),
            1,
        )

    def test_funnel_events_are_append_only(self):
        from management.models import IgFunnelStepEvent
        from management.services.ig_funnel_analytics import record_client_step_event

        client = IgClient.get_or_create_for_sender("ig-append-only")
        event = record_client_step_event(
            client,
            event_type=IgFunnelStepEvent.Type.CONVERSATION_STARTED,
            event_key="append:conversation",
        )
        event.stage = "tampered"
        with self.assertRaises(ValueError):
            event.save()

    def test_product_pin_records_the_evidence_backed_funnel_step(self):
        from management.models import IgFunnelStepEvent
        from management.services import bot_orders
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Funnel", slug="funnel-product")
        product = Product.objects.create(
            title="Funnel product",
            slug="funnel-product-item",
            category=category,
            price=1090,
            status=ProductStatus.PUBLISHED,
        )
        client = IgClient.get_or_create_for_sender("ig-product-step")

        self.assertTrue(bot_orders.pin_product(client, product.pk))
        event = IgFunnelStepEvent.objects.get(
            episode__client=client,
            event_type=IgFunnelStepEvent.Type.PRODUCT_PINNED,
        )
        self.assertEqual(event.evidence["product_id"], product.pk)

    def test_low_sample_funnel_hides_conversion_percentage(self):
        from management.models import IgFunnelStepEvent
        from management.services.ig_funnel_analytics import record_client_step_event

        client = IgClient.get_or_create_for_sender("ig-low-sample")
        record_client_step_event(
            client,
            event_type=IgFunnelStepEvent.Type.BOT_REPLIED_FIRST,
            event_key="low-sample:first-reply",
        )
        payload = self.client.get(reverse("management_bot_stats_api") + "?days=7").json()
        first_step = payload["funnel"][0]
        self.assertTrue(first_step["low_sample"])
        self.assertIsNone(first_step["cr_percent"])

    def test_admin_template_renders_event_cohort_separately_from_stage_snapshot(self):
        response = self.client.get(reverse("management_bot"))

        self.assertContains(response, "Когортна воронка")
        self.assertContains(response, "Поточний стан діалогів")

    def test_variant_aware_quote_accepts_thermo_price_instead_of_base_price(self):
        from management.services.instagram_bot import _validated_price_quote
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import Category, Product, ProductStatus

        category = Category.objects.create(name="Thermo", slug="funnel-thermo")
        product = Product.objects.create(
            title="Футболка бойова квиточка",
            slug="funnel-thermo-product",
            category=category,
            price=1090,
            status=ProductStatus.PUBLISHED,
        )
        white = Color.objects.create(name="Білий", primary_hex="#FFFFFF")
        thermo = Color.objects.create(name="Термохром", primary_hex="#222222")
        ProductColorVariant.objects.create(
            product=product, color=white, price_override=1090, is_default=True,
        )
        thermo_variant = ProductColorVariant.objects.create(
            product=product, color=thermo, price_override=1590,
        )
        client = IgClient.get_or_create_for_sender("ig-thermo-price")
        client.current_product = product
        client.sales_context = {
            "assisted_checkout_selection": {
                "product_id": product.pk,
                "color_variant_id": thermo_variant.pk,
            }
        }
        client.save(update_fields=["current_product", "sales_context", "updated_at"])

        quote = _validated_price_quote(
            client,
            {
                "product": product.pk,
                "variant": thermo_variant.pk,
                "price_quoted": "1590",
            },
        )

        self.assertEqual(quote["amount"], "1590.00")
        self.assertEqual(quote["color_variant_id"], thermo_variant.pk)
        self.assertIsNone(
            _validated_price_quote(
                client,
                {
                    "product": product.pk,
                    "variant": thermo_variant.pk,
                    "price_quoted": "1090",
                },
            )
        )

    def test_operational_silence_scan_is_dry_run_by_default_and_idempotent_when_applied(self):
        from management.models import IgFunnelDropOff, IgFunnelStepEvent
        from management.services.ig_funnel_analytics import scan_open_dropoffs

        now = timezone.make_aware(datetime(2026, 8, 5, 12, 0), ZoneInfo("Europe/Kyiv"))
        client = IgClient.get_or_create_for_sender("ig-silence-scan")
        client.stage = IgClient.Stage.CHECKOUT
        client.last_message_at = now - timedelta(hours=30)
        client.save(update_fields=["stage", "last_message_at", "updated_at"])

        dry = scan_open_dropoffs(now=now, limit=10)
        self.assertEqual(dry["matched"], 1)
        self.assertFalse(dry["applied"])
        self.assertEqual(IgFunnelStepEvent.objects.count(), 0)

        first = scan_open_dropoffs(now=now, limit=10, apply=True)
        second = scan_open_dropoffs(now=now, limit=10, apply=True)
        self.assertEqual(first["matched"], 1)
        self.assertEqual(second["matched"], 1)
        self.assertEqual(
            IgFunnelDropOff.objects.filter(
                episode__client=client,
                kind=IgFunnelDropOff.Kind.SILENCE,
            ).count(),
            1,
        )

    @patch("management.services.instagram_bot.notify_manager", return_value=True)
    def test_manager_echo_records_one_manager_engaged_fact(self, _notify):
        from management.models import IgFunnelStepEvent

        client = IgClient.get_or_create_for_sender("ig-manager-funnel")
        instagram_bot._handle_echo(
            client.igsid,
            "Підключаюсь до діалогу",
            mid="manager-mid-1",
            persistence_only=True,
        )
        instagram_bot._handle_echo(
            client.igsid,
            "Ще уточнення",
            mid="manager-mid-2",
            persistence_only=True,
        )

        self.assertEqual(
            IgFunnelStepEvent.objects.filter(
                episode__client=client,
                event_type=IgFunnelStepEvent.Type.MANAGER_ENGAGED,
            ).count(),
            1,
        )
