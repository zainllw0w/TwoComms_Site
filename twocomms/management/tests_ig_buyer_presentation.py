"""W3 / IMP-019 — честная подпись метрики и бейдж покупателя (F-SCORE-001, DR-002).

Первопричина жалобы заказчика («показує 0% у задоволеного клієнта») — не
неверное вычисление. Промпт анализа **прямо предписывает** не повышать
`purchase_probability` при подтверждённой оплате, потому что метрика описывает
намерение купить, видимое в сообщениях. У человека, который уже купил и
обсуждает обмен, такого намерения нет, и модель честно отдаёт ~0.

Ломается презентация: UI подписывает это число как «ймовірність» без пометки
«клієнт уже купив». Администратор читает «0% — не купить», а модель имела в
виду «сейчас ничего не покупает, потому что уже купил».

DR-002: менять презентацию, не семантику. Здесь — подпись метрики и бейдж
покупателя с честным указанием источника суммы.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from management.ig_bot_models import (
    IgClient,
    IgPaymentConfirmationReview,
    IgPaymentReviewDecision,
)
from orders.models import Order


class BuyerPresentationMixin:
    def _buyer(self, key, *, amount="2100.00"):
        client = IgClient.get_or_create_for_sender(key)
        review = IgPaymentConfirmationReview.objects.create(
            client=client,
            dedupe_key=f"{key}:review",
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
        )
        IgPaymentReviewDecision.objects.create(
            review=review,
            client=client,
            decision=IgPaymentReviewDecision.Decision.MANAGER_VERIFIED,
            verification_source="manager",
            verification_scope=IgPaymentReviewDecision.VerificationScope.FULL_PAYMENT,
            confirmed_amount=Decimal(amount),
            amount_source="manager_input",
            actor=self.manager,
            actor_source=IgPaymentReviewDecision.ActorSource.MANAGEMENT_USER,
            actor_external_id=str(self.manager.pk),
        )
        from management.services.bot_payment_truth import (
            recalculate_client_payment_aggregates,
        )

        recalculate_client_payment_aggregates(client)
        client.refresh_from_db()
        return client


class BuyerBadgePayloadTests(BuyerPresentationMixin, TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "buyer-badge-manager", password="x", is_staff=True
        )

    def test_buyer_payload_exposes_a_buyer_badge(self):
        from management.bot_views import _buyer_badge_payload

        badge = _buyer_badge_payload(self._buyer("badge-simple"))

        self.assertTrue(badge["is_buyer"])
        self.assertEqual(badge["purchases"], 1)
        self.assertIn("купив", badge["label"])

    def test_non_buyer_payload_has_no_badge(self):
        from management.bot_views import _buyer_badge_payload

        badge = _buyer_badge_payload(IgClient.get_or_create_for_sender("badge-none"))

        self.assertFalse(badge["is_buyer"])
        self.assertEqual(badge["label"], "")

    def test_manager_confirmed_amount_is_labelled_as_such(self):
        """Сумма не от провайдера не должна выглядеть как выручка провайдера."""
        from management.bot_views import _buyer_badge_payload

        badge = _buyer_badge_payload(self._buyer("badge-provider-unverified"))

        self.assertTrue(badge["provider_unverified"])
        self.assertIn("менеджер", badge["amount_note"].lower())

    def test_amount_is_shown_when_it_is_known(self):
        from management.bot_views import _buyer_badge_payload

        badge = _buyer_badge_payload(self._buyer("badge-amount", amount="1750.00"))

        self.assertEqual(badge["total_spent"], "1750.00")
        self.assertFalse(badge["amount_unknown"])

    def test_unknown_amount_is_not_reported_as_zero(self):
        from management.bot_views import _buyer_badge_payload
        from management.services.bot_payment_truth import (
            recalculate_client_payment_aggregates,
        )
        from management.services.ig_order_assignments import link_order_to_client

        client = IgClient.get_or_create_for_sender("badge-amount-unknown")
        order = Order.objects.create(
            order_number="TWC-BADGE-PREPAID",
            full_name="Buyer",
            phone="380500000000",
            total_sum=Decimal("1500.00"),
            payment_status="prepaid",
            status="ship",
        )
        link_order_to_client(order, client=client, actor=self.manager)
        recalculate_client_payment_aggregates(client)
        client.refresh_from_db()

        badge = _buyer_badge_payload(client)

        self.assertTrue(badge["is_buyer"])
        self.assertTrue(badge["amount_unknown"])
        self.assertEqual(badge["total_spent"], "")


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class BuyerBadgeApiTests(BuyerPresentationMixin, TestCase):
    def setUp(self):
        from django.test import Client as DjangoClient

        self.manager = get_user_model().objects.create_user(
            "buyer-badge-api-manager",
            password="x",
            is_staff=True,
            is_superuser=True,
        )
        self.http = DjangoClient()
        self.http.force_login(self.manager)

    def test_client_row_carries_the_buyer_badge(self):
        buyer = self._buyer("badge-api-row")

        data = self.http.get(reverse("management_bot_clients_api")).json()
        row = next(item for item in data["clients"] if item["id"] == buyer.pk)

        self.assertTrue(row["buyer"]["is_buyer"])
        self.assertEqual(row["buyer"]["purchases"], 1)

    def test_potential_metric_is_labelled_as_current_intent(self):
        """Число подписано как намерение текущего цикла, а не как «ймовірність»."""
        buyer = self._buyer("badge-api-potential")

        data = self.http.get(reverse("management_bot_clients_api")).json()
        row = next(item for item in data["clients"] if item["id"] == buyer.pk)

        self.assertEqual(row["potential"]["metric_label"], "намір купити зараз")
        self.assertIn("уже купив", row["potential"]["metric_note"])

    def test_non_buyer_metric_note_does_not_claim_a_purchase(self):
        stranger = IgClient.get_or_create_for_sender("badge-api-stranger")

        data = self.http.get(reverse("management_bot_clients_api")).json()
        row = next(item for item in data["clients"] if item["id"] == stranger.pk)

        self.assertEqual(row["potential"]["metric_label"], "намір купити зараз")
        self.assertNotIn("уже купив", row["potential"]["metric_note"])


class BuyerBadgeTemplateTests(TestCase):
    def _template(self):
        from pathlib import Path

        from django.conf import settings

        return (
            Path(settings.BASE_DIR)
            / "management"
            / "templates"
            / "management"
            / "bot.html"
        ).read_text(encoding="utf-8")

    def test_probability_is_no_longer_labelled_as_bare_likelihood(self):
        template = self._template()

        self.assertFalse(
            "'ймовірність'" in template,
            "підпис «ймовірність» без контексту і є першопричиною скарги",
        )

    def test_template_renders_the_buyer_badge(self):
        template = self._template()

        self.assertTrue(
            "bot-buyer-badge" in template,
            "у карточці немає бейджа покупця",
        )

    def test_buyer_badge_has_its_own_style(self):
        template = self._template()

        self.assertTrue(
            ".bot-buyer-badge{" in template,
            "бейдж покупця без стилю зіллється з рештою тексту",
        )


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class BuyerBadgeDetailApiTests(BuyerPresentationMixin, TestCase):
    """Бейдж потрібен і в шапці діалогу, а не лише в списку клієнтів."""

    def setUp(self):
        from django.test import Client as DjangoClient

        self.manager = get_user_model().objects.create_user(
            "buyer-detail-manager", password="x", is_staff=True, is_superuser=True
        )
        self.http = DjangoClient()
        self.http.force_login(self.manager)

    def test_client_detail_carries_the_buyer_badge(self):
        buyer = self._buyer("badge-detail")

        data = self.http.get(
            reverse("management_bot_client_detail_api", args=[buyer.pk])
        ).json()

        self.assertTrue(data["client"]["buyer"]["is_buyer"])
        self.assertEqual(data["client"]["buyer"]["purchases"], 1)
        self.assertTrue(data["client"]["buyer"]["provider_unverified"])

    def test_client_detail_potential_is_labelled(self):
        buyer = self._buyer("badge-detail-potential")

        data = self.http.get(
            reverse("management_bot_client_detail_api", args=[buyer.pk])
        ).json()

        self.assertEqual(
            data["potential"]["metric_label"], "намір купити зараз"
        )
        self.assertIn("уже купив", data["potential"]["metric_note"])
