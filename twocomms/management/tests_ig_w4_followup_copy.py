"""W4 regression tests for follow-up copy and the checkout-offer cascade."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgCheckoutProposal,
    IgClient,
    IgDeal,
    IgFollowUpTask,
    InstagramBotSettings,
)
from management.services import bot_followups
from management.services.instagram_bot import ProviderDeliveryReceipt


KYIV = ZoneInfo("Europe/Kyiv")


class FollowupCopyTests(TestCase):
    def setUp(self):
        self.client_record = IgClient.get_or_create_for_sender("w4-followup-copy")
        self.client_record.stage = IgClient.Stage.CHECKOUT
        self.client_record.last_message_at = datetime(2026, 8, 3, 15, 0, tzinfo=KYIV)
        self.client_record.save(
            update_fields=["stage", "last_message_at", "updated_at"]
        )

    def _task(self, *, kind, language="uk", discount=0, deal=None, level=0):
        self.client_record.language = language
        self.client_record.save(update_fields=["language", "updated_at"])
        return IgFollowUpTask.objects.create(
            client=self.client_record,
            deal=deal,
            due_at=self.client_record.last_message_at,
            kind=kind,
            discount_percent=discount,
            level=level,
        )

    def test_thinking_copy_has_no_male_voice_and_offers_a_clear_exit(self):
        expected = {
            "uk": ("що зупинило", "більше не писатиму", "хотів"),
            "ru": ("что остановило", "больше не буду писать", "хотел"),
            "en": ("what is holding you back", "will not message again", "had a chance"),
        }
        for locale, (question, exit_copy, forbidden) in expected.items():
            with self.subTest(locale=locale):
                task = self._task(kind=IgFollowUpTask.Kind.THINKING, language=locale)
                text = bot_followups.compose_followup(task).lower()
                self.assertIn(question, text)
                self.assertIn(exit_copy, text)
                self.assertNotIn(forbidden, text)

    def test_qualification_copy_asks_for_a_closed_yes_or_no_choice(self):
        task = self._task(kind=IgFollowUpTask.Kind.QUALIFICATION)

        text = bot_followups.compose_followup(task).lower()

        self.assertIn("за 2 хвилини", text)
        self.assertIn("напишіть «ні»", text)
        self.assertIn("закрию питання", text)

    def test_five_percent_copy_uses_exact_deal_amounts_when_available(self):
        deal = IgDeal.objects.create(
            client=self.client_record,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("1000.00"),
        )
        task = self._task(
            kind=IgFollowUpTask.Kind.RESCUE,
            discount=5,
            deal=deal,
        )

        text = bot_followups.compose_followup(task)

        self.assertIn("950 грн", text)
        self.assertIn("1000", text)

    def test_payment_copy_never_guesses_unknown_invoice_state(self):
        deal = IgDeal.objects.create(
            client=self.client_record,
            status=IgDeal.Status.AWAITING_PAYMENT,
            invoice_id="legacy-without-ttl",
            invoice_url="https://pay.example/legacy",
            amount=Decimal("1000.00"),
        )
        task = self._task(kind=IgFollowUpTask.Kind.PAYMENT, deal=deal)

        text = bot_followups.compose_followup(task).lower()

        self.assertNotIn("ще активне", text)
        self.assertNotIn("вже неактивне", text)
        self.assertIn("перевірю", text)


class CheckoutOfferCascadeTests(TestCase):
    def setUp(self):
        current = timezone.now().astimezone(KYIV)
        self.now = current.replace(hour=15, minute=0, second=0, microsecond=0)
        if self.now <= current:
            self.now += timedelta(days=1)
        settings = InstagramBotSettings.load()
        settings.is_enabled = True
        settings.save(update_fields=["is_enabled", "updated_at"])
        self.client_record = IgClient.get_or_create_for_sender("w4-offer-cascade")
        self.client_record.stage = IgClient.Stage.CHECKOUT
        self.client_record.language = "uk"
        self.client_record.last_message_at = self.now
        self.client_record.save(
            update_fields=["stage", "language", "last_message_at", "updated_at"]
        )
        self.deal = IgDeal.objects.create(
            client=self.client_record,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("1000.00"),
            requested_payment_amount=Decimal("1000.00"),
        )
        self.proposal = IgCheckoutProposal.objects.create_current(
            deal=self.deal,
            catalog_total=Decimal("1000.00"),
            quoted_total=Decimal("1000.00"),
            requested_payment_amount=Decimal("1000.00"),
            items_digest="a" * 64,
            expires_at=self.now + timedelta(minutes=25),
        )
        self.deal.refresh_from_db()

    def test_offer_schedules_payment_followup_at_observable_expiry(self):
        with patch("management.services.bot_followups._now", return_value=self.now):
            task = bot_followups.schedule_after_bot_reply(
                self.client_record,
                reply="Персональна пропозиція готова",
                deal=self.deal,
            )

        self.assertEqual(task.kind, IgFollowUpTask.Kind.PAYMENT)
        self.assertEqual(task.reason, "checkout_proposal_abandoned")
        self.assertEqual(task.deal_id, self.deal.id)
        self.assertEqual(task.due_at, self.proposal.expires_at)

    def test_expired_offer_copy_says_it_can_be_reissued_not_that_it_is_live(self):
        task = IgFollowUpTask.objects.create(
            client=self.client_record,
            deal=self.deal,
            due_at=self.proposal.expires_at,
            kind=IgFollowUpTask.Kind.PAYMENT,
            reason="checkout_proposal_abandoned",
        )

        text = bot_followups.compose_followup(
            task,
            now=self.proposal.expires_at + timedelta(seconds=1),
        ).lower()

        self.assertIn("вже неактивна", text)
        self.assertIn("зроблю нову", text)
        self.assertNotIn("ще активна", text)

    @patch(
        "management.services.instagram_bot.send_text",
        return_value=ProviderDeliveryReceipt(True, "", "", "w4-cascade"),
    )
    def test_first_touch_schedules_a_safe_second_cascade_step(self, _send_text):
        first_send_at = self.proposal.expires_at
        first = IgFollowUpTask.objects.create(
            client=self.client_record,
            deal=self.deal,
            due_at=first_send_at,
            kind=IgFollowUpTask.Kind.PAYMENT,
            reason="checkout_proposal_abandoned",
            level=0,
            meta_window_deadline=self.client_record.last_message_at + timedelta(hours=23),
        )

        sent = bot_followups.process_due_followups(
            InstagramBotSettings.load(),
            now=first_send_at,
            limit=1,
        )

        first.refresh_from_db()
        self.assertEqual(
            sent,
            1,
            f"status={first.status} skip={first.skip_reason} error={first.last_error}",
        )
        self.assertEqual(first.status, IgFollowUpTask.Status.SENT)
        second = IgFollowUpTask.objects.get(
            client=self.client_record,
            status=IgFollowUpTask.Status.PENDING,
            reason="checkout_proposal_abandoned",
            level=1,
        )
        self.assertEqual(second.kind, IgFollowUpTask.Kind.PAYMENT)
        self.assertGreaterEqual(second.due_at - first.sent_at, timedelta(hours=18))

    @patch("management.services.instagram_bot.send_text")
    def test_manager_tasks_remain_pending_and_are_never_auto_sent(self, send_text):
        manager_task = IgFollowUpTask.objects.create(
            client=self.client_record,
            deal=self.deal,
            due_at=self.now,
            kind=IgFollowUpTask.Kind.MANAGER_TASK,
            reason="payment_abandoned_manager_review",
        )

        bot_followups.process_due_followups(
            InstagramBotSettings.load(),
            now=self.now,
            limit=1,
        )

        manager_task.refresh_from_db()
        self.assertEqual(manager_task.status, IgFollowUpTask.Status.PENDING)
        send_text.assert_not_called()
