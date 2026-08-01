"""W3 / IMP-015 — обмін і повернення перестають бути скаргою.

Це друга половина критерію приймання хвилі. Перша (IMP-013/014) зробила
клієнта #59 «оплачено»; ця задача забирає в нього ярлик «Підтримка / скарга».

Механіка дефекту (F-SCORE-002, F-SCORE-006):

1. `SUPPORT_RE` містить `обмін\\w*|обмен\\w*|поверн\\w*|refund|return|exchange`,
   тому «розмір не підійшов, хочу обмін» ловиться як скарга;
2. перевірка скарги стоїть **вище** перевірки покупки, тому навіть покупець
   не доходить до `paid_order_waiting`;
3. `SIZE_RE` у тому ж тексті ставить `primary_objection=SIZE`, і прохання про
   обмін потрапляє в таблицю «Заперечення клієнтів» — тобто записується як
   заперечення **проти покупки**, яка вже відбулася.

Обмін — не скарга і не заперечення. Це окремий сервісний кейс на тлі
здійсненої покупки, і домен для нього вже існує: `IgPostSaleCase`
з `CaseType.EXCHANGE/RETURN` та готовий `detect_post_sale_type()`.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from management.ig_bot_models import (
    IgClient,
    IgConversationAnalysisSnapshot,
    IgPaymentConfirmationReview,
    IgPaymentReviewDecision,
)
from management.models import InstagramBotMessage
from orders.models import Order


Types = IgConversationAnalysisSnapshot.InteractionType


class PostSaleSemanticsMixin:
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
        return client

    def _interaction_type(self, client, text, *, role=None, result=None):
        from management.services.bot_sales_classifier import _interaction_type

        return _interaction_type(
            client,
            result or {},
            text,
            role or InstagramBotMessage.Role.USER,
        )


class PostSaleInteractionTypeTests(PostSaleSemanticsMixin, TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "post-sale-semantics-manager", password="x", is_staff=True
        )

    def test_buyer_asking_for_exchange_is_an_exchange_request(self):
        """Дословний кейс заказчика: клієнт #59."""
        buyer = self._buyer("post-sale-exchange-buyer")

        self.assertEqual(
            self._interaction_type(buyer, "розмір не підійшов, хочу обмін"),
            Types.EXCHANGE_REQUEST,
        )

    def test_buyer_asking_for_refund_is_a_return_request(self):
        """F-PAT-001 #6: «поверніть кошти» від оплатившого."""
        buyer = self._buyer("post-sale-refund-buyer")

        self.assertEqual(
            self._interaction_type(buyer, "поверніть кошти за замовлення"),
            Types.RETURN_REQUEST,
        )

    def test_undelivered_parcel_from_buyer_is_still_a_complaint(self):
        """Реальна скарга мусить лишитися скаргою — інакше ми втратимо сигнал."""
        buyer = self._buyer("post-sale-undelivered-buyer")

        self.assertEqual(
            self._interaction_type(buyer, "товар не прийшов, де посилка?"),
            Types.SUPPORT_COMPLAINT,
        )

    def test_defective_item_from_buyer_is_still_a_complaint(self):
        buyer = self._buyer("post-sale-defect-buyer")

        self.assertEqual(
            self._interaction_type(buyer, "на футболці брак, шов розійшовся"),
            Types.SUPPORT_COMPLAINT,
        )

    def test_buyer_without_post_sale_text_stays_paid_order_waiting(self):
        buyer = self._buyer("post-sale-neutral-buyer")

        self.assertEqual(
            self._interaction_type(buyer, "дякую, все супер"),
            Types.PAID_ORDER_WAITING,
        )

    def test_pre_sale_size_change_question_is_not_a_post_sale_request(self):
        """F-PAT-001 #3: «а можна поміняти розмір на L?» до покупки."""
        stranger = IgClient.get_or_create_for_sender("post-sale-pre-sale-asker")

        result = self._interaction_type(stranger, "а можна поміняти розмір на L?")

        self.assertNotIn(result, {Types.EXCHANGE_REQUEST, Types.RETURN_REQUEST})

    def test_manager_message_stays_an_observation(self):
        buyer = self._buyer("post-sale-manager-message")

        self.assertEqual(
            self._interaction_type(
                buyer,
                "оформив обмін на XL",
                role=InstagramBotMessage.Role.MANAGER,
            ),
            Types.MANAGER_OBSERVATION,
        )

    def test_opt_out_wins_over_post_sale(self):
        buyer = self._buyer("post-sale-opt-out")

        self.assertEqual(
            self._interaction_type(
                buyer, "хочу обмін, але більше не пишіть", result={"opt_out": True}
            ),
            Types.OPT_OUT,
        )


class PostSaleTypeDetectionTests(TestCase):
    def test_refund_request_in_ukrainian_imperative_is_detected(self):
        """`RETURN_RE` не ловив «поверніть/верніть» — найпоширенішу форму."""
        from management.ig_bot_models import IgPostSaleCase
        from management.services.ig_post_sale import detect_post_sale_type

        for text in (
            "поверніть кошти за замовлення",
            "верніть гроші будь ласка",
            "поверните деньги",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    detect_post_sale_type(text), IgPostSaleCase.CaseType.RETURN
                )

    def test_delivery_complaint_is_not_a_post_sale_type(self):
        from management.services.ig_post_sale import detect_post_sale_type

        self.assertEqual(detect_post_sale_type("товар не прийшов"), "")

    def test_returning_to_the_topic_is_not_a_refund_request(self):
        """«поверн\\w*» надто широкий: не кожне слово з цим коренем — повернення."""
        from management.services.ig_post_sale import detect_post_sale_type

        self.assertEqual(
            detect_post_sale_type("повернуся до вас завтра з розміром"), ""
        )


