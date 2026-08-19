from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from management.models import (
    IgCommerceManagerReview,
    IgCommerceTurnDecision,
    IgClient,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services.ig_commerce_replies import build_durable_reply_payload
from management.services.ig_commerce_state import apply_turn, resume_turn_delivery
from management.services.ig_commerce_types import CommerceTurnRequest
from management.services import instagram_bot
from storefront.models import Category, Product, ProductStatus


class CommerceReplyBuilderTests(SimpleTestCase):
    def test_exact_reference_has_one_safe_persistable_reply(self):
        payload = build_durable_reply_payload(
            CommerceTurnRequest(exact_product_id=42),
            action="product_selected",
            reasons=("exact_product_reference",),
            before={},
            after={"lines": [{"product_id": 42}]},
        )

        self.assertEqual(payload, {
            "text": [
                "Зафіксувала цей варіант. Підкажіть, будь ласка, розмір, колір і кількість."
            ],
        })
        rendered = " ".join(payload["text"]).lower()
        for forbidden in ("грн", "наяв", "оплат", "http", "менеджер"):
            self.assertNotIn(forbidden, rendered)

    def test_clarification_and_stale_candidate_have_safe_single_replies(self):
        clarification = build_durable_reply_payload(
            CommerceTurnRequest(pending_clarification="multiple_product_links"),
            action="clarification_requested",
            reasons=("pending_clarification",),
            before={},
            after={"pending_clarification": "multiple_product_links"},
        )
        stale_candidate = build_durable_reply_payload(
            CommerceTurnRequest(query="1"),
            action="candidate_rejected",
            reasons=("candidate_prompt_mismatch",),
            before={"candidate_generation": 2},
            after={"rejected_reason": "candidate_prompt_mismatch"},
        )

        self.assertEqual(clarification, {
            "text": [
                "Бачу кілька товарів. Надішліть, будь ласка, одне посилання на потрібний варіант."
            ],
        })
        self.assertEqual(stale_candidate, {
            "text": [
                "Ця добірка вже неактуальна. Виберіть варіант з останнього повідомлення або надішліть посилання на товар."
            ],
        })
        for payload in (clarification, stale_candidate):
            rendered = " ".join(payload["text"]).lower()
            for forbidden in ("грн", "наяв", "оплат", "http", "менеджер"):
                self.assertNotIn(forbidden, rendered)

    def test_ordinary_field_update_stays_on_existing_reply_path(self):
        payload = build_durable_reply_payload(
            CommerceTurnRequest(field_updates={"size": "M"}),
            action="selection_updated",
            reasons=("explicit_field_update",),
            before={},
            after={"lines": [{"size": "M"}]},
        )

        self.assertEqual(payload, {})

    def test_every_supported_clarification_is_single_chunk_and_fact_safe(self):
        for clarification in (
            "multiple_product_links",
            "which_product",
            "print_placement",
            "new_purchase_or_exchange",
        ):
            with self.subTest(clarification=clarification):
                payload = build_durable_reply_payload(
                    CommerceTurnRequest(pending_clarification=clarification),
                    action="clarification_requested",
                    reasons=("pending_clarification",),
                    before={},
                    after={"pending_clarification": clarification},
                )
                self.assertEqual(len(payload.get("text") or []), 1)
                rendered = payload["text"][0].lower()
                for forbidden in ("грн", "наяв", "оплат", "http", "менеджер"):
                    self.assertNotIn(forbidden, rendered)


class CommerceReplyOutboxTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name=f"Commerce outbox {self._testMethodName}",
            slug=f"igco-out-{self._testMethodName}"[:45],
        )
        self.product = Product.objects.create(
            title="Commerce outbox T-shirt",
            slug=f"igco-shirt-{self._testMethodName}"[:45],
            category=self.category,
            price=1090,
            status=ProductStatus.PUBLISHED,
        )
        self.client = IgClient.get_or_create_for_sender(
            f"commerce-delivery-{self._testMethodName}"[:64]
        )

    def _source(self, suffix: str) -> InstagramBotMessage:
        return InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text=suffix,
            mid=f"commerce-delivery-{self._testMethodName}-{suffix}"[:255],
            provider_created_at=timezone.now(),
        )

    def test_reducer_persists_builder_payload_before_decision_creation(self):
        source = self._source("exact-reference")
        request = CommerceTurnRequest(exact_product_id=self.product.pk)

        decision = apply_turn(
            self.client,
            source,
            request,
            reply_builder=build_durable_reply_payload,
        )

        self.assertEqual(
            decision.reply_payload,
            {
                "text": [
                    "Зафіксувала цей варіант. Підкажіть, будь ласка, розмір, колір і кількість."
                ]
            },
        )
        self.assertTrue(decision.delivery_required)
        self.assertEqual(
            decision.delivery_state,
            IgCommerceTurnDecision.DeliveryState.PENDING,
        )

    def test_replay_returns_stored_payload_without_invoking_builder_again(self):
        source = self._source("builder-replay")
        first = apply_turn(
            self.client,
            source,
            CommerceTurnRequest(exact_product_id=self.product.pk),
            reply_builder=build_durable_reply_payload,
        )

        replay = apply_turn(
            self.client,
            source,
            CommerceTurnRequest(exact_product_id=self.product.pk),
            reply_builder=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("stored decision replay must bypass reply builder")
            ),
        )

        self.assertEqual(replay.pk, first.pk)
        self.assertEqual(replay.reply_payload, first.reply_payload)

    def test_invalid_transport_state_is_unknown_even_with_a_receipt(self):
        source = self._source("invalid-state")
        decision = apply_turn(
            self.client,
            source,
            CommerceTurnRequest(exact_product_id=self.product.pk),
            reply_builder=build_durable_reply_payload,
        )

        delivered = resume_turn_delivery(
            source,
            transport=lambda _decision: {
                "state": "provider_maybe",
                "text_receipts": [
                    {"index": 0, "provider_message_id": "meta-invalid-state"}
                ],
            },
        )

        self.assertEqual(
            delivered.delivery_state,
            IgCommerceTurnDecision.DeliveryState.UNKNOWN,
        )
        self.assertEqual(
            delivered.reconciliation_status,
            IgCommerceTurnDecision.ReconciliationStatus.REQUIRED,
        )
        self.assertTrue(
            IgCommerceManagerReview.objects.filter(
                decision=decision,
                reason="delivery_unknown",
            ).exists()
        )

    def test_blank_receipt_id_cannot_be_marked_sent(self):
        source = self._source("blank-receipt-id")
        decision = apply_turn(
            self.client,
            source,
            CommerceTurnRequest(exact_product_id=self.product.pk),
            reply_builder=build_durable_reply_payload,
        )

        delivered = resume_turn_delivery(
            source,
            transport=lambda _decision: {
                "state": "sent",
                "text_receipts": [
                    {"index": 0, "provider_message_id": "   "},
                ],
            },
        )

        self.assertEqual(
            delivered.delivery_state,
            IgCommerceTurnDecision.DeliveryState.UNKNOWN,
        )
        self.assertEqual(
            delivered.reconciliation_status,
            IgCommerceTurnDecision.ReconciliationStatus.REQUIRED,
        )
        self.assertTrue(
            IgCommerceManagerReview.objects.filter(
                decision=decision,
                reason="delivery_unknown",
            ).exists()
        )

    def test_duplicate_receipt_ids_cannot_be_marked_sent(self):
        source = self._source("duplicate-receipt-id")
        decision = apply_turn(
            self.client,
            source,
            CommerceTurnRequest(exact_product_id=self.product.pk),
            reply_payload={"text": ["one", "two"]},
        )

        delivered = resume_turn_delivery(
            source,
            transport=lambda _decision: {
                "state": "sent",
                "text_receipts": [
                    {"index": 0, "provider_message_id": "same-provider-id"},
                    {"index": 1, "provider_message_id": "same-provider-id"},
                ],
            },
        )

        self.assertEqual(
            delivered.delivery_state,
            IgCommerceTurnDecision.DeliveryState.UNKNOWN,
        )
        self.assertEqual(
            delivered.reconciliation_status,
            IgCommerceTurnDecision.ReconciliationStatus.REQUIRED,
        )
        self.assertTrue(
            IgCommerceManagerReview.objects.filter(
                decision=decision,
                reason="delivery_unknown",
            ).exists()
        )

    def test_overlong_receipt_id_cannot_be_marked_sent(self):
        source = self._source("overlong-receipt-id")
        decision = apply_turn(
            self.client,
            source,
            CommerceTurnRequest(exact_product_id=self.product.pk),
            reply_builder=build_durable_reply_payload,
        )

        delivered = resume_turn_delivery(
            source,
            transport=lambda _decision: {
                "state": "sent",
                "text_receipts": [
                    {"index": 0, "provider_message_id": "x" * 256},
                ],
            },
        )

        self.assertEqual(
            delivered.delivery_state,
            IgCommerceTurnDecision.DeliveryState.UNKNOWN,
        )
        self.assertEqual(
            delivered.reconciliation_status,
            IgCommerceTurnDecision.ReconciliationStatus.REQUIRED,
        )

    def test_indexed_receipt_without_id_is_unknown_not_partial(self):
        source = self._source("missing-indexed-receipt-id")
        decision = apply_turn(
            self.client,
            source,
            CommerceTurnRequest(exact_product_id=self.product.pk),
            reply_payload={"text": ["one"]},
        )

        delivered = resume_turn_delivery(
            source,
            transport=lambda _decision: {
                "state": "sent",
                "text_receipts": [{"index": 0}],
            },
        )

        self.assertEqual(
            delivered.delivery_state,
            IgCommerceTurnDecision.DeliveryState.UNKNOWN,
        )
        self.assertEqual(
            delivered.reconciliation_status,
            IgCommerceTurnDecision.ReconciliationStatus.REQUIRED,
        )

    def test_sent_without_any_receipt_is_unknown_not_partial(self):
        source = self._source("missing-receipt-list")
        decision = apply_turn(
            self.client,
            source,
            CommerceTurnRequest(exact_product_id=self.product.pk),
            reply_payload={"text": ["one"]},
        )

        delivered = resume_turn_delivery(
            source,
            transport=lambda _decision: {"state": "sent"},
        )

        self.assertEqual(
            delivered.delivery_state,
            IgCommerceTurnDecision.DeliveryState.UNKNOWN,
        )
        self.assertEqual(
            delivered.reconciliation_status,
            IgCommerceTurnDecision.ReconciliationStatus.REQUIRED,
        )
        self.assertTrue(
            IgCommerceManagerReview.objects.filter(
                decision=decision,
                reason="delivery_unknown",
            ).exists()
        )


class CommerceWorkerDeliveryTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name=f"Commerce delivery {self._testMethodName}",
            slug=f"igco-delivery-{self._testMethodName}"[:45],
        )
        self.product = Product.objects.create(
            title="Commerce delivery T-shirt",
            slug=f"igco-delivery-shirt-{self._testMethodName}"[:45],
            category=self.category,
            price=1090,
            status=ProductStatus.PUBLISHED,
        )
        self.client = IgClient.get_or_create_for_sender(
            f"commerce-worker-{self._testMethodName}"[:64]
        )
        self.client.profile_fetched_at = timezone.now()
        self.client.save(update_fields=["profile_fetched_at", "updated_at"])
        self.settings = InstagramBotSettings.load()
        self.settings.is_enabled = True
        self.settings.ai_enabled = True
        self.settings.save(update_fields=["is_enabled", "ai_enabled", "updated_at"])

    def _processing_row(self, suffix: str) -> InstagramBotMessage:
        return InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text=f"https://twocomms.shop/product/{self.product.slug}/",
            mid=f"commerce-worker-{self._testMethodName}-{suffix}"[:255],
            status=InstagramBotMessage.Status.PROCESSING,
            processing_started_at=timezone.now(),
        )

    def _worker_patches(self):
        return patch.multiple(
            "management.services.instagram_bot",
            _rate_exceeded=lambda *_args, **_kwargs: False,
            gemini_generate=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("durable commerce reply must not call Gemini")
            ),
            send_sender_action=lambda *_args, **_kwargs: None,
        )

    def test_receipted_durable_reply_skips_gemini_and_is_not_sent_twice(self):
        from management.services.instagram_bot import ProviderDeliveryReceipt

        row = self._processing_row("receipt")
        with self._worker_patches(), patch(
            "management.services.bot_sales_classifier.ensure_rule_classification",
            return_value=None,
        ) as classify, patch(
            "management.services.instagram_bot.send_text",
            return_value=ProviderDeliveryReceipt(True, "", "", "meta-commerce-1"),
        ) as send_text:
            self.assertTrue(instagram_bot._process_one(self.settings, row))

        decision = IgCommerceTurnDecision.objects.get(source_message=row)
        row.refresh_from_db()
        self.assertEqual(decision.delivery_state, IgCommerceTurnDecision.DeliveryState.SENT)
        self.assertEqual(decision.provider_message_ids, ["meta-commerce-1"])
        self.assertEqual(
            decision.text_receipts,
            [{"index": 0, "provider_message_id": "meta-commerce-1"}],
        )
        self.assertEqual(row.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(row.send_state, "sent")
        self.assertEqual(send_text.call_count, 1)
        self.assertEqual(send_text.call_args.args[2], decision.reply_payload["text"][0])
        self.assertTrue(send_text.call_args.kwargs["return_receipt"])
        classify.assert_not_called()
        reply = InstagramBotMessage.objects.get(
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.MODEL,
        )
        self.assertEqual(reply.text, decision.reply_payload["text"][0])
        self.assertEqual(reply.provider_message_id, "meta-commerce-1")

        replay = resume_turn_delivery(
            row,
            transport=lambda _decision: (_ for _ in ()).throw(
                AssertionError("sent decision must not be replayed")
            ),
        )
        self.assertEqual(replay.delivery_state, IgCommerceTurnDecision.DeliveryState.SENT)

    def test_non_durable_field_update_continues_through_gemini(self):
        from management.services.instagram_bot import ProviderDeliveryReceipt

        row = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="M",
            mid=f"commerce-worker-{self._testMethodName}-field-update"[:255],
            status=InstagramBotMessage.Status.PROCESSING,
            processing_started_at=timezone.now(),
        )
        with patch(
            "management.services.bot_sales_classifier.ensure_rule_classification",
            return_value=None,
        ), patch(
            "management.services.instagram_bot._rate_exceeded",
            return_value=False,
        ), patch(
            "management.services.instagram_bot._repeated_question",
            return_value=0,
        ), patch(
            "management.services.instagram_bot.send_sender_action",
            return_value=None,
        ), patch(
            "management.services.instagram_bot.gemini_generate",
            return_value="Підкажу деталі.",
        ) as gemini, patch(
            "management.services.instagram_bot.send_text",
            return_value=ProviderDeliveryReceipt(
                True,
                "",
                "",
                "meta-commerce-field-update",
            ),
        ), patch("management.services.instagram_bot.log") as log:
            self.assertTrue(instagram_bot._process_one(self.settings, row))

        decision = IgCommerceTurnDecision.objects.get(source_message=row)
        self.assertFalse(decision.delivery_required)
        self.assertEqual(
            decision.delivery_state,
            IgCommerceTurnDecision.DeliveryState.NOT_REQUIRED,
        )
        self.assertEqual(gemini.call_count, 1)
        self.assertNotIn(
            "commerce_turn_project",
            [call.args[1] for call in log.call_args_list if len(call.args) > 1],
        )

    def test_missing_receipt_becomes_unknown_with_one_review_and_no_replay(self):
        from management.services.instagram_bot import ProviderDeliveryReceipt

        row = self._processing_row("unknown")
        with self._worker_patches(), patch(
            "management.services.bot_sales_classifier.ensure_rule_classification",
            return_value=None,
        ), patch(
            "management.services.instagram_bot.send_text",
            return_value=ProviderDeliveryReceipt(True, "", "", "   "),
        ) as send_text:
            self.assertFalse(instagram_bot._process_one(self.settings, row))

        decision = IgCommerceTurnDecision.objects.get(source_message=row)
        row.refresh_from_db()
        self.assertEqual(decision.delivery_state, IgCommerceTurnDecision.DeliveryState.UNKNOWN)
        self.assertEqual(
            decision.reconciliation_status,
            IgCommerceTurnDecision.ReconciliationStatus.REQUIRED,
        )
        self.assertEqual(row.status, InstagramBotMessage.Status.FAILED)
        self.assertEqual(row.send_state, "unknown")
        self.assertEqual(send_text.call_count, 1)
        self.assertTrue(
            IgCommerceManagerReview.objects.filter(
                decision=decision,
                reason="delivery_unknown",
            ).exists()
        )

        replay = resume_turn_delivery(
            row,
            transport=lambda _decision: (_ for _ in ()).throw(
                AssertionError("unknown decision must not be replayed")
            ),
        )
        self.assertEqual(replay.delivery_state, IgCommerceTurnDecision.DeliveryState.UNKNOWN)
        self.assertEqual(send_text.call_count, 1)

    def test_transport_exception_is_terminal_unknown_with_one_review(self):
        row = self._processing_row("transport-exception")
        with self._worker_patches(), patch(
            "management.services.bot_sales_classifier.ensure_rule_classification",
            return_value=None,
        ) as classify, patch(
            "management.services.instagram_bot.send_text",
            side_effect=TimeoutError("Meta receipt timed out"),
        ) as send_text:
            self.assertFalse(instagram_bot._process_one(self.settings, row))

        decision = IgCommerceTurnDecision.objects.get(source_message=row)
        row.refresh_from_db()
        self.assertEqual(
            decision.delivery_state,
            IgCommerceTurnDecision.DeliveryState.UNKNOWN,
        )
        self.assertEqual(
            decision.reconciliation_status,
            IgCommerceTurnDecision.ReconciliationStatus.REQUIRED,
        )
        self.assertEqual(row.status, InstagramBotMessage.Status.FAILED)
        self.assertEqual(row.send_state, "unknown")
        self.assertEqual(send_text.call_count, 1)
        classify.assert_not_called()
        self.assertEqual(
            IgCommerceManagerReview.objects.filter(
                decision=decision,
                reason="delivery_unknown",
            ).count(),
            1,
        )

    def test_existing_sending_decision_requires_one_review_without_resend(self):
        row = self._processing_row("sending")
        decision = apply_turn(
            self.client,
            row,
            CommerceTurnRequest(exact_product_id=self.product.pk),
            reply_builder=build_durable_reply_payload,
        )
        IgCommerceTurnDecision.objects.filter(pk=decision.pk).update(
            delivery_state=IgCommerceTurnDecision.DeliveryState.SENDING,
            reconciliation_status=IgCommerceTurnDecision.ReconciliationStatus.NOT_REQUIRED,
        )

        with self._worker_patches(), patch(
            "management.services.bot_sales_classifier.ensure_rule_classification",
            return_value=None,
        ) as classify, patch(
            "management.services.instagram_bot.send_text",
            side_effect=AssertionError("sending decision must not cross Meta again"),
        ) as send_text:
            self.assertFalse(instagram_bot._process_one(self.settings, row))

        decision.refresh_from_db()
        row.refresh_from_db()
        self.assertEqual(
            decision.delivery_state,
            IgCommerceTurnDecision.DeliveryState.SENDING,
        )
        self.assertEqual(
            decision.reconciliation_status,
            IgCommerceTurnDecision.ReconciliationStatus.REQUIRED,
        )
        self.assertEqual(row.status, InstagramBotMessage.Status.FAILED)
        self.assertEqual(row.send_state, "unknown")
        self.assertEqual(send_text.call_count, 0)
        classify.assert_not_called()
        self.assertEqual(
            IgCommerceManagerReview.objects.filter(
                decision=decision,
                reason="delivery_sending",
            ).count(),
            1,
        )

    def test_stale_reclaimer_finalizes_receipted_sent_decision_exactly_once(self):
        row = self._processing_row("sent-before-local-finalize")
        row.send_state = "sending"
        row.send_started_at = timezone.now()
        row.processing_started_at = timezone.now() - timedelta(minutes=10)
        row.save(
            update_fields=[
                "send_state",
                "send_started_at",
                "processing_started_at",
            ]
        )
        decision = apply_turn(
            self.client,
            row,
            CommerceTurnRequest(exact_product_id=self.product.pk),
            reply_builder=build_durable_reply_payload,
        )
        delivered = resume_turn_delivery(
            row,
            transport=lambda _decision: {
                "state": "sent",
                "text_receipts": [
                    {"index": 0, "provider_message_id": "meta-recovered-sent"}
                ],
            },
        )
        self.assertEqual(
            delivered.delivery_state,
            IgCommerceTurnDecision.DeliveryState.SENT,
        )
        replies_before = self.settings.replies_count

        self.assertEqual(instagram_bot.reclaim_stale_processing(max_age_seconds=0), 0)

        row.refresh_from_db()
        self.settings.refresh_from_db()
        self.client.refresh_from_db()
        self.assertEqual(row.status, InstagramBotMessage.Status.DONE)
        self.assertEqual(row.send_state, "sent")
        self.assertEqual(self.settings.replies_count, replies_before + 1)
        self.assertIsNotNone(self.settings.last_reply_at)
        self.assertIsNotNone(self.client.last_bot_reply_at)
        self.assertEqual(
            InstagramBotMessage.objects.filter(
                sender_id=self.client.igsid,
                role=InstagramBotMessage.Role.MODEL,
                provider_message_id="meta-recovered-sent",
            ).count(),
            1,
        )

        self.assertEqual(instagram_bot.reclaim_stale_processing(max_age_seconds=0), 0)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.replies_count, replies_before + 1)

    def test_stale_sending_reclaim_marks_decision_for_review_without_resend(self):
        row = self._processing_row("sending-reclaim")
        row.send_state = "sending"
        row.send_started_at = timezone.now() - timedelta(minutes=10)
        row.processing_started_at = timezone.now() - timedelta(minutes=10)
        row.save(update_fields=["send_state", "send_started_at", "processing_started_at"])
        decision = apply_turn(
            self.client,
            row,
            CommerceTurnRequest(exact_product_id=self.product.pk),
            reply_builder=build_durable_reply_payload,
        )
        IgCommerceTurnDecision.objects.filter(pk=decision.pk).update(
            delivery_state=IgCommerceTurnDecision.DeliveryState.SENDING,
        )

        self.assertEqual(instagram_bot.reclaim_stale_processing(max_age_seconds=0), 0)

        decision.refresh_from_db()
        self.assertEqual(
            decision.reconciliation_status,
            IgCommerceTurnDecision.ReconciliationStatus.REQUIRED,
        )
        self.assertEqual(
            IgCommerceManagerReview.objects.filter(
                decision=decision,
                reason="delivery_sending",
            ).count(),
            1,
        )
