"""IMP-053: follow-up cascades are data, not an if/elif side effect."""

from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase

from management.models import (
    IgBotNotification,
    IgClient,
    IgDeal,
    IgFollowUpTask,
    IgPaymentProjection,
    InstagramBotSettings,
)


KYIV = ZoneInfo("Europe/Kyiv")


class FollowupPolicyTableTests(TestCase):
    def test_paid_delivery_steps_use_a_dedicated_fulfillment_kind(self):
        from management.services.bot_followups import (
            FOLLOWUP_POLICIES,
            _persisted_step_kind,
        )

        kind_values = {value for value, _label in IgFollowUpTask.Kind.choices}
        self.assertIn("fulfillment", kind_values)
        self.assertEqual(
            [
                _persisted_step_kind(step)
                for step in FOLLOWUP_POLICIES["paid_missing_delivery"].steps
            ],
            ["fulfillment", "fulfillment", "fulfillment"],
        )

    def test_all_nine_designed_scenarios_have_explicit_steps_and_terminals(self):
        from management.services.bot_followups import FOLLOWUP_POLICIES

        self.assertEqual(
            set(FOLLOWUP_POLICIES),
            {
                "payment_link_unpaid",
                "price_quoted_silence",
                "thinking_hesitation",
                "price_objection",
                "missing_customer_size",
                "restock_wait",
                "paid_missing_delivery",
                "delivery_ready_unpaid",
                "first_reply_silence",
            },
        )
        for key, policy in FOLLOWUP_POLICIES.items():
            with self.subTest(policy=key):
                self.assertTrue(policy.steps)
                self.assertTrue(policy.terminal_conditions)
                self.assertEqual(
                    [step.index for step in policy.steps],
                    list(range(len(policy.steps))),
                )
                for step in policy.steps:
                    self.assertIn(step.trigger, {"time", "event", "reactive"})
                    self.assertTrue(step.condition)
                    self.assertTrue(step.copy_key)

    def test_policy_offsets_match_the_approved_funnel_design(self):
        from management.services.bot_followups import FOLLOWUP_POLICIES

        expected = {
            "payment_link_unpaid": [
                timedelta(minutes=25),
                timedelta(hours=4),
                timedelta(hours=23),
                None,
                timedelta(hours=72),
            ],
            "price_quoted_silence": [
                timedelta(hours=2),
                timedelta(hours=24),
                timedelta(hours=72),
            ],
            "thinking_hesitation": [
                timedelta(hours=20),
                timedelta(hours=72),
                timedelta(days=7),
            ],
            "price_objection": [timedelta(hours=24), timedelta(hours=96)],
            "missing_customer_size": [
                timedelta(minutes=40),
                timedelta(hours=6),
                timedelta(hours=36),
            ],
            "restock_wait": [timedelta(0), None, timedelta(days=14)],
            "paid_missing_delivery": [
                timedelta(minutes=20),
                timedelta(hours=3),
                timedelta(hours=20),
            ],
            "delivery_ready_unpaid": [timedelta(minutes=30)],
            "first_reply_silence": [timedelta(hours=2), timedelta(hours=20)],
        }
        self.assertEqual(
            {
                key: [step.offset for step in policy.steps]
                for key, policy in FOLLOWUP_POLICIES.items()
            },
            expected,
        )


class FollowupPolicyResolutionTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 3, 10, 0, tzinfo=KYIV)
        self.client_record = IgClient.get_or_create_for_sender("policy-client")
        self.client_record.last_message_at = self.now
        self.client_record.save(update_fields=["last_message_at", "updated_at"])

    def _deal(self, **overrides):
        values = {
            "client": self.client_record,
            "status": IgDeal.Status.QUOTED,
        }
        values.update(overrides)
        return IgDeal.objects.create(**values)

    def test_resolver_uses_commerce_facts_before_generic_stage(self):
        from management.services.bot_followups import resolve_followup_scenario

        deal = self._deal(status=IgDeal.Status.AWAITING_PAYMENT)
        self.client_record.stage = IgClient.Stage.CHECKOUT
        self.client_record.primary_objection = IgClient.Objection.PRICE
        self.client_record.save(
            update_fields=["stage", "primary_objection", "updated_at"]
        )

        self.assertEqual(
            resolve_followup_scenario(self.client_record, deal=deal),
            "payment_link_unpaid",
        )

    def test_resolver_separates_price_thinking_size_and_first_reply(self):
        from management.services.bot_followups import resolve_followup_scenario

        cases = (
            (IgClient.Stage.CHECKOUT, IgClient.Objection.PRICE, "", "price_objection"),
            (IgClient.Stage.CHECKOUT, IgClient.Objection.THINKING, "", "thinking_hesitation"),
            (IgClient.Stage.PRODUCT_MATCHED, IgClient.Objection.NONE, "", "missing_customer_size"),
            (IgClient.Stage.NEW, IgClient.Objection.NONE, "", "first_reply_silence"),
        )
        for stage, objection, size, expected in cases:
            with self.subTest(expected=expected):
                self.client_record.stage = stage
                self.client_record.primary_objection = objection
                self.client_record.current_size = size
                self.client_record.save(
                    update_fields=["stage", "primary_objection", "current_size", "updated_at"]
                )
                self.assertEqual(
                    resolve_followup_scenario(self.client_record),
                    expected,
                )

    def test_resolver_distinguishes_paid_missing_delivery_from_ready_unpaid(self):
        from management.services.bot_followups import resolve_followup_scenario

        paid = self._deal(status=IgDeal.Status.PAID)
        self.assertEqual(
            resolve_followup_scenario(self.client_record, deal=paid),
            "paid_missing_delivery",
        )

        unpaid_ready = self._deal(
            status=IgDeal.Status.QUOTED,
            np_full_name="Олена Тест",
            np_phone="+380500000000",
            np_city="Київ",
            np_office="1",
        )
        self.assertEqual(
            resolve_followup_scenario(self.client_record, deal=unpaid_ready),
            "delivery_ready_unpaid",
        )

    def test_next_step_comes_from_the_same_policy(self):
        from management.services.bot_followups import _schedule_next_policy_step

        sent = IgFollowUpTask.objects.create(
            client=self.client_record,
            due_at=self.now,
            status=IgFollowUpTask.Status.SENT,
            sent_at=self.now,
            kind=IgFollowUpTask.Kind.THINKING,
            reason="thinking_hesitation",
            level=0,
        )

        self.assertTrue(
            _schedule_next_policy_step(sent, self.client_record, now=self.now)
        )
        nxt = IgFollowUpTask.objects.get(
            client=self.client_record,
            status=IgFollowUpTask.Status.PENDING,
        )
        self.assertEqual(nxt.reason, "thinking_hesitation")
        self.assertEqual(nxt.level, 1)
        self.assertEqual(nxt.due_at, self.now + timedelta(hours=52))

    def test_terminal_step_records_reason_and_moves_client_to_cold_via_fsm(self):
        from management.services.bot_followups import _complete_policy_after_send

        terminal = IgFollowUpTask.objects.create(
            client=self.client_record,
            due_at=self.now,
            status=IgFollowUpTask.Status.SENT,
            sent_at=self.now,
            kind=IgFollowUpTask.Kind.THINKING,
            reason="thinking_hesitation",
            level=2,
        )

        self.assertTrue(_complete_policy_after_send(terminal, self.client_record))
        self.client_record.refresh_from_db()
        self.assertEqual(self.client_record.lost_reason, "thinking_exhausted")
        self.assertEqual(self.client_record.stage, IgClient.Stage.COLD)


class FollowupPolicyIntegrationTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 3, 10, 0, tzinfo=KYIV)
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.save(update_fields=["is_enabled", "updated_at"])
        self.client_record = IgClient.get_or_create_for_sender("policy-integration")
        self.client_record.last_message_at = self.now
        self.client_record.language = "uk"
        self.client_record.save(
            update_fields=["last_message_at", "language", "updated_at"]
        )

    def _paid_missing_delivery_deal(self):
        deal = IgDeal.objects.create(
            client=self.client_record,
            status=IgDeal.Status.PAID,
            payment_status="paid",
            paid_at=self.now,
        )
        IgPaymentProjection.objects.create(
            client=self.client_record,
            deal=deal,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount="1090.00",
            paid_at=self.now,
        )
        return deal

    def test_fulfillment_guard_allows_verified_buyer_but_sales_followup_does_not(self):
        from management.services.bot_followups import _client_allows_followup

        deal = self._paid_missing_delivery_deal()

        allowed, reason = _client_allows_followup(
            self.client_record,
            deal=deal,
            kind="fulfillment",
        )
        sales_allowed, sales_reason = _client_allows_followup(
            self.client_record,
            deal=deal,
            kind=IgFollowUpTask.Kind.PAYMENT,
        )

        self.assertTrue(allowed, reason)
        self.assertFalse(sales_allowed)
        self.assertEqual(sales_reason, "already_converted")

    def test_fulfillment_bypasses_sales_frequency_limit(self):
        from management.services.bot_followups import _client_allows_followup

        deal = self._paid_missing_delivery_deal()
        IgFollowUpTask.objects.create(
            client=self.client_record,
            due_at=self.now - timedelta(hours=1),
            sent_at=self.now - timedelta(hours=1),
            status=IgFollowUpTask.Status.SENT,
            kind=IgFollowUpTask.Kind.QUALIFICATION,
        )

        allowed, reason = _client_allows_followup(
            self.client_record,
            deal=deal,
            kind="fulfillment",
        )

        self.assertTrue(allowed, reason)

    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    def test_fulfillment_g1_schedules_g2_without_mutating_sales_counters(self, _send_text):
        from management.services.bot_followups import process_due_followups

        deal = self._paid_missing_delivery_deal()
        self.client_record.followup_level = 4
        self.client_record.discount_offered_percent = 5
        self.client_record.save(
            update_fields=["followup_level", "discount_offered_percent", "updated_at"]
        )
        first = IgFollowUpTask.objects.create(
            client=self.client_record,
            deal=deal,
            due_at=self.now,
            status=IgFollowUpTask.Status.PENDING,
            kind="fulfillment",
            reason="paid_missing_delivery",
            level=0,
            meta_window_deadline=self.now + timedelta(hours=23),
        )

        self.assertEqual(
            process_due_followups(self.settings, now=self.now, limit=1),
            1,
        )

        first.refresh_from_db()
        self.client_record.refresh_from_db()
        second = IgFollowUpTask.objects.get(
            client=self.client_record,
            status=IgFollowUpTask.Status.PENDING,
            reason="paid_missing_delivery",
            level=1,
        )
        self.assertEqual(first.status, IgFollowUpTask.Status.SENT)
        self.assertEqual(second.kind, "fulfillment")
        self.assertEqual(second.due_at, self.now + timedelta(hours=2, minutes=40))
        self.assertEqual(self.client_record.followup_level, 4)
        self.assertEqual(self.client_record.discount_offered_percent, 5)

    @patch("management.services.instagram_bot.send_text")
    def test_fulfillment_is_skipped_when_delivery_becomes_complete(self, send_text):
        from management.services.bot_followups import process_due_followups

        deal = self._paid_missing_delivery_deal()
        task = IgFollowUpTask.objects.create(
            client=self.client_record,
            deal=deal,
            due_at=self.now,
            status=IgFollowUpTask.Status.PENDING,
            kind="fulfillment",
            reason="paid_missing_delivery",
            level=1,
            meta_window_deadline=self.now + timedelta(hours=23),
        )
        deal.np_full_name = "Олена Тест"
        deal.np_phone = "+380500000000"
        deal.np_city = "Київ"
        deal.np_office = "1"
        deal.save(
            update_fields=["np_full_name", "np_phone", "np_city", "np_office", "updated_at"]
        )

        self.assertEqual(
            process_due_followups(self.settings, now=self.now, limit=1),
            0,
        )

        task.refresh_from_db()
        self.assertEqual(task.status, IgFollowUpTask.Status.SKIPPED)
        self.assertEqual(task.skip_reason, "policy_condition_changed")
        send_text.assert_not_called()

    @patch("management.services.instagram_bot._deliver_manager_notification", return_value=True)
    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    def test_fulfillment_g3_persists_idempotent_manager_escalation(
        self,
        _send_text,
        _deliver_notification,
    ):
        from management.services.bot_followups import process_due_followups

        deal = self._paid_missing_delivery_deal()
        IgFollowUpTask.objects.create(
            client=self.client_record,
            deal=deal,
            due_at=self.now,
            status=IgFollowUpTask.Status.PENDING,
            kind="fulfillment",
            reason="paid_missing_delivery",
            level=2,
            meta_window_deadline=self.now + timedelta(hours=23),
        )

        self.assertEqual(
            process_due_followups(self.settings, now=self.now, limit=1),
            1,
        )

        notification = IgBotNotification.objects.get(
            dedupe_key=f"fulfillment_missing_delivery:{deal.pk}:g3"
        )
        self.assertEqual(notification.event_type, "fulfillment_missing_delivery")
        self.assertEqual(notification.client_id, self.client_record.pk)
        self.assertIn(
            f"/bot/?client={self.client_record.pk}",
            str(notification.payload.get("text") or ""),
        )

    def test_schedule_after_reply_selects_payment_policy_from_deal_truth(self):
        from management.services.bot_followups import schedule_after_bot_reply

        deal = IgDeal.objects.create(
            client=self.client_record,
            status=IgDeal.Status.AWAITING_PAYMENT,
        )

        with patch("management.services.bot_followups._now", return_value=self.now):
            task = schedule_after_bot_reply(self.client_record, deal=deal)

        self.assertIsNotNone(task)
        self.assertEqual(task.reason, "payment_link_unpaid")
        self.assertEqual(task.level, 0)
        self.assertEqual(task.due_at, self.now + timedelta(minutes=25))

    def test_schedule_after_reply_uses_missing_size_policy(self):
        from management.services.bot_followups import schedule_after_bot_reply

        self.client_record.stage = IgClient.Stage.PRODUCT_MATCHED
        self.client_record.current_size = ""
        self.client_record.save(
            update_fields=["stage", "current_size", "updated_at"]
        )

        with patch("management.services.bot_followups._now", return_value=self.now):
            task = schedule_after_bot_reply(self.client_record)

        self.assertIsNotNone(task)
        self.assertEqual(task.reason, "missing_customer_size")
        self.assertEqual(task.level, 0)
        self.assertEqual(task.due_at, self.now + timedelta(minutes=40))

    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    def test_sent_policy_step_schedules_the_next_step_without_spam(self, _send_text):
        from management.services.bot_followups import process_due_followups

        first = IgFollowUpTask.objects.create(
            client=self.client_record,
            due_at=self.now,
            status=IgFollowUpTask.Status.PENDING,
            kind=IgFollowUpTask.Kind.QUALIFICATION,
            reason="first_reply_silence",
            level=0,
            meta_window_deadline=self.now + timedelta(hours=23),
        )

        self.assertEqual(
            process_due_followups(self.settings, now=self.now, limit=1),
            1,
        )

        first.refresh_from_db()
        self.assertEqual(first.status, IgFollowUpTask.Status.SENT)
        second = IgFollowUpTask.objects.get(
            client=self.client_record,
            status=IgFollowUpTask.Status.PENDING,
            reason="first_reply_silence",
            level=1,
        )
        self.assertGreaterEqual(second.due_at - first.sent_at, timedelta(hours=18))
        self.assertLessEqual(second.due_at, first.meta_window_deadline)

    @patch("management.services.instagram_bot.send_text")
    def test_changed_policy_condition_skips_send(self, send_text):
        from management.services.bot_followups import process_due_followups

        task = IgFollowUpTask.objects.create(
            client=self.client_record,
            due_at=self.now,
            status=IgFollowUpTask.Status.PENDING,
            kind=IgFollowUpTask.Kind.QUALIFICATION,
            reason="missing_customer_size",
            level=0,
            meta_window_deadline=self.now + timedelta(hours=23),
        )
        self.client_record.current_size = "M"
        self.client_record.save(update_fields=["current_size", "updated_at"])

        self.assertEqual(
            process_due_followups(self.settings, now=self.now, limit=1),
            0,
        )

        task.refresh_from_db()
        self.assertEqual(task.status, IgFollowUpTask.Status.SKIPPED)
        self.assertEqual(task.skip_reason, "policy_condition_changed")
        send_text.assert_not_called()

    def test_copy_key_selects_scenario_specific_size_copy(self):
        from management.services.bot_followups import compose_followup

        task = IgFollowUpTask.objects.create(
            client=self.client_record,
            due_at=self.now,
            kind=IgFollowUpTask.Kind.QUALIFICATION,
            reason="missing_customer_size",
            level=0,
        )

        text = compose_followup(task).lower()

        self.assertIn("зріст і вагу", text)
        self.assertIn("мірки", text)

    def test_policy_copy_follows_ru_and_en_client_language(self):
        from management.services.bot_followups import compose_followup

        task = IgFollowUpTask.objects.create(
            client=self.client_record,
            due_at=self.now,
            kind=IgFollowUpTask.Kind.QUALIFICATION,
            reason="missing_customer_size",
            level=0,
        )
        expected = {
            "ru": ("рост и вес", "замеры"),
            "en": ("height and weight", "measurements"),
        }
        for language, fragments in expected.items():
            with self.subTest(language=language):
                self.client_record.language = language
                self.client_record.save(update_fields=["language", "updated_at"])
                task.client = self.client_record
                text = compose_followup(task).lower()
                for fragment in fragments:
                    self.assertIn(fragment, text)

    def test_out_of_window_policy_step_keeps_reason_and_prepared_copy(self):
        from management.services.bot_followups import _schedule_next_policy_step

        sent = IgFollowUpTask.objects.create(
            client=self.client_record,
            due_at=self.now,
            status=IgFollowUpTask.Status.SENT,
            sent_at=self.now,
            kind=IgFollowUpTask.Kind.THINKING,
            reason="thinking_hesitation",
            level=0,
        )

        self.assertTrue(
            _schedule_next_policy_step(sent, self.client_record, now=self.now)
        )

        manager_task = IgFollowUpTask.objects.get(
            client=self.client_record,
            status=IgFollowUpTask.Status.PENDING,
        )
        self.assertEqual(manager_task.kind, IgFollowUpTask.Kind.MANAGER_TASK)
        self.assertEqual(manager_task.reason, "thinking_hesitation")
        self.assertEqual(manager_task.skip_reason, "meta_window_closed")
        self.assertTrue(manager_task.message_text.strip())

    def test_delivery_ready_policy_continues_with_payment_step_a2(self):
        from management.services.bot_followups import _schedule_next_policy_step

        deal = IgDeal.objects.create(
            client=self.client_record,
            status=IgDeal.Status.QUOTED,
            np_full_name="Олена Тест",
            np_phone="+380500000000",
            np_city="Київ",
            np_office="1",
        )
        sent = IgFollowUpTask.objects.create(
            client=self.client_record,
            deal=deal,
            due_at=self.now,
            status=IgFollowUpTask.Status.SENT,
            sent_at=self.now,
            kind=IgFollowUpTask.Kind.PAYMENT,
            reason="delivery_ready_unpaid",
            level=0,
        )

        self.assertTrue(
            _schedule_next_policy_step(sent, self.client_record, now=self.now)
        )

        nxt = IgFollowUpTask.objects.get(
            client=self.client_record,
            status=IgFollowUpTask.Status.PENDING,
        )
        self.assertEqual(nxt.reason, "payment_link_unpaid")
        self.assertEqual(nxt.level, 1)
        self.assertGreaterEqual(nxt.due_at - self.now, timedelta(hours=18))
