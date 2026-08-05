from contextlib import nullcontext
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from management.models import (
    GeminiKeyState,
    IgBotNotification,
    IgClient,
    IgConversationAnalysisJob,
    IgConversationAnalysisSnapshot,
    IgDeal,
    IgFollowUpTask,
    IgPaymentProjection,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import bot_conversation_analysis, bot_followups, bot_sales_classifier
from management.services import call_ai_analysis
from management.services import gemini_keys, instagram_bot
from orders.models import Order


class GeminiFailureRoutingTests(TestCase):
    def test_transient_live_pool_summaries_are_provider_outages(self):
        for marker in ("read_timeout", "transport", "quota_429", "http_408", "http_5xx"):
            with self.subTest(marker=marker):
                error = call_ai_analysis.CallAIAnalysisError(
                    f"Усі Gemini-кандидати для live chat недоступні. Спроби: {marker}"
                )
                self.assertEqual(
                    instagram_bot._gemini_failure_kind(error),
                    "provider_outage",
                )

    def test_payload_or_safety_failures_are_not_provider_outages(self):
        error = call_ai_analysis.CallAIAnalysisError(
            "Помилка запиту до Gemini: malformed request payload"
        )

        self.assertEqual(
            instagram_bot._gemini_failure_kind(error),
            "generation_error",
        )


class LiveReplyLanguageTests(TestCase):
    def test_english_message_is_detected_as_english(self):
        self.assertEqual(
            bot_sales_classifier.detect_language(
                "Greetings, I wanted to check the status of my order"
            ),
            "en",
        )

    def test_catalog_token_does_not_turn_existing_ukrainian_client_english(self):
        client = IgClient.get_or_create_for_sender("catalog-token-language")
        client.language = "uk"
        client.save(update_fields=["language", "updated_at"])
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="XL",
        )

        bot_sales_classifier.classify_message(client, message=message)

        client.refresh_from_db()
        self.assertEqual(client.language, "uk")

    def test_single_english_catalog_word_does_not_override_client_language(self):
        client = IgClient.get_or_create_for_sender("single-catalog-word-language")
        client.language = "uk"
        client.save(update_fields=["language", "updated_at"])
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="shirt",
        )

        bot_sales_classifier.classify_message(client, message=message)

        client.refresh_from_db()
        self.assertEqual(client.language, "uk")

    def test_catalog_url_does_not_turn_existing_ukrainian_client_english(self):
        client = IgClient.get_or_create_for_sender("catalog-url-language")
        client.language = "uk"
        client.save(update_fields=["language", "updated_at"])
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="https://twocomms.shop/catalog/t-shirts",
        )

        bot_sales_classifier.classify_message(client, message=message)

        client.refresh_from_db()
        self.assertEqual(client.language, "uk")

    def test_latin_transliteration_does_not_override_existing_ukrainian_language(self):
        client = IgClient.get_or_create_for_sender("transliteration-language")
        client.language = "uk"
        client.save(update_fields=["language", "updated_at"])
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Dobryi den, khochu futbolku",
        )

        bot_sales_classifier.classify_message(client, message=message)

        client.refresh_from_db()
        self.assertEqual(client.language, "uk")

    def test_english_order_question_uses_order_reasoning(self):
        task = instagram_bot.select_chat_reasoning_task(
            [{"role": "user", "text": "What is the status of order TWC28072026N01?"}]
        )

        self.assertEqual(task, "order_decision")

    def test_english_order_question_updates_crm_order_status_intent(self):
        client = IgClient.get_or_create_for_sender("english-order-status-intent")
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="What is the status of order TWC28072026N01?",
        )

        bot_sales_classifier.classify_message(client, message=message)

        client.refresh_from_db()
        self.assertEqual(client.intent, IgClient.Intent.ORDER_STATUS)

    def test_english_collaboration_is_not_spam(self):
        client = IgClient.get_or_create_for_sender("english-collaboration")
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Hello, I would like to discuss a partnership and collaboration.",
        )

        result = bot_sales_classifier.classify_message(client, message=message)

        client.refresh_from_db()
        self.assertEqual(client.language, "en")
        self.assertEqual(result["interaction_type"], "collaboration")
        self.assertNotEqual(client.stage, IgClient.Stage.SPAM)

    def test_refund_with_order_reference_is_support_not_order_status(self):
        client = IgClient.get_or_create_for_sender("english-refund-intent")
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Please refund order TWC28072026N01",
        )

        result = bot_sales_classifier.classify_message(client, message=message)

        client.refresh_from_db()
        self.assertEqual(client.intent, IgClient.Intent.SUPPORT)
        self.assertEqual(result["interaction_type"], "support_complaint")

    def test_payment_with_order_reference_is_payment_not_order_status(self):
        client = IgClient.get_or_create_for_sender("english-payment-intent")
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Payment for TWC28072026N01 is complete",
        )

        bot_sales_classifier.classify_message(client, message=message)

        client.refresh_from_db()
        self.assertEqual(client.intent, IgClient.Intent.PAYMENT)

    def test_english_client_receives_english_followup_copy(self):
        client = IgClient.get_or_create_for_sender("english-followup-language")
        client.language = "en"
        client.save(update_fields=["language", "updated_at"])
        task = IgFollowUpTask.objects.create(
            client=client,
            due_at=timezone.now(),
            kind=IgFollowUpTask.Kind.QUALIFICATION,
            reason="language-test",
        )

        reply = bot_followups.compose_followup(task)

        self.assertEqual(bot_sales_classifier.detect_language(reply), "en")
        self.assertIn("order", reply.lower())


