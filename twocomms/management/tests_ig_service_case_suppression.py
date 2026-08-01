"""W3 / IMP-016 — клієнту з відкритим сервісним кейсом не продають.

F-SCORE-009 у поєднанні з F-CTX-002 описує повний механізм відмови:

1. `_client_allows_followup` не знає про `IgPostSaleCase`, тому клієнт, який
   попросив обмін, через 12 годин отримує «знижка 5%»;
2. `tags_for_client` **безумовно** додає тег `sales`, тому інструкції про
   продаж підбираються навіть у постпродажному діалозі;
3. `SALES_AUTOMATION_GUARDRAILS` з текстом про rescue-офери 5%/10%
   інжектиться в промпт **завжди**, без огляду на стадію.

Тому виправлення лише в follow-up симптом не знімає: бот усе одно знає про
знижки і може запропонувати їх у реактивній відповіді. Гасити треба на трьох
рівнях одночасно.

Клієнта #59 від цієї скидки врятував `manager_takeover`, тобто випадок,
а не правило.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from management.ig_bot_models import (
    IgClient,
    IgPaymentConfirmationReview,
    IgPaymentReviewDecision,
    IgPostSaleCase,
)
from management.models import InstagramBotMessage
from orders.models import Order


class ServiceCaseMixin:
    def _buyer(self, key):
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
            confirmed_amount=Decimal("2100.00"),
            amount_source="manager_input",
            actor=self.manager,
            actor_source=IgPaymentReviewDecision.ActorSource.MANAGEMENT_USER,
            actor_external_id=str(self.manager.pk),
        )
        return client

    def _case(self, client, *, status, case_type=None, key="case"):
        message = InstagramBotMessage.objects.create(
            client=client,
            role=InstagramBotMessage.Role.USER,
            text=f"хочу обмін ({key})",
        )
        order = Order.objects.create(
            order_number=f"TWC-SVC-{client.pk}-{key}",
            full_name="Buyer",
            phone="380500000000",
            total_sum=Decimal("2100.00"),
            payment_status="paid",
            status="ship",
        )
        return IgPostSaleCase.objects.create(
            client=client,
            order=order,
            source_message=message,
            case_type=case_type or IgPostSaleCase.CaseType.EXCHANGE,
            status=status,
            requested_size="XL",
        )


class ServiceCaseFollowupSuppressionTests(ServiceCaseMixin, TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "service-case-manager", password="x", is_staff=True
        )

    def test_open_exchange_case_blocks_followup(self):
        from management.services.bot_followups import _client_allows_followup

        buyer = self._buyer("service-open-exchange")
        self._case(buyer, status=IgPostSaleCase.Status.OPEN)

        allowed, reason = _client_allows_followup(buyer)

        self.assertFalse(allowed)
        self.assertEqual(reason, "service_case_open")

    def test_case_in_transit_still_blocks_followup(self):
        """Стан клієнта #59: заміна вже в дорозі, продавати все одно не час."""
        from management.services.bot_followups import _client_allows_followup

        buyer = self._buyer("service-in-transit")
        self._case(buyer, status=IgPostSaleCase.Status.IN_TRANSIT)

        allowed, reason = _client_allows_followup(buyer)

        self.assertFalse(allowed)
        self.assertEqual(reason, "service_case_open")

    def test_completed_case_stops_blocking_followup(self):
        """Закритий кейс не має глушити продажі назавжди."""
        from management.services.bot_followups import _client_allows_followup

        buyer = self._buyer("service-completed")
        self._case(buyer, status=IgPostSaleCase.Status.COMPLETED)

        allowed, reason = _client_allows_followup(buyer)

        self.assertFalse(allowed)
        self.assertEqual(
            reason,
            "already_converted",
            "після закриття кейсу причиною лишається сам факт покупки, не кейс",
        )

    def test_rescue_discount_is_not_scheduled_during_a_service_case(self):
        """Дословний сценарій скарги: «обмін» → через 12 годин «знижка 5%»."""
        from management.services.bot_followups import schedule_rescue_offer

        buyer = self._buyer("service-rescue-blocked")
        buyer.stage = IgClient.Stage.CHECKOUT
        buyer.save(update_fields=["stage", "updated_at"])
        self._case(buyer, status=IgPostSaleCase.Status.OPEN)

        self.assertIsNone(schedule_rescue_offer(buyer))

    def test_service_interaction_type_blocks_followup_without_a_case(self):
        """Скарга без оформленого кейсу теж не повинна вести до продажі."""
        from management.ig_bot_models import IgConversationAnalysisSnapshot
        from management.services.bot_followups import _client_allows_followup

        client = IgClient.get_or_create_for_sender("service-complaint-no-case")
        message = InstagramBotMessage.objects.create(
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="посилка не прийшла",
        )
        IgConversationAnalysisSnapshot.objects.create(
            client=client,
            last_analyzed_message=message,
            interaction_type=(
                IgConversationAnalysisSnapshot.InteractionType.SUPPORT_COMPLAINT
            ),
            score_band=IgConversationAnalysisSnapshot.Band.COLD,
            dedupe_key="service-complaint-no-case:1",
        )

        allowed, reason = _client_allows_followup(client)

        self.assertFalse(allowed)
        self.assertEqual(reason, "service_case_open")

    def test_clean_buyer_without_a_case_is_not_blocked_for_this_reason(self):
        from management.services.bot_followups import _client_allows_followup

        stranger = IgClient.get_or_create_for_sender("service-clean-lead")

        allowed, reason = _client_allows_followup(stranger)

        self.assertTrue(allowed, reason)