class PostSaleObjectionTests(PostSaleSemanticsMixin, TestCase):
    """F-SCORE-006: постпродажне звернення не є заперечення проти покупки."""

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "post-sale-objection-manager", password="x", is_staff=True
        )

    def test_exchange_request_does_not_become_a_size_objection(self):
        from management.services.bot_sales_classifier import classify_message

        buyer = self._buyer("post-sale-objection-buyer")

        classify_message(buyer, text="розмір L не підійшов, хочу обмін на XL", role="user")

        buyer.refresh_from_db()
        self.assertNotEqual(
            buyer.primary_objection,
            IgClient.Objection.SIZE,
            "прохання про обмін не є заперечення проти покупки",
        )

    def test_pre_sale_size_question_still_sets_size_objection(self):
        """Регрес: до покупки питання про розмір лишається заперечанням."""
        from management.services.bot_sales_classifier import classify_message

        stranger = IgClient.get_or_create_for_sender("post-sale-objection-stranger")

        classify_message(stranger, text="не знаю який розмір L чи XL", role="user")

        stranger.refresh_from_db()
        self.assertEqual(stranger.primary_objection, IgClient.Objection.SIZE)


class PostSalePresentationTests(PostSaleSemanticsMixin, TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "post-sale-presentation-manager", password="x", is_staff=True
        )

    def test_exchange_request_tone_is_not_support(self):
        """Червоний бейдж «скарга» на обміні — це і є скарга заказчика."""
        from management.bot_views import _interaction_tone

        self.assertNotEqual(_interaction_tone(Types.EXCHANGE_REQUEST), "support")
        self.assertNotEqual(_interaction_tone(Types.RETURN_REQUEST), "support")

    def test_exchange_and_return_share_a_service_tone(self):
        from management.bot_views import _interaction_tone

        self.assertEqual(_interaction_tone(Types.EXCHANGE_REQUEST), "service")
        self.assertEqual(_interaction_tone(Types.RETURN_REQUEST), "service")

    def test_real_complaint_keeps_support_tone(self):
        from management.bot_views import _interaction_tone

        self.assertEqual(_interaction_tone(Types.SUPPORT_COMPLAINT), "support")

    def test_service_tone_has_its_own_badge_style(self):
        """Без свого стилю тон `service` відрендериться як безбарвний `neutral`."""
        from pathlib import Path

        from django.conf import settings

        template = (
            Path(settings.BASE_DIR)
            / "management"
            / "templates"
            / "management"
            / "bot.html"
        ).read_text(encoding="utf-8")

        self.assertTrue(
            ".bot-category-badge.cat-service{" in template,
            "у bot.html немає стилю .bot-category-badge.cat-service",
        )

    def test_analysis_prompt_lists_the_new_types(self):
        from management.services.bot_conversation_analysis import SYSTEM_PROMPT

        self.assertIn("exchange_request", SYSTEM_PROMPT)
        self.assertIn("return_request", SYSTEM_PROMPT)

    def test_normalize_accepts_exchange_request_from_the_model(self):
        from management.services.bot_conversation_analysis import _normalize

        result = _normalize(
            {
                "interaction_type": Types.EXCHANGE_REQUEST,
                "score_band": IgConversationAnalysisSnapshot.Band.PAID,
                "purchase_probability": "0.1000",
                "confidence": "0.9000",
                "summary": "клієнт просить обмін розміру",
                "uncertainties": [],
            },
            {},
            verified_payment=True,
        )

        self.assertEqual(result["interaction_type"], Types.EXCHANGE_REQUEST)


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class ComplaintsViewTests(PostSaleSemanticsMixin, TestCase):
    """Фільтр «скарги» мусить показувати скарги, а не сервісні звернення."""

    def setUp(self):
        from django.test import Client as DjangoClient

        self.manager = get_user_model().objects.create_user(
            "complaints-view-manager", password="x", is_staff=True, is_superuser=True
        )
        self.http = DjangoClient()
        self.http.force_login(self.manager)

    def _client_with_type(self, key, interaction_type):
        client = IgClient.get_or_create_for_sender(key)
        message = InstagramBotMessage.objects.create(
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="текст",
        )
        IgConversationAnalysisSnapshot.objects.create(
            client=client,
            last_analyzed_message=message,
            interaction_type=interaction_type,
            score_band=IgConversationAnalysisSnapshot.Band.EXPLORING,
            dedupe_key=f"complaints-view:{key}:{message.pk}",
        )
        return client

    def test_complaints_view_excludes_exchange_requests(self):
        from django.urls import reverse

        complaint = self._client_with_type("complaints-real", Types.SUPPORT_COMPLAINT)
        exchange = self._client_with_type("complaints-exchange", Types.EXCHANGE_REQUEST)

        data = self.http.get(
            reverse("management_bot_clients_api"), {"view": "complaints"}
        ).json()
        rows = {row["id"]: row for row in data["clients"]}

        self.assertIn(complaint.pk, rows)
        self.assertNotIn(exchange.pk, rows)
        self.assertEqual(rows[complaint.pk]["interaction_tone"], "support")

    def test_exchange_request_row_is_labelled_as_a_service_case(self):
        from django.urls import reverse

        exchange = self._client_with_type(
            "complaints-exchange-label", Types.EXCHANGE_REQUEST
        )

        data = self.http.get(reverse("management_bot_clients_api")).json()
        row = next(item for item in data["clients"] if item["id"] == exchange.pk)

        self.assertEqual(row["interaction_type"], "exchange_request")
        self.assertEqual(row["interaction_type_label"], "Обмін товару")
        self.assertEqual(row["interaction_tone"], "service")