class LiveReplyKeyPriorityTests(TestCase):
    def test_reply_worker_prioritizes_the_most_recent_active_conversation(self):
        now = timezone.now()
        older_client = IgClient.get_or_create_for_sender("older-live-conversation")
        newer_client = IgClient.get_or_create_for_sender("newer-live-conversation")
        older_client.last_message_at = now - timedelta(hours=1)
        newer_client.last_message_at = now
        older_client.save(update_fields=["last_message_at", "updated_at"])
        newer_client.save(update_fields=["last_message_at", "updated_at"])
        older = InstagramBotMessage.objects.create(
            sender_id=older_client.igsid,
            client=older_client,
            role=InstagramBotMessage.Role.USER,
            text="older pending",
            status=InstagramBotMessage.Status.PENDING,
            provider_created_at=now - timedelta(hours=1),
        )
        newer = InstagramBotMessage.objects.create(
            sender_id=newer_client.igsid,
            client=newer_client,
            role=InstagramBotMessage.Role.USER,
            text="newer pending",
            status=InstagramBotMessage.Status.PENDING,
            provider_created_at=now,
        )
        self.assertLess(older.pk, newer.pk)

        claimed = instagram_bot._claim_next()

        self.assertEqual(claimed.pk, newer.pk)

    def test_background_roles_cannot_borrow_reserved_chat_keys(self):
        pools = gemini_keys.DEFAULT_ROLE_KEY_POOLS

        self.assertEqual(pools["chat"]["own"], ["GEMINI_API", "GEMINI_API2"])
        for role in ("management", "checker"):
            available = set(pools[role]["own"] + pools[role]["borrow"])
            self.assertTrue({"GEMINI_API", "GEMINI_API2"}.isdisjoint(available))

    @override_settings(GEMINI_ROLE_KEY_POOLS={
        "chat": {"own": ["GEMINI_API"], "borrow": ["GEMINI_API2"]},
        "management": {
            "own": ["GEMINI_API3"],
            "borrow": ["GEMINI_API", "GEMINI_API2", "GEMINI_API4"],
        },
        "checker": {
            "own": ["GEMINI_API5"],
            "borrow": ["GEMINI_API2", "GEMINI_API6"],
        },
    })
    def test_runtime_pool_override_cannot_restore_chat_key_borrowing(self):
        env = {f"GEMINI_API{n}": f"runtime-key-{n or '1'}" for n in ("", "2", "3", "4", "5", "6")}
        with patch.dict("os.environ", env, clear=False):
            for role in ("management", "checker"):
                names = {key for key, _value, _model in gemini_keys.iter_attempts(role)}
                self.assertTrue({"GEMINI_API", "GEMINI_API2"}.isdisjoint(names))
            chat_names = {key for key, _value, _model in gemini_keys.iter_attempts("chat")}
            self.assertEqual(
                chat_names,
                {"GEMINI_API", "GEMINI_API2", "GEMINI_API3", "GEMINI_API4", "GEMINI_API5", "GEMINI_API6"},
            )

    @override_settings(GEMINI_KEY_PROJECT_GROUPS={
        "GEMINI_API": "chat-project",
        "GEMINI_API2": "chat-project",
        "GEMINI_API3": "chat-project",
        "GEMINI_API4": "background-project",
        "GEMINI_API5": "background-project",
        "GEMINI_API6": "background-project",
    })
    def test_background_pool_excludes_aliases_sharing_chat_project_or_secret(self):
        env = {f"GEMINI_API{n}": f"project-key-{n or '1'}" for n in ("", "2", "3", "4", "5", "6")}
        env["GEMINI_API4"] = env["GEMINI_API"]
        with patch.dict("os.environ", env, clear=False):
            names = {key for key, _value, _model in gemini_keys.iter_attempts("management")}
            self.assertNotIn("GEMINI_API", names)
            self.assertNotIn("GEMINI_API2", names)
            self.assertNotIn("GEMINI_API3", names)
            self.assertNotIn("GEMINI_API4", names)
            self.assertIn("GEMINI_API5", names)
            self.assertIn("GEMINI_API6", names)

    @patch("management.services.bot_conversation_analysis.gemini_generate_json")
    def test_background_analysis_defers_while_customer_reply_is_pending(self, generate):
        settings = InstagramBotSettings.load()
        settings.is_enabled = True
        settings.save(update_fields=["is_enabled"])
        client = IgClient.get_or_create_for_sender("analysis-defers-for-live-reply")
        analyzed = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Хочу футболку",
            status=InstagramBotMessage.Status.DONE,
        )
        bot_conversation_analysis.schedule_analysis(
            client, analyzed, delay_seconds=0
        )
        InstagramBotMessage.objects.create(
            sender_id="new-live-customer",
            role=InstagramBotMessage.Role.USER,
            text="Hello",
            status=InstagramBotMessage.Status.PENDING,
        )

        result = bot_conversation_analysis.process_due_analysis(limit=1)

        self.assertEqual(result, {
            "done": 0,
            "failed": 0,
            "skipped": 0,
            "superseded": 0,
        })
        self.assertEqual(
            IgConversationAnalysisJob.objects.get(client=client).status,
            IgConversationAnalysisJob.Status.PENDING,
        )
        generate.assert_not_called()

    @patch("management.services.bot_conversation_analysis.gemini_generate_json")
    @patch(
        "management.services.bot_conversation_analysis._customer_reply_work_waiting",
        side_effect=[False, True],
    )
    def test_analysis_releases_claim_if_live_reply_arrives_after_initial_check(
        self, waiting, generate
    ):
        client = IgClient.get_or_create_for_sender("analysis-race-with-live-reply")
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Хочу футболку",
            status=InstagramBotMessage.Status.DONE,
        )
        bot_conversation_analysis.schedule_analysis(client, message, delay_seconds=0)

        result = bot_conversation_analysis.process_due_analysis(limit=1)

        job = IgConversationAnalysisJob.objects.get(client=client)
        self.assertEqual(result, {
            "done": 0,
            "failed": 0,
            "skipped": 0,
            "superseded": 0,
        })
        self.assertEqual(job.status, IgConversationAnalysisJob.Status.PENDING)
        self.assertEqual(job.attempts, 0)
        generate.assert_not_called()
        self.assertEqual(waiting.call_count, 2)

    @patch("management.services.bot_conversation_analysis.gemini_generate_json")
    def test_analysis_releases_claim_when_live_reply_arrives_before_provider_call(
        self, generate
    ):
        settings = InstagramBotSettings.load()
        settings.is_enabled = True
        settings.save(update_fields=["is_enabled"])
        client = IgClient.get_or_create_for_sender("analysis-race-before-provider")
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Хочу футболку",
            status=InstagramBotMessage.Status.DONE,
        )
        bot_conversation_analysis.schedule_analysis(client, message, delay_seconds=0)

        original_conversation = bot_conversation_analysis._conversation

        def conversation_with_new_live_reply(*args, **kwargs):
            output = original_conversation(*args, **kwargs)
            InstagramBotMessage.objects.create(
                sender_id="live-arrives-during-analysis",
                role=InstagramBotMessage.Role.USER,
                text="Hello, I need help now",
                status=InstagramBotMessage.Status.PENDING,
                source="webhook",
            )
            return output

        with patch.object(
            bot_conversation_analysis,
            "_conversation",
            side_effect=conversation_with_new_live_reply,
        ):
            result = bot_conversation_analysis.process_due_analysis(limit=1)

        job = IgConversationAnalysisJob.objects.get(client=client)
        self.assertEqual(result, {
            "done": 0,
            "failed": 0,
            "skipped": 0,
            "superseded": 0,
        })
        self.assertEqual(job.status, IgConversationAnalysisJob.Status.PENDING)
        self.assertEqual(job.attempts, 0)
        generate.assert_not_called()

    @patch(
        "management.services.bot_conversation_analysis._process_claim",
        return_value="done",
    )
    def test_disabled_reply_runtime_does_not_starve_crm_analysis(self, process):
        settings = InstagramBotSettings.load()
        settings.is_enabled = False
        settings.save(update_fields=["is_enabled"])
        client = IgClient.get_or_create_for_sender("analysis-while-replies-disabled")
        analyzed = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="Хочу футболку",
            status=InstagramBotMessage.Status.DONE,
        )
        bot_conversation_analysis.schedule_analysis(client, analyzed, delay_seconds=0)
        InstagramBotMessage.objects.create(
            sender_id="stale-pending-while-disabled",
            role=InstagramBotMessage.Role.USER,
            text="Hello",
            status=InstagramBotMessage.Status.PENDING,
        )

        result = bot_conversation_analysis.process_due_analysis(limit=1)

        self.assertEqual(result["done"], 1)
        process.assert_called_once()

    def test_reconcile_uses_provider_time_for_historical_refresh(self):
        now = timezone.now()
        settings = InstagramBotSettings.load()
        settings.analysis_reconcile_after = now - timedelta(days=1)
        settings.analysis_backfill_enabled = False
        settings.save(update_fields=[
            "analysis_reconcile_after", "analysis_backfill_enabled",
        ])
        client = IgClient.get_or_create_for_sender("historical-provider-time")
        InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="старе повідомлення",
            source="manual_refresh",
            provider_created_at=now - timedelta(days=30),
            status=InstagramBotMessage.Status.DONE,
        )

        result = bot_conversation_analysis.reconcile_analysis_jobs(limit=20, now=now)

        self.assertEqual(result["queued"], 0)
        self.assertEqual(result["historical_blocked"], 1)
        self.assertFalse(IgConversationAnalysisJob.objects.filter(client=client).exists())

    def test_reconcile_watermark_uses_latest_provider_event_not_highest_db_id(self):
        now = timezone.now()
        settings = InstagramBotSettings.load()
        settings.analysis_reconcile_after = now - timedelta(days=1)
        settings.analysis_backfill_enabled = False
        settings.save(update_fields=[
            "analysis_reconcile_after", "analysis_backfill_enabled",
        ])
        client = IgClient.get_or_create_for_sender("provider-time-watermark")
        fresh = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="fresh webhook message",
            source="webhook",
            provider_created_at=now,
            status=InstagramBotMessage.Status.DONE,
        )
        historical_import = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="old imported message",
            source="manual_refresh",
            provider_created_at=now - timedelta(days=30),
            status=InstagramBotMessage.Status.DONE,
        )
        self.assertGreater(historical_import.pk, fresh.pk)

        result = bot_conversation_analysis.reconcile_analysis_jobs(limit=20, now=now)

        self.assertEqual(result["queued"], 1)
        job = IgConversationAnalysisJob.objects.get(client=client)
        self.assertEqual(job.watermark_message_id, fresh.pk)

    def test_old_rules_snapshot_is_reclassified_under_current_rules_version(self):
        client = IgClient.get_or_create_for_sender("rules-version-refresh")
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="What is the status of my order?",
            source="webhook",
            status=InstagramBotMessage.Status.DONE,
        )
        IgConversationAnalysisSnapshot.objects.create(
            client=client,
            last_analyzed_message=message,
            dedupe_key=f"rules:2026-07-26.v5:{client.pk}:{message.pk}",
            score_band=IgConversationAnalysisSnapshot.Band.COLD,
            interaction_type=IgConversationAnalysisSnapshot.InteractionType.INFORMATION_ONLY,
            analysis_model="rules",
            rules_version="2026-07-26.v5",
        )

        result = bot_sales_classifier.ensure_rule_classification(client, message)

        self.assertIsNotNone(result)
        current = client.analysis_snapshots.get(
            last_analyzed_message=message,
            rules_version=bot_sales_classifier.ANALYSIS_RULES_VERSION,
        )
        self.assertEqual(current.analysis_model, "rules")
        self.assertEqual(client.analysis_snapshots.count(), 2)

    @patch("management.services.bot_conversation_analysis.gemini_generate_json")
    def test_existing_historical_reconcile_job_is_skipped_without_ai(self, generate):
        now = timezone.now()
        settings = InstagramBotSettings.load()
        settings.analysis_reconcile_after = now - timedelta(days=1)
        settings.analysis_backfill_enabled = False
        settings.save(update_fields=[
            "analysis_reconcile_after", "analysis_backfill_enabled",
        ])
        client = IgClient.get_or_create_for_sender("historical-pending-job")
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="старе повідомлення",
            source="manual_refresh",
            provider_created_at=now - timedelta(days=30),
            status=InstagramBotMessage.Status.DONE,
        )
        job = bot_conversation_analysis.schedule_analysis(
            client,
            message,
            trigger="reconcile",
            now=now,
            delay_seconds=0,
        )

        result = bot_conversation_analysis.process_due_analysis(limit=1, now=now)

        job.refresh_from_db()
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(job.status, IgConversationAnalysisJob.Status.SKIPPED)
        self.assertEqual(job.skip_reason, "historical_reconcile")
        generate.assert_not_called()

    @patch("management.services.bot_conversation_analysis.gemini_generate_json")
    def test_old_prompt_refresh_at_analyzed_watermark_is_skipped_without_ai(
        self, generate
    ):
        now = timezone.now()
        settings = InstagramBotSettings.load()
        settings.analysis_reconcile_after = now - timedelta(days=1)
        settings.analysis_backfill_enabled = False
        settings.save(update_fields=[
            "analysis_reconcile_after", "analysis_backfill_enabled",
        ])
        client = IgClient.get_or_create_for_sender("old-analyzed-watermark-refresh")
        message = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="old message with a stale prompt snapshot",
            source="manual_refresh",
            provider_created_at=now - timedelta(days=30),
            status=InstagramBotMessage.Status.DONE,
        )
        job = IgConversationAnalysisJob.objects.create(
            client=client,
            watermark_message_id=message.pk,
            analyzed_watermark_message_id=message.pk,
            revision=2,
            analyzed_revision=1,
            status=IgConversationAnalysisJob.Status.PENDING,
            due_at=now,
            next_attempt_at=now,
            trigger="reconcile",
            required_state_fingerprint="stale-prompt-refresh",
        )
        generate.return_value = {"parsed": {}, "model": "test", "meta": {}}

        result = bot_conversation_analysis.process_due_analysis(limit=1, now=now)

        job.refresh_from_db()
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(job.status, IgConversationAnalysisJob.Status.SKIPPED)
        self.assertEqual(job.skip_reason, "historical_reconcile")
        generate.assert_not_called()

    @patch("management.services.bot_conversation_analysis.gemini_generate_json")
    def test_imported_historical_triggers_are_skipped_without_ai(self, generate):
        now = timezone.now()
        settings = InstagramBotSettings.load()
        settings.analysis_reconcile_after = now - timedelta(days=1)
        settings.analysis_backfill_enabled = False
        settings.save(update_fields=[
            "analysis_reconcile_after", "analysis_backfill_enabled",
        ])
        for index, trigger in enumerate(("poll_history", "poll_backfill", "manual_refresh")):
            client = IgClient.get_or_create_for_sender(f"historical-trigger-{index}")
            message = InstagramBotMessage.objects.create(
                sender_id=client.igsid,
                client=client,
                role=InstagramBotMessage.Role.USER,
                text="старе повідомлення",
                source={
                    "poll_history": "poll_history",
                    "poll_backfill": "poll",
                    "manual_refresh": "manual_refresh",
                }[trigger],
                provider_created_at=now - timedelta(days=30),
                status=InstagramBotMessage.Status.DONE,
            )
            bot_conversation_analysis.schedule_analysis(
                client, message, trigger=trigger, now=now, delay_seconds=0,
            )
            result = bot_conversation_analysis.process_due_analysis(limit=1, now=now)
            job = IgConversationAnalysisJob.objects.get(client=client)
            self.assertEqual(result["skipped"], 1)
            self.assertEqual(job.status, IgConversationAnalysisJob.Status.SKIPPED)
            self.assertEqual(job.skip_reason, "historical_reconcile")
        generate.assert_not_called()

    @patch("management.services.bot_conversation_analysis.gemini_generate_json")
    def test_old_refresh_job_is_skipped_even_if_client_has_older_analyzed_fresh_row(
        self, generate
    ):
        now = timezone.now()
        settings = InstagramBotSettings.load()
        settings.analysis_reconcile_after = now - timedelta(days=1)
        settings.analysis_backfill_enabled = False
        settings.save(update_fields=[
            "analysis_reconcile_after", "analysis_backfill_enabled",
        ])
        client = IgClient.get_or_create_for_sender("historical-job-with-fresh-row")
        fresh = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="fresh message already handled",
            source="webhook",
            provider_created_at=now,
            status=InstagramBotMessage.Status.DONE,
        )
        historical = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="old imported message",
            source="manual_refresh",
            provider_created_at=now - timedelta(days=30),
            status=InstagramBotMessage.Status.DONE,
        )
        job = bot_conversation_analysis.schedule_analysis(
            client,
            historical,
            trigger="manual_refresh",
            now=now,
            delay_seconds=0,
        )
        job.analyzed_watermark_message_id = fresh.pk
        job.analyzed_revision = max(0, int(job.revision or 0) - 1)
        job.save(update_fields=[
            "analyzed_watermark_message_id", "analyzed_revision", "updated_at",
        ])

        result = bot_conversation_analysis.process_due_analysis(limit=1, now=now)

        job.refresh_from_db()
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(job.skip_reason, "historical_reconcile")
        generate.assert_not_called()

    @patch("management.services.bot_conversation_analysis.gemini_generate_json")
    def test_old_high_watermark_cannot_hide_fresh_unanalyzed_message(self, generate):
        now = timezone.now()
        settings = InstagramBotSettings.load()
        settings.analysis_reconcile_after = now - timedelta(days=1)
        settings.analysis_backfill_enabled = False
        settings.save(update_fields=[
            "analysis_reconcile_after", "analysis_backfill_enabled",
        ])
        client = IgClient.get_or_create_for_sender("fresh-delta-beats-old-watermark")
        fresh = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="fresh webhook message needs analysis",
            source="webhook",
            provider_created_at=now,
            status=InstagramBotMessage.Status.DONE,
        )
        historical = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="old imported message",
            source="manual_refresh",
            provider_created_at=now - timedelta(days=30),
            status=InstagramBotMessage.Status.DONE,
        )
        self.assertGreater(historical.pk, fresh.pk)
        job = bot_conversation_analysis.schedule_analysis(
            client,
            historical,
            trigger="manual_refresh",
            now=now,
            delay_seconds=0,
        )
        generate.return_value = {"parsed": {}, "model": "test", "meta": {}}

        result = bot_conversation_analysis.process_due_analysis(limit=1, now=now)

        job.refresh_from_db()
        self.assertEqual(result["done"], 1)
        self.assertEqual(job.status, IgConversationAnalysisJob.Status.DONE)
        self.assertNotEqual(job.skip_reason, "historical_reconcile")
        generate.assert_called_once()

    def test_historical_guard_preserves_recent_payment_and_order_truth_changes(self):
        now = timezone.now()
        settings = InstagramBotSettings.load()
        settings.analysis_reconcile_after = now - timedelta(days=1)
        settings.analysis_backfill_enabled = False
        settings.save(update_fields=[
            "analysis_reconcile_after", "analysis_backfill_enabled",
        ])

        for field in ("payment_truth_updated_at", "order_truth_updated_at"):
            with self.subTest(field=field):
                client = IgClient.get_or_create_for_sender(
                    f"historical-{field}-change"
                )
                message = InstagramBotMessage.objects.create(
                    sender_id=client.igsid,
                    client=client,
                    role=InstagramBotMessage.Role.USER,
                    text="old imported message",
                    source="manual_refresh",
                    provider_created_at=now - timedelta(days=30),
                    status=InstagramBotMessage.Status.DONE,
                )
                job = bot_conversation_analysis.schedule_analysis(
                    client,
                    message,
                    trigger="manual_refresh",
                    now=now,
                    delay_seconds=0,
                )
                deal = IgDeal.objects.create(client=client)
                setattr(deal, field, now)
                deal.save(update_fields=[field])

                self.assertFalse(
                    bot_conversation_analysis._historical_reconcile_job(
                        job,
                        message.pk,
                    )
                )

    def test_old_refresh_cannot_replace_pending_fresh_webhook_job(self):
        now = timezone.now()
        settings = InstagramBotSettings.load()
        settings.analysis_reconcile_after = now - timedelta(days=1)
        settings.analysis_backfill_enabled = False
        settings.save(update_fields=[
            "analysis_reconcile_after", "analysis_backfill_enabled",
        ])
        client = IgClient.get_or_create_for_sender("fresh-job-survives-old-refresh")
        fresh = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="fresh webhook message",
            source="webhook",
            provider_created_at=now,
            status=InstagramBotMessage.Status.DONE,
        )
        job = bot_conversation_analysis.schedule_analysis(
            client,
            fresh,
            trigger="webhook_inbound",
            now=now,
            delay_seconds=0,
        )
        original_revision = job.revision
        historical = InstagramBotMessage.objects.create(
            sender_id=client.igsid,
            client=client,
            role=InstagramBotMessage.Role.USER,
            text="old imported message",
            source="manual_refresh",
            provider_created_at=now - timedelta(days=30),
            status=InstagramBotMessage.Status.DONE,
        )
        self.assertGreater(historical.pk, fresh.pk)

        returned = bot_conversation_analysis.schedule_analysis(
            client,
            historical,
            trigger="manual_refresh",
            now=now,
            delay_seconds=0,
        )

        returned.refresh_from_db()
        self.assertEqual(returned.pk, job.pk)
        self.assertEqual(returned.trigger, "webhook_inbound")
        self.assertEqual(returned.watermark_message_id, fresh.pk)
        self.assertEqual(returned.revision, original_revision)

    @patch("management.services.call_ai_analysis.time.sleep")
    @patch("management.services.call_ai_analysis.gemini_keys.clear_model_overload")
    @patch("management.services.call_ai_analysis.gemini_keys.iter_attempts", return_value=iter(()))
    @patch("management.services.call_ai_analysis.gemini_keys.model_chain", return_value=["gemini-test"])
    @patch("management.services.call_ai_analysis.gemini_keys.max_rounds", return_value=3)
    def test_pool_does_not_sleep_when_every_key_is_already_unavailable(
        self, _rounds, _models, _attempts, _clear, sleep
    ):
        with self.assertRaises(call_ai_analysis.CallAIAnalysisError):
            call_ai_analysis._run_with_pool(
                "chat",
                {"contents": [{"role": "user", "parts": [{"text": "hello"}]}]},
                deadline_seconds=20,
            )

        sleep.assert_not_called()


class DeterministicReplyFallbackTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.ai_enabled = True
        self.settings.allowed_senders = ""
        self.settings.save(update_fields=[
            "is_enabled", "ai_enabled", "allowed_senders",
        ])
        self.client = IgClient.get_or_create_for_sender("fallback-english-client")
        self.client.profile_fetched_at = timezone.now()
        self.client.save(update_fields=["profile_fetched_at", "updated_at"])

    def _order(self, number, **overrides):
        values = {
            "order_number": number,
            "full_name": "Test Customer",
            "phone": "0501112233",
            "city": "Kyiv",
            "np_office": "Branch 1",
            "payment_status": "paid",
            "status": "new",
            "total_sum": Decimal("3428.00"),
        }
        values.update(overrides)
        return Order.objects.create(**values)

    def _pending(self, text, suffix):
        return InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text=text,
            mid=f"fallback-{suffix}",
            status=InstagramBotMessage.Status.PENDING,
            source="webhook",
        )

    @patch("management.services.instagram_bot._deliver_manager_notification", return_value=False)
    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    @patch("management.services.instagram_bot.gemini_generate", return_value=None)
    def test_linked_order_gets_factual_english_reply_when_gemini_is_unavailable(
        self, _generate, send_text, _sender_action, _deliver
    ):
        order = self._order("TWC28072026N01")
        IgDeal.objects.create(
            client=self.client,
            status=IgDeal.Status.ORDER_CREATED,
            order=order,
            payment_status="paid",
            payment_truth=IgDeal.PaymentTruth.CONFIRMED,
            paid_amount=Decimal("3428.00"),
        )
        row = self._pending(
            "Greetings, what is the status of order TWC28072026N01?",
            "linked-order",
        )

        self.assertEqual(instagram_bot.process_pending(self.settings, max_items=1), 1)

        row.refresh_from_db()
        reply = send_text.call_args.args[2]
        self.assertEqual(row.status, InstagramBotMessage.Status.DONE)
        self.assertIn("TWC28072026N01", reply)
        self.assertIn("paid", reply.lower())
        self.assertIn("processed", reply.lower())
        self.assertIn("not been marked as shipped", reply.lower())
        self.assertNotIn("Kyiv", reply)
        self.assertFalse(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason__startswith="ai_fallback",
            ).exists()
        )
        self.assertFalse(
            IgFollowUpTask.objects.filter(
                client=self.client,
                status=IgFollowUpTask.Status.PENDING,
            ).exists()
        )

    @patch("management.services.instagram_bot._deliver_manager_notification", return_value=False)
    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    @patch("management.services.instagram_bot.gemini_generate", return_value=None)
    def test_refund_request_for_confirmed_order_is_handed_to_manager(
        self, _generate, send_text, _sender_action, _deliver
    ):
        order = self._order("TWC28072026N07")
        IgDeal.objects.create(
            client=self.client,
            status=IgDeal.Status.ORDER_CREATED,
            order=order,
            pay_type=IgDeal.PayType.ONLINE_FULL,
            requested_payment_amount=Decimal("3428.00"),
            amount=Decimal("3428.00"),
            payment_status="paid",
            payment_truth=IgDeal.PaymentTruth.CONFIRMED,
            paid_amount=Decimal("3428.00"),
        )
        row = self._pending(
            "Please refund order TWC28072026N07",
            "confirmed-order-refund",
        )

        self.assertEqual(instagram_bot.process_pending(self.settings, max_items=1), 1)

        reply = send_text.call_args.args[2].lower()
        self.assertIn("manager", reply)
        self.assertNotIn("fully paid", reply)
        self.assertTrue(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason=f"ai_fallback:support:{row.pk}",
                kind=IgFollowUpTask.Kind.MANAGER_TASK,
            ).exists()
        )
        self.assertFalse(
            IgFollowUpTask.objects.filter(
                client=self.client,
                status=IgFollowUpTask.Status.PENDING,
            ).exists()
        )

    @patch("management.services.instagram_bot._deliver_manager_notification", return_value=False)
    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    @patch("management.services.instagram_bot.gemini_generate", return_value=None)
    def test_unlinked_order_gets_private_manager_handoff_without_failed_row(
        self, _generate, send_text, _sender_action, _deliver
    ):
        self._order("TWC28072026N02")
        row = self._pending(
            "Please check order TWC28072026N02 for me",
            "unlinked-order",
        )

        self.assertEqual(instagram_bot.process_pending(self.settings, max_items=1), 1)

        row.refresh_from_db()
        reply = send_text.call_args.args[2]
        self.assertEqual(row.status, InstagramBotMessage.Status.DONE)
        self.assertIn("manager", reply.lower())
        self.assertNotIn("paid", reply.lower())
        self.assertNotIn("3428", reply)
        task = IgFollowUpTask.objects.get(
            client=self.client,
            reason=f"ai_fallback:order_unverified:{row.pk}",
        )
        self.assertEqual(task.status, IgFollowUpTask.Status.SKIPPED)
        self.assertEqual(task.skip_reason, "human_agent_required")
        self.assertEqual(
            IgBotNotification.objects.filter(
                client=self.client,
                event_type="ai_reply_fallback",
            ).count(),
            1,
        )
        self.assertFalse(
            IgFollowUpTask.objects.filter(
                client=self.client,
                status=IgFollowUpTask.Status.PENDING,
            ).exists()
        )
        self.client.refresh_from_db()
        self.assertEqual(self.client.stage, IgClient.Stage.LEAD_TO_MANAGER)

    @patch("management.services.instagram_bot._deliver_manager_notification", return_value=False)
    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    @patch("management.services.instagram_bot.gemini_generate", return_value=None)
    def test_confirmed_prepayment_is_not_described_as_fully_paid(
        self, _generate, send_text, _sender_action, _deliver
    ):
        order = self._order("TWC28072026N05")
        deal = IgDeal.objects.create(
            client=self.client,
            status=IgDeal.Status.ORDER_CREATED,
            order=order,
            pay_type=IgDeal.PayType.PREPAYMENT,
            requested_payment_amount=Decimal("500.00"),
            amount=Decimal("3428.00"),
            payment_status="paid",
            payment_truth=IgDeal.PaymentTruth.CONFIRMED,
            paid_amount=Decimal("500.00"),
        )
        IgPaymentProjection.objects.create(
            deal=deal,
            client=self.client,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("500.00"),
        )
        row = self._pending(
            "What is the status of order TWC28072026N05?",
            "confirmed-prepayment",
        )

        self.assertEqual(instagram_bot.process_pending(self.settings, max_items=1), 1)

        reply = send_text.call_args.args[2].lower()
        self.assertIn("prepayment", reply)
        self.assertIn("500", reply)
        self.assertIn("2928", reply)
        self.assertNotIn("is paid and", reply)

    @patch("management.services.instagram_bot._deliver_manager_notification", return_value=False)
    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    @patch("management.services.instagram_bot.gemini_generate", return_value=None)
    def test_confirmed_amount_mismatch_is_handed_to_manager(
        self, _generate, send_text, _sender_action, _deliver
    ):
        order = self._order("TWC28072026N06")
        deal = IgDeal.objects.create(
            client=self.client,
            status=IgDeal.Status.ORDER_CREATED,
            order=order,
            pay_type=IgDeal.PayType.ONLINE_FULL,
            requested_payment_amount=Decimal("3428.00"),
            amount=Decimal("3428.00"),
            payment_status="paid",
            payment_truth=IgDeal.PaymentTruth.CONFIRMED,
            paid_amount=Decimal("500.00"),
        )
        IgPaymentProjection.objects.create(
            deal=deal,
            client=self.client,
            truth=IgDeal.PaymentTruth.CONFIRMED,
            gross_amount=Decimal("500.00"),
        )
        row = self._pending(
            "What is the status of order TWC28072026N06?",
            "amount-mismatch",
        )

        self.assertEqual(instagram_bot.process_pending(self.settings, max_items=1), 1)

        reply = send_text.call_args.args[2].lower()
        self.assertIn("manager", reply)
        self.assertNotIn("fully paid", reply)
        self.assertTrue(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason=f"ai_fallback:order_payment_unverified:{row.pk}",
            ).exists()
        )

    @patch("management.services.instagram_bot._deliver_manager_notification", return_value=False)
    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    @patch("management.services.instagram_bot.gemini_generate", return_value=None)
    def test_linked_order_without_canonical_payment_truth_gets_handoff(
        self, _generate, send_text, _sender_action, _deliver
    ):
        order = self._order("TWC28072026N04")
        IgDeal.objects.create(
            client=self.client,
            status=IgDeal.Status.ORDER_CREATED,
            order=order,
            payment_status="paid",
            payment_truth=IgDeal.PaymentTruth.UNVERIFIED,
            paid_amount=Decimal("3428.00"),
        )
        row = self._pending(
            "Please check order TWC28072026N04",
            "unverified-order",
        )

        self.assertEqual(instagram_bot.process_pending(self.settings, max_items=1), 1)

        row.refresh_from_db()
        reply = send_text.call_args.args[2]
        self.assertEqual(row.status, InstagramBotMessage.Status.DONE)
        self.assertIn("manager", reply.lower())
        self.assertNotIn("paid", reply.lower())
        self.assertTrue(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason=f"ai_fallback:order_payment_unverified:{row.pk}",
            ).exists()
        )

    @patch("management.services.instagram_bot._deliver_manager_notification", return_value=False)
    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    @patch("management.services.instagram_bot.gemini_generate", return_value=None)
    def test_english_collaboration_gets_one_manager_handoff(
        self, _generate, send_text, _sender_action, _deliver
    ):
        row = self._pending(
            "Hello, I would like to discuss a partnership and collaboration.",
            "collaboration",
        )

        self.assertEqual(instagram_bot.process_pending(self.settings, max_items=1), 1)

        row.refresh_from_db()
        reply = send_text.call_args.args[2]
        self.assertEqual(row.status, InstagramBotMessage.Status.DONE)
        self.assertIn("collaboration", reply.lower())
        self.assertIn("manager", reply.lower())
        self.client.refresh_from_db()
        self.assertEqual(self.client.language, "en")
        self.assertEqual(self.client.spam_strikes, 0)
        self.assertEqual(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason=f"ai_fallback:collaboration:{row.pk}",
            ).count(),
            1,
        )
        self.assertEqual(
            IgBotNotification.objects.filter(
                client=self.client,
                event_type="ai_reply_fallback",
            ).count(),
            1,
        )

    @patch.dict("os.environ", {
        "MANAGEMENT_TG_BOT_TOKEN": "test-token",
        "MANAGEMENT_TG_ADMIN_CHAT_ID": "123",
    }, clear=False)
    @patch("management.services.instagram_bot._http")
    @patch("management.services.instagram_bot.send_sender_action")
    def test_repeated_fallback_reentry_sends_one_manager_notification(
        self, _sender_action, http
    ):
        http.return_value = (200, '{"ok": true, "result": {"message_id": 77}}')
        row = self._pending(
            "Please check order TWC28072026N03 for me",
            "repeated-fallback",
        )
        self._order("TWC28072026N03")

        from management.services.bot_reply_fallback import build_ai_failure_fallback

        first = build_ai_failure_fallback(row)
        second = build_ai_failure_fallback(row)

        self.assertEqual(first, second)
        self.assertEqual(
            IgFollowUpTask.objects.filter(
                client=self.client,
                reason=f"ai_fallback:order_unverified:{row.pk}",
            ).count(),
            1,
        )
        notification = IgBotNotification.objects.get(
            client=self.client,
            event_type="ai_reply_fallback",
        )
        self.assertEqual(notification.status, IgBotNotification.Status.SENT)
        self.assertEqual(notification.telegram_message_id, "77")
        self.assertEqual(http.call_count, 1)

    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    @patch("management.services.instagram_bot.gemini_generate", return_value=None)
    def test_orphan_inbound_gets_generic_fallback(self, _generate, send_text, _sender_action):
        row = InstagramBotMessage.objects.create(
            sender_id="orphan-fallback-sender",
            role=InstagramBotMessage.Role.USER,
            text="Hello, can you help me?",
            mid="orphan-fallback",
            status=InstagramBotMessage.Status.PENDING,
            source="webhook",
        )

        self.assertEqual(instagram_bot.process_pending(self.settings, max_items=1), 1)

        row.refresh_from_db()
        self.assertEqual(row.status, InstagramBotMessage.Status.DONE)
        self.assertIn("manager", send_text.call_args.args[2].lower())

    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.gemini_generate")
    @patch("management.services.instagram_bot.send_text")
    def test_generic_provider_outage_queues_one_recovery_without_false_manager_handoff(
        self, send_text, _generate, _sender_action
    ):
        from management.models import IgAiReplyRecoveryJob
        from management.services.instagram_bot import ProviderDeliveryReceipt

        source = self._pending("Can you help me choose a T-shirt?", "generic-outage")

        def typed_provider_outage(*_args, **kwargs):
            kwargs["failure_context"]["kind"] = "provider_outage"
            return None

        def confirmed_holding(*_args, **_kwargs):
            # The recovery intent must survive a process death during the
            # holding-message send, so it precedes the Meta boundary.
            job = IgAiReplyRecoveryJob.objects.get(source_message=source)
            self.pre_send_recovery_state = (
                job.holding_message_id,
                job.activated_at,
            )
            return ProviderDeliveryReceipt(True, "", "", "meta-outage-holding-1")

        _generate.side_effect = typed_provider_outage
        send_text.side_effect = confirmed_holding

        with patch.object(instagram_bot, "log") as logs:
            self.assertEqual(
                instagram_bot.process_pending(self.settings, max_items=1),
                1,
                logs.call_args_list,
            )
        self.assertEqual(self.pre_send_recovery_state, (None, None))

        reply = send_text.call_args.args[2].lower()
        job = IgAiReplyRecoveryJob.objects.get(source_message=source)
        source.refresh_from_db()
        self.client.refresh_from_db()
        self.assertNotIn("manager", reply)
        self.assertEqual(source.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(job.status, IgAiReplyRecoveryJob.Status.PENDING)
        self.assertIsNotNone(job.holding_message_id)
        self.assertNotEqual(self.client.stage, IgClient.Stage.LEAD_TO_MANAGER)

    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.gemini_generate")
    @patch("management.services.instagram_bot.send_text")
    @patch("management.services.instagram_bot._repeated_question", return_value=1)
    @patch(
        "management.services.instagram_bot._wait_for_typing_window",
        return_value="permission_denied",
    )
    def test_provider_outage_permission_change_during_typing_terminalizes_recovery(
        self, _wait, _repeated, send_text, generate, _sender_action
    ):
        from management.models import IgAiReplyRecoveryJob

        source = self._pending("Can you help me choose a T-shirt?", "permission-typing")

        def typed_provider_outage(*_args, **kwargs):
            kwargs["failure_context"]["kind"] = "provider_outage"
            return None

        generate.side_effect = typed_provider_outage

        self.assertEqual(
            instagram_bot.process_pending(self.settings, max_items=1),
            0,
        )

        source.refresh_from_db()
        job = IgAiReplyRecoveryJob.objects.get(source_message=source)
        self.assertEqual(source.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(job.status, IgAiReplyRecoveryJob.Status.CANCELLED)
        self.assertIsNone(job.activated_at)
        self.assertIsNone(job.next_attempt_at)
        self.assertIsNotNone(job.completed_at)
        self.assertIn("permission", job.last_error)
        send_text.assert_not_called()

    @patch(
        "management.services.ig_reply_boundary.customer_send_boundary",
        return_value=nullcontext(False),
    )
    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.gemini_generate")
    @patch("management.services.instagram_bot.send_text")
    @patch("management.services.instagram_bot._repeated_question", return_value=1)
    @patch(
        "management.services.instagram_bot._wait_for_typing_window",
        return_value="allowed",
    )
    def test_provider_outage_permission_change_at_send_boundary_terminalizes_recovery(
        self, _wait, _repeated, send_text, generate, _sender_action, _send_boundary
    ):
        from management.models import IgAiReplyRecoveryJob

        source = self._pending("Can you help me choose a T-shirt?", "permission-send")

        def typed_provider_outage(*_args, **kwargs):
            kwargs["failure_context"]["kind"] = "provider_outage"
            return None

        generate.side_effect = typed_provider_outage

        self.assertEqual(
            instagram_bot.process_pending(self.settings, max_items=1),
            0,
        )

        source.refresh_from_db()
        job = IgAiReplyRecoveryJob.objects.get(source_message=source)
        self.assertEqual(source.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(job.status, IgAiReplyRecoveryJob.Status.CANCELLED)
        self.assertIsNone(job.activated_at)
        self.assertIsNone(job.next_attempt_at)
        self.assertIsNotNone(job.completed_at)
        self.assertIn("permission", job.last_error)
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.gemini_generate")
    @patch("management.services.instagram_bot.send_text")
    @patch("management.services.instagram_bot._repeated_question", return_value=1)
    @patch("management.services.instagram_bot._wait_for_typing_window")
    def test_provider_outage_retryable_lease_loss_keeps_recovery_prepared(
        self, wait, _repeated, send_text, generate, _sender_action
    ):
        from management.models import IgAiReplyRecoveryJob

        source = self._pending("Can you help me choose a T-shirt?", "lease-retry")

        def typed_provider_outage(*_args, **kwargs):
            kwargs["failure_context"]["kind"] = "provider_outage"
            return None

        def lose_lease(_settings, claimed_row, *_args, **_kwargs):
            instagram_bot._requeue_for_active_lease(claimed_row)
            return "lease_lost"

        generate.side_effect = typed_provider_outage
        wait.side_effect = lose_lease

        self.assertEqual(
            instagram_bot.process_pending(self.settings, max_items=1),
            0,
        )

        source.refresh_from_db()
        job = IgAiReplyRecoveryJob.objects.get(source_message=source)
        self.assertEqual(source.status, InstagramBotMessage.Status.PENDING)
        self.assertEqual(job.status, IgAiReplyRecoveryJob.Status.PENDING)
        self.assertIsNone(job.activated_at)
        self.assertIsNone(job.next_attempt_at)
        self.assertIsNone(job.completed_at)
        send_text.assert_not_called()

    def test_recovery_schedule_failure_is_terminal_with_known_unsent_state(self):
        source = self._pending("Can you help me choose a T-shirt?", "recovery-schedule-failed")

        def typed_provider_outage(*_args, **kwargs):
            kwargs["failure_context"]["kind"] = "provider_outage"
            return None

        with patch(
            "management.services.instagram_bot.gemini_generate",
            side_effect=typed_provider_outage,
        ), patch(
            "management.services.instagram_bot.send_sender_action"
        ), patch(
            "management.services.instagram_bot.send_text"
        ) as send_text, patch(
            "management.services.ig_ai_reply_recovery.schedule_recovery",
            side_effect=RuntimeError("recovery storage unavailable"),
        ):
            self.assertEqual(instagram_bot.process_pending(self.settings, max_items=1), 0)

        source.refresh_from_db()
        self.assertEqual(source.status, InstagramBotMessage.Status.FAILED)
        self.assertEqual(source.send_state, "failed")
        send_text.assert_not_called()

    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.gemini_generate", return_value=None)
    @patch("management.services.instagram_bot.send_text", return_value=(True, "", ""))
    def test_untyped_generation_failure_never_schedules_outage_recovery(
        self, send_text, _generate, _sender_action
    ):
        from management.models import IgAiReplyRecoveryJob

        source = self._pending("Can you help me choose a T-shirt?", "untyped-none")

        self.assertEqual(instagram_bot.process_pending(self.settings, max_items=1), 1)

        self.client.refresh_from_db()
        self.assertFalse(
            IgAiReplyRecoveryJob.objects.filter(source_message=source).exists()
        )
        self.assertIn("manager", send_text.call_args.args[2].lower())
        self.assertEqual(self.client.stage, IgClient.Stage.LEAD_TO_MANAGER)


class LiveReplyReceiptTests(TestCase):
    def setUp(self):
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.ai_enabled = True
        self.settings.save(update_fields=["is_enabled", "ai_enabled"])
        self.client = IgClient.get_or_create_for_sender("live-receipt-client")

    def _pending(self, suffix: str) -> InstagramBotMessage:
        return InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Підкажіть, будь ласка, ціну.",
            mid=f"live-receipt-{suffix}",
            status=InstagramBotMessage.Status.PENDING,
        )

    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.gemini_generate", return_value="Зараз підкажу ціну.")
    @patch("management.services.instagram_bot.send_text")
    def test_confirmed_meta_receipt_persists_history_and_reply_time(
        self, send_text, _generate, _sender_action
    ):
        from management.services.instagram_bot import ProviderDeliveryReceipt

        send_text.return_value = ProviderDeliveryReceipt(
            True, "", "", "meta-live-receipt-1"
        )
        source = self._pending("confirmed")

        self.assertEqual(instagram_bot.process_pending(self.settings, max_items=1), 1)

        source.refresh_from_db()
        reply = InstagramBotMessage.objects.get(
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.MODEL,
        )
        self.client.refresh_from_db()
        self.assertEqual(source.send_state, "sent")
        self.assertEqual(reply.provider_message_id, "meta-live-receipt-1")
        self.assertIsNotNone(self.client.last_bot_reply_at)

    @patch("management.services.instagram_bot.send_sender_action")
    @patch("management.services.instagram_bot.gemini_generate", return_value="Зараз підкажу ціну.")
    @patch("management.services.instagram_bot.send_text")
    def test_meta_success_without_receipt_is_ambiguous_not_sent(
        self, send_text, _generate, _sender_action
    ):
        from management.services.instagram_bot import ProviderDeliveryReceipt

        send_text.return_value = ProviderDeliveryReceipt(True, "", "", "")
        source = self._pending("missing")

        self.assertEqual(instagram_bot.process_pending(self.settings, max_items=1), 0)

        source.refresh_from_db()
        self.assertEqual(source.status, InstagramBotMessage.Status.FAILED)
        self.assertEqual(source.send_state, "unknown")
        self.assertFalse(
            InstagramBotMessage.objects.filter(
                sender_id=self.client.igsid,
                role=InstagramBotMessage.Role.MODEL,
            ).exists()
        )

    @patch("management.services.instagram_bot._clear_client_delivery_error")
    @patch("management.services.instagram_bot._clear_send_error")
    @patch("management.services.instagram_bot._register_outgoing_message")
    @patch("management.services.instagram_bot._mark_bot_sent")
    @patch("management.services.instagram_bot._provider_url", return_value="https://meta.test/messages")
    @patch("management.services.instagram_bot.provider_transport")
    @patch("management.services.instagram_bot.get_page_token", return_value="token")
    @patch("management.services.instagram_bot._provider_account_id", return_value="account")
    @patch("management.services.instagram_bot._provider_http")
    def test_second_meta_chunk_without_id_is_unknown(
        self,
        provider_http,
        _account,
        _token,
        transport,
        _url,
        _mark,
        _register,
        _clear_send,
        _clear_client,
    ):
        provider_http.side_effect = [
            (200, '{"message_id":"first-chunk"}'),
            (200, "{}"),
        ]
        transport.return_value = instagram_bot.INSTAGRAM_LOGIN_TRANSPORT

        receipt = instagram_bot.send_text(
            self.settings,
            self.client.igsid,
            "a" * 951,
            return_receipt=True,
        )

        self.assertIsInstance(receipt, instagram_bot.ProviderDeliveryReceipt)
        self.assertFalse(receipt.ok)
        self.assertEqual(receipt.kind, "unknown")
        self.assertEqual(receipt.hint, "provider_message_id_missing")
        self.assertEqual(provider_http.call_count, 2)