class ServiceCasePromptSuppressionTests(ServiceCaseMixin, TestCase):
    """F-CTX-002: гасити треба і тег `sales`, і текст про rescue-офери."""

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "service-prompt-manager", password="x", is_staff=True
        )

    def test_sales_tag_is_dropped_during_a_service_case(self):
        from management.services.bot_playbooks import tags_for_client

        buyer = self._buyer("service-tags-open")
        self._case(buyer, status=IgPostSaleCase.Status.OPEN)

        tags = tags_for_client(buyer)

        self.assertNotIn("sales", tags)
        self.assertIn("post_sale", tags)

    def test_discount_tags_are_dropped_during_a_service_case(self):
        from management.services.bot_playbooks import tags_for_client

        buyer = self._buyer("service-tags-discount")
        buyer.primary_objection = IgClient.Objection.PRICE
        buyer.save(update_fields=["primary_objection", "updated_at"])
        self._case(buyer, status=IgPostSaleCase.Status.OPEN)

        tags = tags_for_client(buyer)

        self.assertNotIn("discount", tags)

    def test_sales_tag_remains_for_a_normal_lead(self):
        from management.services.bot_playbooks import tags_for_client

        stranger = IgClient.get_or_create_for_sender("service-tags-lead")

        self.assertIn("sales", tags_for_client(stranger))

    def test_rescue_offer_text_is_not_injected_during_a_service_case(self):
        from management.services.instagram_bot import automation_guardrails

        buyer = self._buyer("service-guardrails-open")
        self._case(buyer, status=IgPostSaleCase.Status.OPEN)

        text = automation_guardrails(buyer)

        self.assertNotIn("rescue", text.lower())
        self.assertNotIn("5%", text)
        self.assertNotIn("10%", text)

    def test_service_guardrails_keep_the_anti_invention_rule(self):
        """Прибрати продажну частину не означає прибрати захист від вигадок."""
        from management.services.instagram_bot import automation_guardrails

        buyer = self._buyer("service-guardrails-safety")
        self._case(buyer, status=IgPostSaleCase.Status.OPEN)

        text = automation_guardrails(buyer)

        self.assertIn("Не вигадуй", text)
        self.assertIn("UA/RU/EN", text)

    def test_service_guardrails_name_the_open_case(self):
        from management.services.instagram_bot import automation_guardrails

        buyer = self._buyer("service-guardrails-named")
        self._case(buyer, status=IgPostSaleCase.Status.IN_TRANSIT)

        text = automation_guardrails(buyer)

        self.assertIn("обмін", text.lower())

    def test_normal_lead_still_gets_the_sales_guardrails(self):
        from management.services.instagram_bot import (
            SALES_AUTOMATION_GUARDRAILS,
            automation_guardrails,
        )

        stranger = IgClient.get_or_create_for_sender("service-guardrails-lead")

        self.assertEqual(automation_guardrails(stranger), SALES_AUTOMATION_GUARDRAILS)


class OpenServiceCaseHelperTests(ServiceCaseMixin, TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "service-helper-manager", password="x", is_staff=True
        )

    def test_terminal_statuses_are_not_open(self):
        from management.services.ig_post_sale import open_service_case

        for index, status in enumerate((
            IgPostSaleCase.Status.COMPLETED,
            IgPostSaleCase.Status.REJECTED,
            IgPostSaleCase.Status.CANCELLED,
        )):
            with self.subTest(status=status):
                buyer = self._buyer(f"service-helper-terminal-{index}")
                self._case(buyer, status=status)
                self.assertIsNone(open_service_case(buyer))

    def test_non_terminal_statuses_are_open(self):
        from management.services.ig_post_sale import open_service_case

        for index, status in enumerate((
            IgPostSaleCase.Status.NEEDS_DETAILS,
            IgPostSaleCase.Status.OPEN,
            IgPostSaleCase.Status.APPROVED,
            IgPostSaleCase.Status.IN_TRANSIT,
            IgPostSaleCase.Status.RECEIVED,
        )):
            with self.subTest(status=status):
                buyer = self._buyer(f"service-helper-open-{index}")
                case = self._case(buyer, status=status)
                self.assertEqual(open_service_case(buyer), case)
