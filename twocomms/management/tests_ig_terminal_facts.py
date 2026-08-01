"""W3 / IMP-018 — підтверджений факт важливіший за останню думку моделі.

Дві незалежні проблеми, обидві дають карточці брехати:

**F-SCORE-008.** Карточка бере останній снапшот через `order_by("-id")` без
жодного пріоритету. У клієнта #59 снапшот 1930 з `0.9500` перекритий снапшотом
1945 з `0.0000`, і адміністратор бачить «холодний · скарга · 0%» у людини, яка
оплатила і вже отримує заміну.

**F-STATE-008.** `open_post_sale_case` викликається на **кожне** повідомлення
без перевірки покупки, тому «а можна поміняти розмір на L?» від клієнта з
нулем покупок створює кейс обміну і клієнт назавжди висить у «потрібна дія».

**Плюс скарга заказчика з живого використання:** бейдж обміну світиться
завжди, бо `latest_post_sale` бере останній кейс **будь-якого** статусу,
включно з `completed`. Закритий обмін мусить зникати з карточки.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from management.ig_bot_models import (
    IgClient,
    IgConversationAnalysisSnapshot,
    IgPaymentConfirmationReview,
    IgPaymentReviewDecision,
    IgPostSaleCase,
)
from management.models import InstagramBotMessage
from orders.models import Order

Types = IgConversationAnalysisSnapshot.InteractionType


class TerminalFactsMixin:
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

    def _message(self, client, text, *, role=None):
        return InstagramBotMessage.objects.create(
            client=client,
            role=role or InstagramBotMessage.Role.USER,
            text=text,
        )

    def _case(self, client, *, status, case_type=None, key="c"):
        order = Order.objects.create(
            order_number=f"TWC-TERM-{client.pk}-{key}",
            full_name="Buyer",
            phone="380500000000",
            total_sum=Decimal("2100.00"),
            payment_status="paid",
            status="ship",
        )
        return IgPostSaleCase.objects.create(
            client=client,
            order=order,
            source_message=self._message(client, f"хочу обмін {key}"),
            case_type=case_type or IgPostSaleCase.CaseType.EXCHANGE,
            status=status,
            requested_size="XL",
        )

    def _snapshot(self, client, interaction_type, *, band=None, key="s"):
        return IgConversationAnalysisSnapshot.objects.create(
            client=client,
            last_analyzed_message=self._message(client, f"текст {key}"),
            interaction_type=interaction_type,
            score_band=band or IgConversationAnalysisSnapshot.Band.COLD,
            dedupe_key=f"terminal-facts:{client.pk}:{key}",
        )


class PostSaleCaseCreationGateTests(TerminalFactsMixin, TestCase):
    """F-STATE-008 через семантику тексту, а не через запис про покупку (DR-008).

    Гейт «тільки покупцю» здавався очевидним, але на проді `IgOrderAssignment` —
    2 записи на 289 клієнтів, тому у реального обміну покупки в системі
    зазвичай не видно. Такий гейт вимкнув би сам механізм.
    """

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "terminal-facts-manager", password="x", is_staff=True
        )

    def test_hypothetical_pre_sale_question_creates_no_case(self):
        from management.services.ig_post_sale import open_post_sale_case

        stranger = IgClient.get_or_create_for_sender("terminal-no-purchase")
        message = self._message(stranger, "а можна поміняти розмір на L?")

        self.assertIsNone(open_post_sale_case(stranger, message))
        self.assertEqual(IgPostSaleCase.objects.filter(client=stranger).count(), 0)

    def test_exchange_policy_question_creates_no_case(self):
        from management.services.ig_post_sale import open_post_sale_case

        stranger = IgClient.get_or_create_for_sender("terminal-policy-question")
        message = self._message(stranger, "які у вас умови обміну?")

        self.assertIsNone(open_post_sale_case(stranger, message))

    def test_conditional_pre_sale_question_creates_no_case(self):
        from management.services.ig_post_sale import open_post_sale_case

        stranger = IgClient.get_or_create_for_sender("terminal-conditional")
        message = self._message(stranger, "якщо не підійде, можна обміняти?")

        self.assertIsNone(open_post_sale_case(stranger, message))

    def test_received_item_creates_a_case_even_without_a_recorded_purchase(self):
        """Головний робочий сценарій: заяву про отриманий товар глушити нельзя."""
        from management.services.ig_post_sale import open_post_sale_case

        stranger = IgClient.get_or_create_for_sender("terminal-received-unlinked")
        message = self._message(stranger, "розмір не підійшов, хочу обмін на XL")

        case = open_post_sale_case(stranger, message)

        self.assertIsNotNone(case)
        self.assertEqual(case.case_type, IgPostSaleCase.CaseType.EXCHANGE)
        self.assertEqual(case.status, IgPostSaleCase.Status.NEEDS_DETAILS)

    def test_received_evidence_beats_a_hypothetical_wording(self):
        from management.services.ig_post_sale import open_post_sale_case

        buyer = self._buyer("terminal-hypothetical-but-received")
        message = self._message(buyer, "а можна поміняти, бо не підійшов розмір")

        self.assertIsNotNone(open_post_sale_case(buyer, message))

    def test_buyer_exchange_request_still_creates_a_case(self):
        from management.services.ig_post_sale import open_post_sale_case

        buyer = self._buyer("terminal-buyer-creates")
        message = self._message(buyer, "розмір не підійшов, хочу обмін на XL")

        case = open_post_sale_case(buyer, message)

        self.assertIsNotNone(case)
        self.assertEqual(case.case_type, IgPostSaleCase.CaseType.EXCHANGE)


class DisplayedInteractionTypeTests(TerminalFactsMixin, TestCase):
    """F-SCORE-008 у практичній формі: накладати факт, а не шукати інший снапшот."""

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "displayed-type-manager", password="x", is_staff=True
        )

    def test_open_exchange_case_overrides_a_stale_snapshot_type(self):
        from management.bot_views import _display_interaction_type

        buyer = self._buyer("displayed-open-exchange")
        self._case(buyer, status=IgPostSaleCase.Status.IN_TRANSIT)

        self.assertEqual(
            _display_interaction_type(buyer, Types.INFORMATION_ONLY),
            Types.EXCHANGE_REQUEST,
        )

    def test_open_return_case_shows_a_return_request(self):
        from management.bot_views import _display_interaction_type

        buyer = self._buyer("displayed-open-return")
        self._case(
            buyer,
            status=IgPostSaleCase.Status.OPEN,
            case_type=IgPostSaleCase.CaseType.RETURN,
        )

        self.assertEqual(
            _display_interaction_type(buyer, Types.COMMUNITY_CASUAL),
            Types.RETURN_REQUEST,
        )

    def test_completed_case_does_not_override_the_snapshot(self):
        from management.bot_views import _display_interaction_type

        buyer = self._buyer("displayed-completed")
        self._case(buyer, status=IgPostSaleCase.Status.COMPLETED)

        self.assertEqual(
            _display_interaction_type(buyer, Types.PAID_ORDER_WAITING),
            Types.PAID_ORDER_WAITING,
        )

    def test_real_complaint_is_not_masked_by_an_open_case(self):
        """Скарга під час обміну — окремий факт, її не можна ховати."""
        from management.bot_views import _display_interaction_type

        buyer = self._buyer("displayed-complaint-during-case")
        self._case(buyer, status=IgPostSaleCase.Status.IN_TRANSIT)

        self.assertEqual(
            _display_interaction_type(buyer, Types.SUPPORT_COMPLAINT),
            Types.SUPPORT_COMPLAINT,
        )

    def test_client_without_a_case_keeps_the_snapshot_type(self):
        from management.bot_views import _display_interaction_type

        stranger = IgClient.get_or_create_for_sender("displayed-no-case")

        self.assertEqual(
            _display_interaction_type(stranger, Types.PRODUCT_INTEREST),
            Types.PRODUCT_INTEREST,
        )


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class PostSaleBadgeLifecycleTests(TerminalFactsMixin, TestCase):
    """Скарга заказчика: бейдж обміну світиться завжди, навіть після закриття."""

    def setUp(self):
        from django.test import Client as DjangoClient

        self.manager = get_user_model().objects.create_user(
            "badge-lifecycle-manager", password="x", is_staff=True, is_superuser=True
        )
        self.http = DjangoClient()
        self.http.force_login(self.manager)

    def _row(self, client):
        data = self.http.get(reverse("management_bot_clients_api")).json()
        return next(row for row in data["clients"] if row["id"] == client.pk)

    def test_completed_case_clears_the_badge(self):
        buyer = self._buyer("badge-completed")
        self._case(buyer, status=IgPostSaleCase.Status.COMPLETED)

        row = self._row(buyer)

        self.assertEqual(row["post_sale_type"], "")
        self.assertEqual(row["post_sale_type_label"], "")

    def test_cancelled_case_clears_the_badge(self):
        buyer = self._buyer("badge-cancelled")
        self._case(buyer, status=IgPostSaleCase.Status.CANCELLED)

        self.assertEqual(self._row(buyer)["post_sale_type_label"], "")

    def test_in_transit_case_keeps_the_badge_and_exposes_the_status(self):
        buyer = self._buyer("badge-in-transit")
        self._case(buyer, status=IgPostSaleCase.Status.IN_TRANSIT)

        row = self._row(buyer)

        self.assertEqual(row["post_sale_type"], "exchange")
        self.assertEqual(row["post_sale_type_label"], "Обмін")
        self.assertEqual(row["post_sale_status_label"], "У дорозі")

    def test_in_transit_case_is_not_a_pending_manager_action(self):
        """«У дорозі» не вимагає дії менеджера — тому й не мусить пульсувати."""
        buyer = self._buyer("badge-in-transit-action")
        self._case(buyer, status=IgPostSaleCase.Status.IN_TRANSIT)

        self.assertFalse(self._row(buyer)["post_sale_needs_action"])

    def test_open_case_is_a_pending_manager_action(self):
        buyer = self._buyer("badge-open-action")
        self._case(buyer, status=IgPostSaleCase.Status.OPEN)

        self.assertTrue(self._row(buyer)["post_sale_needs_action"])

    def test_badge_shows_type_and_status_together_in_the_template(self):
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
            "post_sale_badge_label" in template,
            "рядок клієнта мусить показувати тип разом зі статусом обміну",
        )
