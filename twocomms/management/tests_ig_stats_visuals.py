from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from management.models import (
    IgClient,
    IgDeal,
    IgDealItem,
    IgFunnelDropOff,
    InstagramBotMessage,
)


MGMT = override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "management.twocomms.shop", "localhost"],
    SECURE_SSL_REDIRECT=False,
)
KYIV = ZoneInfo("Europe/Kyiv")


@MGMT
class StatsApiVisualContractTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            "stats-visual-staff",
            password="test",
            is_staff=True,
        )
        self.client.force_login(staff)

    def _client(self, sender, **fields):
        row = IgClient.get_or_create_for_sender(sender)
        for key, value in fields.items():
            setattr(row, key, value)
        row.save()
        return row

    def _message(self, client, role, created_at, text="test"):
        row = InstagramBotMessage.objects.create(
            client=client,
            sender_id=client.igsid,
            role=role,
            text=text,
            status=InstagramBotMessage.Status.DONE,
        )
        InstagramBotMessage.objects.filter(pk=row.pk).update(created_at=created_at)
        client.last_message_at = created_at
        client.save(update_fields=["last_message_at", "updated_at"])
        return row

    def test_additive_contract_exposes_server_period_and_message_role_totals(self):
        moment = timezone.make_aware(datetime(2026, 8, 5, 12, 0), KYIV)
        first = self._client("stats-visible-one")
        second = self._client("stats-visible-two")
        hidden = self._client("stats-hidden", hidden_at=moment)

        self._message(first, InstagramBotMessage.Role.USER, moment)
        self._message(first, InstagramBotMessage.Role.MODEL, moment + timedelta(minutes=1))
        self._message(first, InstagramBotMessage.Role.MANAGER, moment + timedelta(minutes=2))
        self._message(second, InstagramBotMessage.Role.USER, moment + timedelta(minutes=3))
        self._message(hidden, InstagramBotMessage.Role.USER, moment + timedelta(minutes=4))

        payload = self.client.get(
            reverse("management_bot_stats_api")
            + "?date_from=2026-08-05&date_to=2026-08-05"
        ).json()

        self.assertTrue(payload["success"])
        self.assertEqual(payload["schema_version"], 2)
        self.assertIsNotNone(datetime.fromisoformat(payload["generated_at"]).tzinfo)
        self.assertEqual(payload["period"]["mode"], "custom")
        self.assertEqual(payload["period"]["timezone"], "Europe/Kiev")
        self.assertEqual(payload["period"]["date_from"], "2026-08-05")
        self.assertEqual(payload["period"]["date_to"], "2026-08-05")
        self.assertEqual(
            datetime.fromisoformat(payload["period"]["local"]["to_exclusive"]).date(),
            datetime(2026, 8, 6).date(),
        )
        self.assertEqual(payload["totals"]["messages"], 4)
        self.assertEqual(payload["totals"]["inbound_messages"], 2)
        self.assertEqual(payload["totals"]["bot_replies"], 1)
        self.assertEqual(payload["totals"]["manager_messages"], 1)
        self.assertEqual(payload["totals"]["unique_conversations"], 2)
        for key in (
            "conversations",
            "qualified",
            "paid",
            "stages",
            "funnel",
            "products",
            "ads",
        ):
            container = payload["totals"] if key in {"conversations", "qualified", "paid"} else payload
            self.assertIn(key, container)

    def test_message_period_uses_provider_time_and_counts_unlinked_sender(self):
        inside = timezone.make_aware(datetime(2026, 8, 5, 12, 0), KYIV)
        outside = timezone.make_aware(datetime(2026, 7, 5, 12, 0), KYIV)
        linked = self._client("stats-provider-time")

        recovered = self._message(
            linked,
            InstagramBotMessage.Role.USER,
            inside + timedelta(days=2),
        )
        InstagramBotMessage.objects.filter(pk=recovered.pk).update(
            provider_created_at=inside
        )
        stale_provider = self._message(
            linked,
            InstagramBotMessage.Role.MODEL,
            inside,
        )
        InstagramBotMessage.objects.filter(pk=stale_provider.pk).update(
            provider_created_at=outside
        )
        unlinked = InstagramBotMessage.objects.create(
            client=None,
            sender_id="stats-unlinked",
            role=InstagramBotMessage.Role.USER,
            text="new sender",
            status=InstagramBotMessage.Status.DONE,
        )
        InstagramBotMessage.objects.filter(pk=unlinked.pk).update(created_at=inside)

        payload = self.client.get(
            reverse("management_bot_stats_api")
            + "?date_from=2026-08-05&date_to=2026-08-05"
        ).json()

        self.assertEqual(payload["totals"]["messages"], 2)
        self.assertEqual(payload["totals"]["inbound_messages"], 2)
        self.assertEqual(payload["totals"]["bot_replies"], 0)
        self.assertEqual(payload["totals"]["unique_conversations"], 2)
        self.assertEqual(payload["totals"]["funnel_conversations"], 1)
        self.assertEqual(payload["totals"]["funnel_qualified"], 0)
        self.assertEqual(
            payload["period"]["event_time"],
            "provider_created_at_or_created_at",
        )

    def test_preset_period_ends_on_current_local_date(self):
        moment = timezone.make_aware(datetime(2026, 8, 7, 13, 0), KYIV)

        with patch("management.bot_views.timezone.now", return_value=moment):
            payload = self.client.get(
                reverse("management_bot_stats_api") + "?days=7"
            ).json()

        self.assertEqual(payload["period"]["date_to"], "2026-08-07")
        self.assertEqual(payload["period"]["label"], "Останні 7 днів")

    def test_loss_uses_unrecovered_canonical_drop_offs_and_paid_stage_is_unverified(self):
        from management.services.ig_funnel_analytics import record_drop_off_for_client

        moment = timezone.now()
        qualified = self._client(
            "stats-qualified",
            buying_readiness=45,
            last_message_at=moment,
        )
        lost = self._client(
            "stats-lost",
            stage=IgClient.Stage.COLD,
            lost_reason="manual_lost",
            primary_objection=IgClient.Objection.NO_BUY,
            last_message_at=moment,
        )
        refused = self._client(
            "stats-refused",
            primary_objection=IgClient.Objection.NO_BUY,
            last_message_at=moment,
        )
        opted_out = self._client(
            "stats-opted-out",
            opted_out_at=moment,
            last_message_at=moment,
        )
        recovered = self._client("stats-recovered", last_message_at=moment)
        legacy_only = self._client(
            "stats-legacy-only",
            stage=IgClient.Stage.COLD,
            lost_reason="legacy_label",
            last_message_at=moment,
        )
        forged_paid = self._client(
            "stats-forged-paid",
            stage=IgClient.Stage.PAID,
            last_message_at=moment,
        )
        for row in (
            qualified,
            lost,
            refused,
            opted_out,
            recovered,
            legacy_only,
            forged_paid,
        ):
            self._message(row, InstagramBotMessage.Role.USER, moment)

        record_drop_off_for_client(
            lost,
            kind=IgFunnelDropOff.Kind.EXPLICIT_REFUSAL,
            reason_code="no_buy",
            occurred_at=moment,
        )
        record_drop_off_for_client(
            lost,
            kind=IgFunnelDropOff.Kind.SILENCE,
            reason_code="silence_after_offer",
            occurred_at=moment,
        )
        record_drop_off_for_client(
            refused,
            kind=IgFunnelDropOff.Kind.EXPLICIT_REFUSAL,
            reason_code="not_interested",
            occurred_at=moment,
        )
        record_drop_off_for_client(
            opted_out,
            kind=IgFunnelDropOff.Kind.OPT_OUT,
            reason_code="stop_messages",
            occurred_at=moment,
        )
        record_drop_off_for_client(
            recovered,
            kind=IgFunnelDropOff.Kind.SILENCE,
            reason_code="later_recovered",
            occurred_at=moment,
        )
        IgFunnelDropOff.objects.filter(episode__client=recovered).update(
            recovered_at=moment
        )

        payload = self.client.get(
            reverse("management_bot_stats_api") + "?days=7"
        ).json()

        self.assertEqual(payload["totals"]["qualified"], 1)
        self.assertEqual(payload["totals"]["lost_or_refused"], 2)
        self.assertEqual(payload["totals"]["paid"], 0)

    def test_empty_custom_period_returns_honest_zero_shape(self):
        payload = self.client.get(
            reverse("management_bot_stats_api")
            + "?date_from=2036-08-05&date_to=2036-08-05"
        ).json()

        self.assertTrue(payload["success"])
        for key in (
            "messages",
            "inbound_messages",
            "bot_replies",
            "manager_messages",
            "unique_conversations",
            "paid",
            "lost_or_refused",
        ):
            self.assertEqual(payload["totals"][key], 0)
        self.assertEqual(payload["interactions"], [])
        self.assertEqual(payload["products"], [])
        self.assertEqual(payload["ads"], [])
        self.assertNotIn("trend", payload)
        self.assertNotIn("delta", payload)

    def test_message_activity_series_uses_real_daily_role_buckets(self):
        first_day = timezone.make_aware(datetime(2026, 8, 5, 12, 0), KYIV)
        second_day = first_day + timedelta(days=1)
        row = self._client("stats-series")
        self._message(row, InstagramBotMessage.Role.USER, first_day)
        self._message(
            row,
            InstagramBotMessage.Role.MODEL,
            first_day + timedelta(minutes=1),
        )
        self._message(row, InstagramBotMessage.Role.MANAGER, second_day)

        payload = self.client.get(
            reverse("management_bot_stats_api")
            + "?date_from=2026-08-05&date_to=2026-08-06"
        ).json()

        self.assertEqual(payload["message_series"]["granularity"], "day")
        self.assertEqual(
            payload["message_series"]["items"],
            [
                {
                    "bucket": "2026-08-05",
                    "messages": 2,
                    "inbound_messages": 1,
                    "bot_replies": 1,
                    "manager_messages": 0,
                },
                {
                    "bucket": "2026-08-06",
                    "messages": 1,
                    "inbound_messages": 0,
                    "bot_replies": 0,
                    "manager_messages": 1,
                },
            ],
        )

    def test_message_activity_series_exposes_integrity_metadata_and_reconciles_totals(self):
        first_day = timezone.make_aware(datetime(2026, 8, 5, 12, 0), KYIV)
        row = self._client("stats-series-integrity")
        first = self._message(row, InstagramBotMessage.Role.USER, first_day)
        second = self._message(
            row,
            InstagramBotMessage.Role.MODEL,
            first_day + timedelta(minutes=1),
        )
        InstagramBotMessage.objects.filter(pk=second.pk).update(
            provider_created_at=first_day + timedelta(minutes=2),
        )

        payload = self.client.get(
            reverse("management_bot_stats_api")
            + "?date_from=2026-08-05&date_to=2026-08-05"
        ).json()

        series = payload["message_series"]
        self.assertTrue(series["has_data"])
        self.assertEqual(series["density"], "single")
        self.assertEqual(series["max_total"], 2)
        self.assertTrue(all(item["bucket"] for item in series["items"]))
        self.assertEqual(
            sum(item["messages"] for item in series["items"]),
            payload["totals"]["messages"],
        )

    def test_empty_message_activity_series_is_explicitly_empty(self):
        payload = self.client.get(
            reverse("management_bot_stats_api")
            + "?date_from=2036-08-05&date_to=2036-08-05"
        ).json()

        series = payload["message_series"]
        self.assertFalse(series["has_data"])
        self.assertEqual(series["max_total"], 0)
        self.assertEqual(series["density"], "single")

    def test_product_rows_connect_real_image_interest_and_verified_paid_items(self):
        from storefront.models import Category, Product

        moment = timezone.now()
        category = Category.objects.create(name="Stats shirts", slug="stats-shirts")
        product = Product.objects.create(
            title="Visual shirt",
            slug="visual-shirt",
            category=category,
            price=1090,
            main_image="products/visual-shirt.webp",
            main_image_alt="Visual shirt front",
        )
        interested = self._client(
            "stats-product-interest",
            current_product=product,
            last_message_at=moment,
        )
        buyer = self._client(
            "stats-product-buyer",
            current_product=product,
            last_message_at=moment,
        )
        self._message(interested, InstagramBotMessage.Role.USER, moment)
        self._message(buyer, InstagramBotMessage.Role.USER, moment)
        deal = IgDeal.objects.create(
            client=buyer,
            status=IgDeal.Status.PAID,
            amount=Decimal("2180.00"),
            payment_status="paid",
            paid_at=moment,
        )
        IgDealItem.objects.create(
            deal=deal,
            product=product,
            title=product.title,
            qty=2,
            unit_price=Decimal("1090.00"),
        )

        payload = self.client.get(
            reverse("management_bot_stats_api") + "?days=7"
        ).json()

        product_row = payload["products"][0]
        self.assertEqual(product_row["product_id"], product.pk)
        self.assertEqual(product_row["count"], 2)
        self.assertEqual(product_row["interest_count"], 2)
        self.assertEqual(product_row["verified_paid_orders"], 1)
        self.assertEqual(product_row["verified_paid_qty"], 2)
        self.assertTrue(
            product_row["image_url"].endswith("/media/products/visual-shirt.webp")
        )
        self.assertEqual(product_row["image_alt"], "Visual shirt front")
        self.assertEqual(
            product_row["thumbnail_url"],
            "/media/products/visual-shirt.webp",
        )
        self.assertEqual(product_row["thumbnail_alt"], "Visual shirt front")

    def test_ad_analytics_connects_attribution_event_funnel_products_and_losses(self):
        from management.models import IgFunnelStepEvent
        from management.services.ig_funnel_analytics import (
            record_client_step_event,
            record_drop_off_for_client,
        )
        from storefront.models import Category, Product

        moment = timezone.now()
        category = Category.objects.create(name="Ad shirts", slug="ad-shirts")
        product = Product.objects.create(
            title="Ad hero shirt",
            slug="ad-hero-shirt",
            category=category,
            price=1090,
            main_image="products/ad-hero-shirt.webp",
        )
        buyer = self._client(
            "stats-ad-buyer",
            ad_id="ad-hero",
            ad_title="Hero creative",
            current_product=product,
            buying_readiness=80,
            last_message_at=moment,
        )
        refused = self._client(
            "stats-ad-refused",
            ad_id="ad-hero",
            ad_title="Hero creative",
            current_product=product,
            buying_readiness=55,
            last_message_at=moment,
        )
        self._message(buyer, InstagramBotMessage.Role.USER, moment)
        self._message(refused, InstagramBotMessage.Role.USER, moment)
        for client, suffix, steps in (
            (
                buyer,
                "buyer",
                (
                    IgFunnelStepEvent.Type.CONVERSATION_STARTED,
                    IgFunnelStepEvent.Type.BOT_REPLIED_FIRST,
                    IgFunnelStepEvent.Type.PRODUCT_PINNED,
                    IgFunnelStepEvent.Type.PRICE_QUOTED,
                    IgFunnelStepEvent.Type.PAYLINK_ISSUED,
                    IgFunnelStepEvent.Type.PAYLINK_VIEWED,
                    IgFunnelStepEvent.Type.PAYMENT_CONFIRMED,
                ),
            ),
            (
                refused,
                "refused",
                (
                    IgFunnelStepEvent.Type.CONVERSATION_STARTED,
                    IgFunnelStepEvent.Type.BOT_REPLIED_FIRST,
                    IgFunnelStepEvent.Type.PRODUCT_PINNED,
                    IgFunnelStepEvent.Type.PRICE_QUOTED,
                ),
            ),
        ):
            for index, event_type in enumerate(steps):
                record_client_step_event(
                    client,
                    event_type=event_type,
                    event_key=f"stats-ad:{suffix}:{event_type}",
                    occurred_at=moment + timedelta(seconds=index),
                )
        record_drop_off_for_client(
            refused,
            kind=IgFunnelDropOff.Kind.EXPLICIT_REFUSAL,
            reason_code="price_too_high",
            stage=IgClient.Stage.CHECKOUT,
            occurred_at=moment + timedelta(minutes=1),
        )
        deal = IgDeal.objects.create(
            client=buyer,
            status=IgDeal.Status.PAID,
            amount=Decimal("1090.00"),
            payment_status="paid",
            paid_at=moment,
        )
        IgDealItem.objects.create(
            deal=deal,
            product=product,
            title=product.title,
            qty=1,
            unit_price=Decimal("1090.00"),
        )

        payload = self.client.get(
            reverse("management_bot_stats_api") + "?days=7"
        ).json()
        ads = payload["ad_analytics"]

        self.assertEqual(ads["totals"]["conversations"], 2)
        self.assertEqual(ads["totals"]["qualified"], 2)
        self.assertEqual(ads["totals"]["product_matched"], 2)
        self.assertEqual(ads["totals"]["paylinks_issued"], 1)
        self.assertEqual(ads["totals"]["paylinks_viewed"], 1)
        self.assertEqual(ads["totals"]["verified_paid"], 1)
        self.assertEqual(ads["totals"]["lost_or_refused"], 1)
        self.assertEqual(ads["totals"]["revenue_unpriced_payments"], 1)
        self.assertEqual(
            ads["attribution"]["basis"],
            "current_client_snapshot",
        )
        self.assertEqual(ads["funnel"][0]["step"], "conversation_started")
        self.assertEqual(ads["funnel"][0]["entered"], 2)
        self.assertEqual(
            next(
                row["entered"]
                for row in ads["funnel"]
                if row["step"] == "paylink_viewed"
            ),
            1,
        )
        self.assertEqual(ads["products"][0]["interest_count"], 2)
        self.assertEqual(ads["products"][0]["verified_paid_qty"], 1)
        self.assertEqual(ads["campaigns"][0]["paylinks_issued"], 1)
        self.assertEqual(ads["campaigns"][0]["lost_or_refused"], 1)

    def test_ad_attribution_coverage_separates_confirmed_partial_and_unattributed_conversations(self):
        moment = timezone.now()
        confirmed = self._client(
            "stats-attribution-confirmed",
            ad_id="coverage-ad",
            ad_title="Coverage creative",
            last_message_at=moment,
        )
        partial = self._client(
            "stats-attribution-partial",
            ad_source="ADS",
            ad_creative_url="https://cdn.example.com/partial-ad.webp",
            last_message_at=moment,
        )
        unattributed = self._client(
            "stats-attribution-unattributed",
            last_message_at=moment,
        )
        for client in (confirmed, partial, unattributed):
            self._message(client, InstagramBotMessage.Role.USER, moment)

        attribution = self.client.get(
            reverse("management_bot_stats_api") + "?days=7"
        ).json()["ad_analytics"]["attribution"]

        self.assertEqual(attribution["conversation_population"], 3)
        self.assertEqual(attribution["confirmed_conversations"], 1)
        self.assertEqual(attribution["partial_conversations"], 1)
        self.assertEqual(attribution["unattributed_conversations"], 1)
        self.assertEqual(attribution["coverage_percent"], 33)
        self.assertEqual(attribution["status"], "partial")
        self.assertEqual(attribution["campaign_count"], 1)

    def test_empty_period_exposes_empty_attribution_coverage_state(self):
        attribution = self.client.get(
            reverse("management_bot_stats_api")
            + "?date_from=2020-01-01&date_to=2020-01-01"
        ).json()["ad_analytics"]["attribution"]

        self.assertEqual(attribution["conversation_population"], 0)
        self.assertEqual(attribution["confirmed_conversations"], 0)
        self.assertEqual(attribution["partial_conversations"], 0)
        self.assertEqual(attribution["unattributed_conversations"], 0)
        self.assertEqual(attribution["coverage_percent"], 0)
        self.assertEqual(attribution["status"], "empty")

    def test_ad_product_keeps_metadata_when_outside_global_top_twenty_five(self):
        from storefront.models import Category, Product

        moment = timezone.now()
        category = Category.objects.create(
            name="Long-tail ad shirts",
            slug="long-tail-ad-shirts",
        )
        for index in range(25):
            product = Product.objects.create(
                title=f"Popular shirt {index:02d}",
                slug=f"popular-shirt-{index:02d}",
                category=category,
                price=1090,
            )
            for client_index in range(2):
                interested = self._client(
                    f"stats-popular-{index:02d}-{client_index}",
                    current_product=product,
                    last_message_at=moment,
                )
                self._message(
                    interested,
                    InstagramBotMessage.Role.USER,
                    moment,
                )

        advertised = Product.objects.create(
            title="Long-tail advertised shirt",
            slug="long-tail-advertised-shirt",
            category=category,
            price=1090,
            main_image="products/long-tail-advertised-shirt.webp",
            main_image_alt="Long-tail advertised shirt front",
        )
        ad_client = self._client(
            "stats-long-tail-ad-client",
            ad_id="long-tail-ad",
            ad_title="Long-tail creative",
            current_product=advertised,
            last_message_at=moment,
        )
        self._message(ad_client, InstagramBotMessage.Role.USER, moment)

        payload = self.client.get(
            reverse("management_bot_stats_api") + "?days=7"
        ).json()

        ad_product = payload["ad_analytics"]["products"][0]
        self.assertEqual(ad_product["product_id"], advertised.pk)
        self.assertEqual(ad_product["product_title"], advertised.title)
        self.assertEqual(
            ad_product["thumbnail_url"],
            "/media/products/long-tail-advertised-shirt.webp",
        )
        self.assertEqual(
            ad_product["thumbnail_alt"],
            "Long-tail advertised shirt front",
        )

    def test_ad_payment_uses_payment_period_not_conversation_recency(self):
        from management.models import IgPaymentProjection

        moment = timezone.now()
        old_message_at = moment - timedelta(days=60)
        buyer = self._client(
            "stats-old-ad-buyer",
            ad_id="old-conversation-ad",
            ad_title="Old conversation creative",
            last_message_at=old_message_at,
        )
        self._message(
            buyer,
            InstagramBotMessage.Role.USER,
            old_message_at,
        )
        deal = IgDeal.objects.create(
            client=buyer,
            status=IgDeal.Status.PAID,
            amount=Decimal("1090.00"),
            payment_status="paid",
            paid_at=moment,
        )
        IgPaymentProjection.objects.create(
            client=buyer,
            deal=deal,
            truth=IgDeal.PaymentTruth.PARTIALLY_REFUNDED,
            gross_amount=Decimal("1090.00"),
            refunded_amount=Decimal("100.00"),
            paid_at=moment,
        )

        ads = self.client.get(
            reverse("management_bot_stats_api") + "?days=7"
        ).json()["ad_analytics"]

        self.assertEqual(ads["totals"]["conversations"], 0)
        self.assertEqual(ads["totals"]["verified_paid"], 1)
        self.assertEqual(ads["totals"]["gross_revenue"], "1090")
        self.assertEqual(ads["totals"]["refunded_revenue"], "100")
        self.assertEqual(ads["totals"]["revenue"], "990")
        self.assertEqual(len(ads["campaigns"]), 1)
        self.assertEqual(ads["campaigns"][0]["chats"], 0)
        self.assertEqual(ads["campaigns"][0]["paid"], 1)
        self.assertEqual(ads["campaigns"][0]["revenue"], "990")

    def test_ad_revenue_is_not_truncated_by_campaign_display_limit(self):
        from management.models import IgPaymentProjection

        moment = timezone.now()
        for campaign_index in range(50):
            for client_index in range(2):
                row = self._client(
                    f"stats-volume-{campaign_index:02d}-{client_index}",
                    ad_id=f"volume-ad-{campaign_index:02d}",
                    ad_title=f"Volume creative {campaign_index:02d}",
                    last_message_at=moment,
                )
                self._message(row, InstagramBotMessage.Role.USER, moment)

        paid = self._client(
            "stats-paid-outside-display-cap",
            ad_id="paid-outside-display-cap",
            ad_title="Paid low-volume creative",
            last_message_at=moment,
        )
        self._message(paid, InstagramBotMessage.Role.USER, moment)
        deal = IgDeal.objects.create(
            client=paid,
            status=IgDeal.Status.PAID,
            amount=Decimal("750.00"),
            payment_status="paid",
            paid_at=moment,
        )
        IgPaymentProjection.objects.create(
            client=paid,
            deal=deal,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("750.00"),
            paid_at=moment,
        )

        ads = self.client.get(
            reverse("management_bot_stats_api") + "?days=7"
        ).json()["ad_analytics"]

        self.assertEqual(ads["totals"]["verified_paid"], 1)
        self.assertEqual(ads["totals"]["revenue"], "750")
        self.assertTrue(
            any(
                row["ad_id"] == "paid-outside-display-cap"
                for row in ads["campaigns"]
            )
        )

    def test_ad_verified_paid_counts_repeat_confirmed_deals_for_one_client(self):
        from management.models import IgPaymentProjection

        moment = timezone.now()
        buyer = self._client(
            "stats-repeat-ad-buyer",
            ad_id="repeat-ad",
            ad_title="Repeat purchase creative",
            last_message_at=moment,
        )
        self._message(buyer, InstagramBotMessage.Role.USER, moment)

        for index, amount in enumerate((Decimal("1090.00"), Decimal("750.00"))):
            deal = IgDeal.objects.create(
                client=buyer,
                status=IgDeal.Status.PAID,
                amount=amount,
                payment_status="paid",
                paid_at=moment + timedelta(minutes=index),
            )
            IgPaymentProjection.objects.create(
                client=buyer,
                deal=deal,
                truth=IgDeal.PaymentTruth.CONFIRMED,
                gross_amount=amount,
                paid_at=deal.paid_at,
            )

        ads = self.client.get(
            reverse("management_bot_stats_api") + "?days=7"
        ).json()["ad_analytics"]

        self.assertEqual(ads["totals"]["verified_paid"], 2)
        self.assertEqual(ads["totals"]["revenue"], "1840")
        self.assertEqual(ads["campaigns"][0]["paid"], 2)

    def test_campaigns_merge_title_variants_under_stable_ad_id(self):
        moment = timezone.now()
        for index, title in enumerate(("Creative title A", "Creative title B")):
            row = self._client(
                f"stats-stable-ad-{index}",
                ad_id="stable-ad-id",
                ad_title=title,
                last_message_at=moment,
            )
            self._message(row, InstagramBotMessage.Role.USER, moment)

        campaigns = self.client.get(
            reverse("management_bot_stats_api") + "?days=7"
        ).json()["ad_analytics"]["campaigns"]

        stable = [row for row in campaigns if row["ad_id"] == "stable-ad-id"]
        self.assertEqual(len(stable), 1)
        self.assertEqual(stable[0]["chats"], 2)
        self.assertEqual(stable[0]["attribution_key_type"], "ad_id")

    def test_stats_api_query_count_stays_bounded(self):
        from management.models import IgFunnelStepEvent, IgPaymentProjection
        from management.services.ig_funnel_analytics import (
            record_client_step_event,
        )
        from storefront.models import Category, Product

        moment = timezone.now()
        category = Category.objects.create(
            name="Query budget shirts",
            slug="query-budget-shirts",
        )
        product = Product.objects.create(
            title="Query budget shirt",
            slug="query-budget-shirt",
            category=category,
            price=1090,
        )
        attributed = self._client(
            "stats-query-budget",
            ad_id="query-budget-ad",
            ad_title="Query budget creative",
            current_product=product,
            last_message_at=moment,
        )
        self._message(attributed, InstagramBotMessage.Role.USER, moment)
        record_client_step_event(
            attributed,
            event_type=IgFunnelStepEvent.Type.PAYLINK_ISSUED,
            event_key="stats-query-budget:paylink-issued",
            occurred_at=moment,
        )
        deal = IgDeal.objects.create(
            client=attributed,
            status=IgDeal.Status.PAID,
            amount=Decimal("1090.00"),
            payment_status="paid",
            paid_at=moment,
        )
        IgPaymentProjection.objects.create(
            client=attributed,
            deal=deal,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("1090.00"),
            paid_at=moment,
        )

        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(
                reverse("management_bot_stats_api") + "?days=7"
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(captured), 65)


class StatsDashboardTemplateContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = (
            Path(__file__).with_name("templates") / "management" / "bot.html"
        ).read_text(encoding="utf-8")

    def test_primary_hierarchy_has_four_stable_kpis_and_server_freshness(self):
        for contract in (
            'class="bot-stats-kpi-grid"',
            "{key:'messages'",
            "{key:'conversations'",
            "{key:'paid'",
            "{key:'lost_or_refused'",
            'data-stats-kpi="\'+spec.key+\'"',
            'id="bot-stats-freshness"',
            "generated_at",
            "font-variant-numeric:tabular-nums",
        ):
            self.assertIn(contract, self.template)

    def test_dashboard_has_truthful_funnel_rankings_and_detail_disclosure(self):
        for contract in (
            "bot-stats-activity-chart",
            "bot-stats-activity-column",
            "message_series",
            "bot-stats-funnel",
            "bot-stats-bottleneck",
            "bot-stats-bar-rail",
            "bot-stats-bar-fill",
            "data-stats-percent",
            "bot-stats-category-bars",
            "bot-stats-product-bars",
            "bot-stats-product-image",
            "verified_paid_qty",
            "interest_count",
            "bot-stats-ad-bars",
            "Детальні дані",
            "Когортна воронка",
            "Причини відвалу",
            "Час на кроці",
            "Бот і менеджер",
            "Знижки",
        ):
            self.assertIn(contract, self.template)

    def test_loading_error_help_and_motion_contracts_are_present(self):
        for contract in (
            "bot-stats-skeleton",
            'id="bot-stats-alert"',
            'id="bot-stats-retry"',
            "bot-stats-help",
            "aria-expanded",
            "event.key==='Escape'",
            "botStatsReveal",
            "botStatsValueOut",
            "botStatsValueIn",
            "botStatsImportantChange",
            "transition:width var(--stats-motion-medium)",
            "prefers-reduced-motion:reduce",
            "function statsPeriodKey(data)",
            "const samePeriod=Boolean(previous&&statsPeriodKey(previous)===statsPeriodKey(data))",
            "const total=normalized.reduce",
            "const shown=normalized.slice(0,7)",
            "formatFreshness(data)",
            "freshnessEl.classList.add('is-stale')",
        ):
            self.assertIn(contract, self.template)

    def test_dashboard_uses_responsive_four_two_one_geometry(self):
        for contract in (
            ".bot-stats-kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));",
            "@media(max-width:880px)",
            ".bot-stats-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))",
            "@media(max-width:560px)",
            ".bot-stats-kpi-grid{grid-template-columns:minmax(0,1fr)",
        ):
            self.assertIn(contract, self.template)

    def test_dashboard_has_compact_overview_advertising_and_product_views(self):
        for contract in (
            "bot-stats-view-switcher",
            'data-stats-view="overview"',
            'data-stats-view="ads"',
            'data-stats-view="products"',
            "function renderAdvertising",
            "function renderProductsView",
            "ad_analytics",
            "paylinks_issued",
            "bot-stats-view-enter",
        ):
            self.assertIn(contract, self.template)

    def test_ad_view_keeps_paid_only_periods_and_discloses_attribution_basis(self):
        for contract in (
            "paylinks_viewed",
            "revenue_unpriced_payments",
            "attribution_key_type",
            "current_client_snapshot",
            "const hasAdvertisingData=",
        ):
            self.assertIn(contract, self.template)
        self.assertNotIn(
            "if(!num(values.conversations))return",
            self.template,
        )

    def test_ad_view_visualizes_attribution_coverage_and_signal_path_even_when_empty(self):
        for contract in (
            "function renderAttributionCoverage",
            "bot-stats-attribution",
            "bot-stats-attribution-ring",
            "bot-stats-attribution-legend",
            "data-attribution-segment",
            "data-attribution-detail",
            "data-ad-signal-step",
            "bot-stats-ad-signal-path",
            "coverage_percent",
            "partial_conversations",
            "unattributed_conversations",
            "conversation_population",
        ):
            self.assertIn(contract, self.template)
        self.assertNotIn(
            "if(!hasAdvertisingData)return '<div class=\"bot-stats-view-zero\"",
            self.template,
        )

    def test_ad_view_bridges_unattributed_overall_activity_without_calling_it_ads(self):
        for contract in (
            "function renderAdContextBridge",
            "bot-stats-context-bridge",
            "Загальний потік · реклама ще не підтверджена",
            "Потрібна рекламна прив’язка",
            "data-context-step",
            "data-context-detail",
            "data-context-population",
            "paylink_issued",
            "paylink_viewed",
            "renderAdContextBridge(data,analytics)",
            "metricValue(data,'conversations')",
            "funnelValue('paylink_issued',overall.paylinks_issued)",
            "funnelValue('paylink_viewed',overall.paylinks_viewed)",
            "num(overall.paid)",
            "if(hasAdData||(!Object.values(values).some(value=>value>0)&&!num(overall.messages)))return ''",
            "toggleContextStep",
            "clearContextSelection",
        ):
            self.assertIn(contract, self.template)

    def test_campaign_ranking_keeps_rows_after_the_primary_eight_in_disclosure(self):
        for contract in (
            "const shown=ranked.slice(0,8)",
            "const remaining=ranked.slice(8)",
            "function renderCampaignRow(row,index)",
            "Ще '+remaining.length+' кампаній",
            'data-stats-disclosure="campaign-more"',
            "bot-stats-campaign-more-list",
        ):
            self.assertIn(contract, self.template)
        self.assertNotIn(
            'data-stats-disclosure="campaign-more" open',
            self.template,
        )

    def test_activity_columns_pin_exact_values_on_tap_and_close_cleanly(self):
        for contract in (
            ".bot-stats-activity-column.is-open .bot-stats-activity-tooltip",
            'aria-expanded="false"',
            "let openActivityColumn=null",
            "function closeActivityTooltip(returnFocus=false)",
            "const activityColumn=event.target.closest('.bot-stats-activity-column')",
            "activityColumn.classList.add('is-open')",
            "activityColumn.setAttribute('aria-expanded','true')",
            "if(openActivityColumn&&!openActivityColumn.contains(event.target))closeActivityTooltip(false)",
            "if(event.key==='Escape'&&openActivityColumn)",
        ):
            self.assertIn(contract, self.template)

    def test_visual_funnel_uses_event_cohorts_and_guards_non_monotonic_steps(self):
        for contract in (
            "const source=(data&&data.funnel||[])",
            "const monotonic=source.every",
            "const drops=model.monotonic?",
            "Окремі події · без оцінки відсіву",
            "renderFunnel(analytics,previousAnalytics",
        ):
            self.assertIn(contract, self.template)
        self.assertNotIn("t.funnel_conversations", self.template)

    def test_activity_uses_density_modes_and_a_single_composition_ring(self):
        for contract in (
            "function activityDensity(series,data)",
            "bot-stats-activity-pulse",
            "bot-stats-activity-density-single",
            "density-compact",
            "density-daily",
            "bot-stats-composition-ring",
            "data-ring-segment",
            "data-ring-value",
            "zero?' is-zero':''",
            "messageSeries.has_data",
            "messageSeries.reconciled",
        ):
            self.assertIn(contract, self.template)

    def test_activity_tooltips_have_one_custom_surface_and_reduced_motion_contract(self):
        self.assertNotIn(
            "data-tooltip-placement=\"auto\" aria-label=\"'+exact+'\" title=\"'+exact+'\"",
            self.template,
        )
        for contract in (
            ".bot-stats-activity-pulse-segment",
            ".bot-stats-ring-segment",
        ):
            self.assertIn(contract, self.template.split("@media(prefers-reduced-motion:reduce)", 1)[1])

    def test_activity_tooltip_applies_the_measured_chart_width(self):
        self.assertIn(
            "width:var(--activity-tooltip-width,max-content)",
            self.template,
        )
        self.assertIn(
            "column.style.setProperty('--activity-tooltip-width',tooltipWidth+'px')",
            self.template,
        )
